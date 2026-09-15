"""The Agent-driven acceptance loop as a CLI.

The Agent executes every host call itself through its own MCP client. This
command surface is where it opens a Workflow, reports what a call returned, asks
Python to evaluate a Stage against the frozen checklists, and reads the
aggregated result. Python never picks a call, never schedules a Stage, and never
invents a checklist item.

Commands:

    open     validate an Agent-authored Workflow and start a session
    record   submit one executed call result as evidence
    item     submit one execution checklist item result
    check    submit one manual acceptance check result
    stage    evaluate one Stage and close it
    finish   aggregate the final TaskResult
    status   show current session state without changing it

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
)
from ainative.session_api import AcceptanceGuide, AcceptanceSession, WorkflowError

# A Stage that reached one of these is closed.
CLOSED_STATUSES = frozenset({TaskStatus.SUCCEEDED, TaskStatus.DEGRADED})


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
    """Validate an Agent-authored Workflow and write the initial session state."""

    workflow_document = _load_json(args.workflow, "workflow")
    state = SessionState(
        task=_load_json(args.task, "task"),
        workflow=workflow_document,
    )
    workflow = state.workflow_object()
    validate_workflow_structure(workflow)
    session = AcceptanceGuide().start(task_from_dict(state.task, "task"), workflow)
    state.save(Path(args.state))

    verdict = Verdict.SUCCEEDED if session.ready else Verdict.BLOCKED
    payload = envelope(
        "open",
        verdict=verdict,
        detail={
            "state": str(args.state),
            "ready": session.ready,
            "guidance": workflow.guidance,
            "route": workflow.route.value,
            "stages": [stage.stage_id for stage in workflow.stage_requests],
            "blocked_reasons": list(session.gate.blocked_reasons),
        },
        errors=session.gate.blocked_reasons,
    )
    return payload, payload["exit_code"]


def command_record(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Submit one executed call result as evidence."""

    state = SessionState.load(Path(args.state))
    result = execution_result_from_dict(_load_json(args.result, "result"), "result")
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
    """Submit one execution checklist item result."""

    state = SessionState.load(Path(args.state))
    item = execution_item_result_from_dict(_load_json(args.result, "result"), "result")
    state.append(EVENT_EXECUTION_ITEM, item.to_dict())
    replay(state)
    state.save(Path(args.state))

    payload = envelope(
        "item",
        verdict=verdict_for_check_status(item.status),
        detail={"item_id": item.item_id, "status": item.status.value},
        errors=(item.reason,) if item.reason else (),
    )
    return payload, payload["exit_code"]


def command_check(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Submit one manual acceptance check result."""

    state = SessionState.load(Path(args.state))
    check = check_result_from_dict(_load_json(args.result, "result"), "result")
    state.append(EVENT_CHECK, check.to_dict())
    replay(state)
    state.save(Path(args.state))

    payload = envelope(
        "check",
        verdict=verdict_for_check_status(check.status),
        detail={"check_id": check.check_id, "status": check.status.value},
        errors=(check.reason,) if check.reason else (),
    )
    return payload, payload["exit_code"]


def command_stage(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Evaluate one Stage against its frozen checklists and close it."""

    state = SessionState.load(Path(args.state))
    session = replay(state)
    result = session.complete_stage(args.stage)
    if result.status in CLOSED_STATUSES and args.stage not in state.closed_stages:
        state.append(EVENT_STAGE_CLOSED, {"stage_id": args.stage})
    state.save(Path(args.state))

    detail = result.to_dict()
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
    """Show the current session state without changing it."""

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
            "completed_calls": list(session.completed_call_ids),
            "completed_stages": list(session.completed_stage_ids),
            "remaining_stages": [
                stage.stage_id
                for stage in session.workflow.stage_requests
                if stage.required and stage.stage_id not in closed
            ],
            "blocked_reasons": list(session.gate.blocked_reasons),
        },
        errors=session.gate.blocked_reasons,
    )
    return payload, payload["exit_code"]


COMMANDS = {
    "open": command_open,
    "record": command_record,
    "item": command_item,
    "check": command_check,
    "stage": command_stage,
    "finish": command_finish,
    "status": command_status,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ainative.session",
        description="Agent-driven Workflow acceptance loop; the Agent executes, Python evaluates.",
    )
    parser.add_argument("--state", required=True, help="session state file (created by 'open')")
    parser.add_argument("--task", help="task JSON (required by 'open')")
    parser.add_argument("--workflow", help="Workflow JSON (required by 'open')")
    parser.add_argument("--result", help="result JSON (required by record/item/check)")
    parser.add_argument("--stage", help="stage id (required by 'stage')")
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args(argv)

    if args.command == "open" and (not args.task or not args.workflow):
        parser.error("open requires --task and --workflow")
    if args.command in {"record", "item", "check"} and not args.result:
        parser.error(f"{args.command} requires --result")
    if args.command == "stage" and not args.stage:
        parser.error("stage requires --stage")

    try:
        payload, code = COMMANDS[args.command](args)
    except (SessionStateError, WorkflowDeserializationError, WorkflowIntegrityError, WorkflowError) as exc:
        payload, code = unusable(args.command, str(exc))
    emit(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
