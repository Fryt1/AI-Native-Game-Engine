"""The Agent-driven acceptance loop as a CLI.

The Agent executes every host call itself through its own MCP client. This
command surface is where it opens a Workflow, reports what a call returned, asks
Python to evaluate a Stage against the frozen checklists, and reads the
aggregated result. Python never picks a call, never schedules a Stage, and never
invents a checklist item.

Commands:

    open       validate an Agent-authored Workflow and start a session
    record     submit one executed call result as evidence
    item       submit one execution checklist item result
    check      submit one manual acceptance check result
    stage      evaluate one Stage and close it
    finish     aggregate the final TaskResult
    status     show current session state without changing it
    supersede  replace the Workflow revision, archiving the old one

A Workflow revision is immutable. `open` refuses to overwrite a state that has
recorded progress, because that would silently discard evidence; replacing a
Workflow is `supersede`, which archives the old revision and the evidence
recorded against it.

Every command prints the same envelope — command, ok, verdict, exit_code, detail,
errors — and exits 0 on a non-blocking result, 1 on a blocking or failing result,
and 2 when the command itself could not run. See `output.py` for the shape.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ainative.cli.output import (
    Verdict,
    emit,
    envelope,
    unusable,
    verdict_for_check_status,
    verdict_for_task_status,
)
from ainative.cli.state import (
    EVENT_CHECK,
    EVENT_EXECUTION_ITEM,
    EVENT_EXECUTION_RESULT,
    EVENT_STAGE_CLOSED,
    SessionState,
    SessionStateError,
)
from ainative.model.results import TaskStatus
from ainative.reading import (
    WorkflowDeserializationError,
    WorkflowIntegrityError,
    check_result_from_dict,
    execution_item_result_from_dict,
    execution_result_from_dict,
    task_from_dict,
    validate_workflow_structure,
    workflow_from_dict,
)
from ainative.session_api import AcceptanceGuide, AcceptanceSession, WorkflowError

# A Stage that reached one of these is closed.
CLOSED_STATUSES = frozenset({TaskStatus.SUCCEEDED, TaskStatus.DEGRADED})


# A command may learn facts about its input before it can fail. `announce` records
# them so a rejected submission still tells the caller which item or check it was,
# instead of an empty detail.
_CONTEXT: dict[str, Any] = {}


def announce(key: str, value: Any) -> None:
    """Record one identifying fact about the current command's input."""

    _CONTEXT[key] = value


def _load_json(path: str | None, what: str) -> Any:
    if not path:
        raise SessionStateError(f"{what} file is required")
    source = Path(path)
    if not source.is_file():
        raise SessionStateError(f"{what} file does not exist: {source}")
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SessionStateError(f"{what} is not valid JSON: {exc}") from exc


def _stage_of(workflow, declared_id: str, what: str) -> str:
    """Find the Stage that declares one checklist item or check."""

    for stage in workflow.stage_requests:
        if any(item.item_id == declared_id for item in stage.execution_checklist):
            return stage.stage_id
        if any(check.check_id == declared_id for check in stage.acceptance_checklist):
            return stage.stage_id
    raise SessionStateError(f"{what} is not declared in the Workflow: {declared_id}")


def replay(state: SessionState) -> AcceptanceSession:
    """Rebuild the session by replaying the Agent's evidence in submitted order.

    Replay must follow the original order, because a call may only be recorded
    after the Stage it depends on has closed. Rebuilding from unordered sets would
    re-trigger dependency failures the Agent already satisfied.

    @param state: the stored workflow and evidence.
    @returns the session with all evidence applied.
    @throws WorkflowError when the Workflow or an event cannot be applied.
    """

    workflow = state.workflow_object()
    task = task_from_dict(state.task, "state.task")
    session = AcceptanceGuide().start(task, workflow)
    for event_type, payload in state.event_objects():
        if event_type == EVENT_EXECUTION_RESULT:
            session.record_execution_result(payload)
        elif event_type == EVENT_EXECUTION_ITEM:
            session.record_execution_item(_stage_of(workflow, payload.item_id, "execution item"), payload)
        elif event_type == EVENT_CHECK:
            session.record_check_result(_stage_of(workflow, payload.check_id, "acceptance check"), payload)
        elif event_type == EVENT_STAGE_CLOSED:
            session.complete_stage(payload)
    return session


def command_open(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Validate an Agent-authored Workflow and write the initial session state.

    Refuses to overwrite a state that already has recorded progress: that would
    discard evidence the Agent submitted. Replacing a Workflow is `supersede`.
    """

    path = Path(args.state)
    if path.is_file():
        existing = SessionState.load(path)
        if existing.has_progress:
            raise SessionStateError(
                f"session state already has recorded progress: {path}; "
                "use supersede to replace the Workflow revision, or a new --state file"
            )

    workflow_document = _load_json(args.workflow, "workflow")
    state = SessionState(
        task=_load_json(args.task, "task"),
        workflow=workflow_document,
    )
    workflow = state.workflow_object()
    validate_workflow_structure(workflow)
    session = AcceptanceGuide().start(task_from_dict(state.task, "task"), workflow)
    state.save(path)

    verdict = Verdict.SUCCEEDED if session.ready else Verdict.BLOCKED
    payload = envelope(
        "open",
        verdict=verdict,
        detail={
            "state": str(args.state),
            "ready": session.ready,
            "guidance": workflow.guidance,
            "route": workflow.route.value,
            "revision_id": workflow.revision_id,
            "stages": [stage.stage_id for stage in workflow.stage_requests],
            "blocked_reasons": list(session.gate.blocked_reasons),
        },
        errors=session.gate.blocked_reasons,
    )
    return payload, payload["exit_code"]


def command_supersede(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Replace the Workflow revision, archiving the old one and its evidence.

    Reports which Stages carry over (unchanged definition) and, separately, which
    Stages had already touched the outside world. Python cannot undo a host edit,
    so a Stage that ran once and is re-run may apply its change twice; naming it
    is the most this layer can do.
    """

    path = Path(args.state)
    state = SessionState.load(path)
    previous = state.workflow_object()

    workflow_document = _load_json(args.workflow, "workflow")
    replacement = workflow_from_dict(workflow_document)
    validate_workflow_structure(replacement)

    if state.has_progress and not replacement.supersedes_workflow_id:
        raise SessionStateError(
            "a replacement revision must name the revision it replaces; "
            f"set supersedes_workflow_id to {previous.revision_id!r}"
        )

    carried = state.carried_over_stages(workflow_document)
    touched_before = set(state.side_effect_stages)

    reason = args.reason or "the Agent authored a replacement revision"
    carried = state.supersede(workflow_document, reason)
    session = AcceptanceGuide().start(task_from_dict(state.task, "task"), replacement)
    state.save(path)

    # A Stage is at risk when its calls already ran against a live host and its
    # definition changed, so the earlier proof no longer covers it and re-running
    # it would repeat a host change.
    at_risk = tuple(
        stage.stage_id
        for stage in replacement.stage_requests
        if stage.stage_id not in carried and stage.stage_id in touched_before
    )

    verdict = Verdict.SUCCEEDED if session.ready else Verdict.BLOCKED
    payload = envelope(
        "supersede",
        verdict=verdict,
        detail={
            "state": str(args.state),
            "ready": session.ready,
            "superseded_revision_id": previous.revision_id,
            "revision_id": replacement.revision_id,
            "reason": reason,
            "carried_over": list(carried),
            "invalidated": [
                stage.stage_id
                for stage in replacement.stage_requests
                if stage.stage_id not in carried
            ],
            "side_effects_at_risk": list(at_risk),
            "archived_events": len(state.revisions[-1]["events"]) if state.revisions else 0,
            "revision_count": len(state.revisions),
            "stages": [stage.stage_id for stage in replacement.stage_requests],
            "blocked_reasons": list(session.gate.blocked_reasons),
        },
        errors=session.gate.blocked_reasons,
    )
    return payload, payload["exit_code"]


def command_record(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Submit one executed call result as evidence.

    Refuses to re-report a call whose Stage has already run that call against a
    live host, unless the Agent says it means to. The reachable hazard is a
    replacement revision: it invalidates a Stage, the Stage's calls become
    runnable again, and re-running one applies the same host change a second time.

    Python cannot see the host, let alone undo it, so this is the point where the
    repeat is preventable.
    """

    state = SessionState.load(Path(args.state))
    result = execution_result_from_dict(_load_json(args.result, "result"), "result")

    if not args.confirm_side_effects:
        already_run = state.calls_already_run()
        if result.call_id in already_run:
            raise SessionStateError(
                f"call {result.call_id} has already run against a live host "
                f"(revision {already_run[result.call_id]}); reporting a new result for it "
                "could apply the same change twice. "
                "Pass --confirm-side-effects to proceed, or author a replacement revision"
            )

    state.append(EVENT_EXECUTION_RESULT, result.to_dict())
    replay(state)
    state.save(Path(args.state))

    payload = envelope(
        "record",
        verdict=verdict_for_task_status(result.status),
        detail={"call_id": result.call_id, "status": result.status.value},
        errors=result.errors,
    )
    return payload, payload["exit_code"]


def command_item(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Submit one execution checklist item result.

    The item id is read before anything else, so a rejected submission still names
    the item it concerned.
    """

    state = SessionState.load(Path(args.state))
    item = execution_item_result_from_dict(_load_json(args.result, "result"), "result")
    announce("item_id", item.item_id)
    announce("status", item.status.value)

    session = replay(state)
    owning = next(
        (
            stage.stage_id
            for stage in session.workflow.stage_requests
            if any(entry.item_id == item.item_id for entry in stage.execution_checklist)
        ),
        None,
    )
    if owning is None:
        raise SessionStateError(f"execution item is not declared in the Workflow: {item.item_id}")
    announce("stage_id", owning)

    state.append(EVENT_EXECUTION_ITEM, item.to_dict())
    replay(state)
    state.save(Path(args.state))

    payload = envelope(
        "item",
        verdict=verdict_for_check_status(item.status),
        detail={
            "item_id": item.item_id,
            "status": item.status.value,
            "stage_id": owning,
        },
        errors=(item.reason,) if item.reason else (),
    )
    return payload, payload["exit_code"]


def command_check(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Submit one manual acceptance check result.

    The check id is read before anything else, so a rejected submission still names
    the check it concerned.
    """

    state = SessionState.load(Path(args.state))
    check = check_result_from_dict(_load_json(args.result, "result"), "result")
    announce("check_id", check.check_id)
    announce("status", check.status.value)

    session = replay(state)
    owning = next(
        (
            stage.stage_id
            for stage in session.workflow.stage_requests
            if any(entry.check_id == check.check_id for entry in stage.acceptance_checklist)
        ),
        None,
    )
    if owning is None:
        raise SessionStateError(f"acceptance check is not declared in the Workflow: {check.check_id}")
    announce("stage_id", owning)

    state.append(EVENT_CHECK, check.to_dict())
    replay(state)
    state.save(Path(args.state))

    payload = envelope(
        "check",
        verdict=verdict_for_check_status(check.status),
        detail={
            "check_id": check.check_id,
            "status": check.status.value,
            "stage_id": owning,
        },
        errors=(check.reason,) if check.reason else (),
    )
    return payload, payload["exit_code"]


def command_stage(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Evaluate one Stage against its frozen checklists and close it.

    Closing a Stage is idempotent: asking again returns the verdict already
    recorded. The hazard of a repeated host change is guarded where the call is
    reported, not here -- see `command_record`.
    """

    state = SessionState.load(Path(args.state))
    session = replay(state)

    closed_before = args.stage in state.closed_stages
    result = session.complete_stage(args.stage)
    if result.status in CLOSED_STATUSES and not closed_before:
        state.append(EVENT_STAGE_CLOSED, {"stage_id": args.stage})
    state.save(Path(args.state))

    detail = result.to_dict()
    detail["side_effects_recorded"] = session.has_side_effects(args.stage)
    payload = envelope(
        "stage",
        verdict=verdict_for_task_status(result.status),
        detail=detail,
        errors=detail.get("errors", ()),
    )
    return payload, payload["exit_code"]


def command_finish(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Aggregate the final TaskResult from the recorded evidence."""

    state = SessionState.load(Path(args.state))
    result = replay(state).finish()

    detail = result.to_dict()
    payload = envelope(
        "finish",
        verdict=verdict_for_task_status(result.status),
        detail=detail,
        errors=detail.get("errors", ()),
    )
    return payload, payload["exit_code"]


def command_status(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Show the current session state without changing it.

    Includes a summary of the bound Workflow, so the Agent can see what it is
    committed to without re-reading the file it authored -- which it may have
    edited since, or lost with the process.
    """

    state = SessionState.load(Path(args.state))
    session = replay(state)
    result = session.finish()
    closed = set(session.completed_stage_ids)

    payload = envelope(
        "status",
        verdict=verdict_for_task_status(result.status),
        detail={
            "state": str(args.state),
            "ready": session.ready,
            "revision_id": session.workflow.revision_id,
            "revision_count": len(state.revisions),
            "completed_calls": list(session.completed_call_ids),
            "completed_stages": list(session.completed_stage_ids),
            "remaining_stages": [
                stage.stage_id
                for stage in session.workflow.stage_requests
                if stage.required and stage.stage_id not in closed
            ],
            "blocked_reasons": list(session.gate.blocked_reasons),
            "workflow": _workflow_summary(session, state),
        },
        errors=session.gate.blocked_reasons,
    )
    return payload, payload["exit_code"]


def _workflow_summary(session: AcceptanceSession, state: SessionState) -> dict[str, Any]:
    """Describe the bound Workflow: its identity, its Stages, and what each needs.

    Enough for the Agent to act without opening the Workflow file again: which
    Stage is closed, which calls it declared, and which checks must be proven.
    """

    closed = set(session.completed_stage_ids)
    touched = set(session.stages_with_side_effects)
    return {
        "workflow_id": session.workflow.workflow_id,
        "revision": session.workflow.revision,
        "guidance": session.workflow.guidance,
        "route": session.workflow.route.value,
        "supersedes_workflow_id": session.workflow.supersedes_workflow_id,
        "replaced": [
            entry.get("revision_id")
            for entry in state.revisions
        ],
        "stages": [
            {
                "stage_id": stage.stage_id,
                "step_id": step.step_id,
                "stage_kind": stage.stage_kind.value,
                "purpose": stage.purpose,
                "required": stage.required,
                "closed": stage.stage_id in closed,
                "side_effects_recorded": stage.stage_id in touched,
                "calls": [
                    {"call_id": call.call_id, "target": call.target.to_dict()}
                    for call in stage.calls
                ],
                "execution_checklist": [
                    {"item_id": item.item_id, "required": item.required}
                    for item in stage.execution_checklist
                ],
                "acceptance_checklist": [
                    {"check_id": check.check_id, "operator": check.operator.value,
                     "required": check.required}
                    for check in stage.acceptance_checklist
                ],
            }
            for step in session.workflow.steps
            for stage in step.stages
        ],
    }


COMMANDS = {
    "open": command_open,
    "record": command_record,
    "item": command_item,
    "check": command_check,
    "stage": command_stage,
    "finish": command_finish,
    "status": command_status,
    "supersede": command_supersede,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ainative.session",
        description="Agent-driven Workflow acceptance loop; the Agent executes, Python evaluates.",
    )
    parser.add_argument("--state", required=True, help="session state file (created by 'open')")
    parser.add_argument("--task", help="task JSON (required by 'open')")
    parser.add_argument("--workflow", help="Workflow JSON (required by 'open' and 'supersede')")
    parser.add_argument("--result", help="result JSON (required by record/item/check)")
    parser.add_argument("--stage", help="stage id (required by 'stage')")
    parser.add_argument("--reason", help="why the previous revision was abandoned (used by 'supersede')")
    parser.add_argument(
        "--confirm-side-effects",
        action="store_true",
        dest="confirm_side_effects",
        help="acknowledge that this call may re-apply a host change (used by 'record')",
    )
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args(argv)

    if args.command == "open" and (not args.task or not args.workflow):
        parser.error("open requires --task and --workflow")
    if args.command == "supersede" and not args.workflow:
        parser.error("supersede requires --workflow")
    if args.command in {"record", "item", "check"} and not args.result:
        parser.error(f"{args.command} requires --result")
    if args.command == "stage" and not args.stage:
        parser.error("stage requires --stage")

    _CONTEXT.clear()
    try:
        payload, code = COMMANDS[args.command](args)
    except (SessionStateError, WorkflowDeserializationError, WorkflowIntegrityError, WorkflowError) as exc:
        payload, code = unusable(args.command, str(exc), context=_CONTEXT)
    emit(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
