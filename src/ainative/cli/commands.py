"""The Agent-driven acceptance loop as a CLI.

The Agent executes every host call itself through its own MCP client. This
command surface is where it opens a Workflow, reports what a call returned, asks
Python to evaluate a node against the frozen checklists, and reads the aggregated
result. Python never picks a call, never schedules a node, and never invents a
checklist item.

Commands:

    open       validate an Agent-authored Workflow and start a session
    record     submit one executed call result as evidence
    item       submit one execution checklist item result
    check      submit one manual acceptance check result
    stage      evaluate one node and close it
    finish     aggregate the final TaskResult
    status     show current session state without changing it
    supersede  replace the Workflow revision, archiving the old one

A node is named by **path** (``/buildings/tower_a/mass/``), never by a bare id: a
``node_id`` is unique only among siblings, which is what lets two subtrees each
declare a ``mass``. ``--stage`` takes that path and may address a STAGE or a
composite.

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
    EVENT_NODE_CLOSED,
    SessionState,
    SessionStateError,
)
from ainative.model.results import TaskStatus
from ainative.reading import (
    TreeIntegrityError,
    WorkflowDeserializationError,
    check_result_from_dict,
    execution_item_result_from_dict,
    execution_result_from_dict,
    task_from_dict,
    validate_tree_structure,
    workflow_from_dict,
)
from ainative.session_api import (
    AcceptanceGuide,
    AcceptanceSession,
    SkillIntegrityError,
    WorkflowError,
)

# A Stage that reached one of these is closed.
CLOSED_STATUSES = frozenset({TaskStatus.SUCCEEDED, TaskStatus.DEGRADED})

#: The code-defined spec: the shape a Workflow document must have.
SPEC_PATH = Path(__file__).resolve().parents[3] / "templates" / "workflow.schema.json"


def _spec_check(document: Any) -> None:
    """Refuse a Workflow document that does not match the spec.

    The spec is the definition of the data structure, so a document that violates
    it is not a Workflow however well-formed its JSON. Without this the two
    definitions drift silently: ``validate_tree_structure`` checks semantics the
    spec cannot express, and nothing checked the shape the spec *does* express.

    This fails closed when the spec itself cannot be read. A spec that is missing
    is not permission to skip it.
    """

    from ainative.reading import schema as schema_module

    try:
        spec = schema_module.load_schema(SPEC_PATH)
    except (OSError, ValueError) as exc:
        raise SessionStateError(
            f"the Workflow spec cannot be read at {SPEC_PATH}: {exc}") from exc
    try:
        schema_module.validate(document, spec)
    except schema_module.SchemaError as exc:
        # Named, because a bare JSON pointer does not say which document it came
        # from, and this is the message a caller reads first.
        raise SessionStateError(f"workflow does not match the spec: {exc}") from exc


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


def _owning_node(session: AcceptanceSession, declared_id: str, what: str) -> str:
    """Find the node that declares one checklist item or check.

    A bare id is resolved only when exactly one node in the tree declares it. Two
    subtrees may each declare ``built``, and judging one of them when the Agent
    meant the other would be a silent wrong answer, so an ambiguous id is refused
    and the caller must name the node path.
    """

    for finder in (session.workflow.path_of_item, session.workflow.path_of_check):
        path = finder(declared_id)
        if path is not None:
            return path
    raise SessionStateError(
        f"{what} is not declared by exactly one node in the Workflow: {declared_id}; "
        "name the node with --stage when the id is ambiguous")


def replay(state: SessionState) -> AcceptanceSession:
    """Rebuild the session by replaying the Agent's evidence in submitted order.

    Replay must follow the original order, because a call may only be recorded
    after the node it depends on has closed. Rebuilding from unordered sets would
    re-trigger dependency failures the Agent already satisfied.

    @param state: the stored workflow and evidence.
    @returns the session with all evidence applied.
    @throws WorkflowError when the Workflow or an event cannot be applied.
    """

    workflow = state.workflow_object()
    task = task_from_dict(state.task, "state.task")
    session = AcceptanceGuide().start(task, workflow)
    for event_type, payload, owner in state.event_objects():
        if event_type == EVENT_EXECUTION_RESULT:
            # Applying the log is not accepting a submission: the ordering was
            # checked when the event was taken in, and a replacement can archive a
            # dependency since. Re-checking here is what made a superseded state
            # unreadable by every command.
            session.record_execution_result(payload, owner, submitted=False)
        elif event_type == EVENT_EXECUTION_ITEM:
            session.record_execution_item(owner or _owning_node(session, payload.item_id,
                                                                "execution item"), payload)
        elif event_type == EVENT_CHECK:
            session.record_check_result(owner or _owning_node(session, payload.check_id,
                                                             "acceptance check"), payload)
        elif event_type == EVENT_NODE_CLOSED:
            session.complete_node(payload)
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
    _spec_check(workflow_document)
    state = SessionState(
        task=_load_json(args.task, "task"),
        workflow=workflow_document,
    )
    workflow = state.workflow_object()
    # Semantic validation belongs to `start`, which every entry point goes through.
    # Calling it here too ran it twice on the same document -- measured at 79 ms for
    # a 3001-node tree, so cheap, but it made this function's contract ambiguous
    # about which layer owns the check. `supersede` keeps its own call for a
    # different reason: it mutates the state before `start` runs, so a document that
    # fails validation there would leave the state already written.
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
            "route": workflow.route.value if workflow.route else None,
            "revision_id": workflow.revision_id,
            "nodes": list(workflow.stage_paths),
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
    _spec_check(workflow_document)
    replacement = workflow_from_dict(workflow_document)
    # Before `state.supersede` below, not merely before `start`: the replacement is
    # written into the state, so a document that fails validation afterwards would
    # already have replaced a working revision.
    validate_tree_structure(replacement)

    if state.has_progress and not replacement.supersedes_workflow_id:
        raise SessionStateError(
            "a replacement revision must name the revision it replaces; "
            f"set supersedes_workflow_id to {previous.revision_id!r}"
        )

    carried = state.carried_over_nodes(workflow_document)
    touched_before = set(state.side_effect_nodes)

    reason = args.reason or "the Agent authored a replacement revision"
    carried = state.supersede(workflow_document, reason)
    session = AcceptanceGuide().start(task_from_dict(state.task, "task"), replacement)
    state.save(path)

    # A node is at risk when its calls already ran against a live host and its
    # definition changed, so the earlier proof no longer covers it and re-running
    # it would repeat a host change.
    at_risk = tuple(
        path
        for path in replacement.stage_paths
        if path not in carried and path in touched_before
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
                path
                for path, _node in replacement.nodes
                if path not in carried
            ],
            "side_effects_at_risk": list(at_risk),
            "archived_events": len(state.revisions[-1]["events"]) if state.revisions else 0,
            "revision_count": len(state.revisions),
            "nodes": list(replacement.stage_paths),
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
    document = _load_json(args.result, "result")
    result = execution_result_from_dict(document, "result")
    announce("call_id", result.call_id)

    # A call id is scoped to the STAGE that declares it, so two subtrees may each
    # declare a "build". The node may be named here or in the submission; when it
    # is neither, the id must be unique or the engine refuses rather than guessing.
    declared = document.get("node_path") if isinstance(document, dict) else None
    named = str(declared or args.stage) if (declared or args.stage) else None
    try:
        node_path = state.workflow_object().resolve_call_path(result.call_id, named)
    except ValueError as exc:
        raise SessionStateError(str(exc)) from exc
    announce("node_path", node_path)

    if not args.confirm_side_effects:
        # The repeat is a repeat of *this node's* call. The same id in a different
        # node is a different host change, which is the whole point of scoping a
        # call id to its STAGE.
        already_run = state.calls_already_run()
        revision = already_run.get((node_path, result.call_id))
        if revision is not None:
            raise SessionStateError(
                f"call {result.call_id} at {node_path} has already run against a live "
                f"host (revision {revision}); reporting a new result for it could apply "
                "the same change twice. Pass --confirm-side-effects to proceed, or "
                "author a replacement revision"
            )

    # One rebuild, one check, one apply -- in that order. Checking against a
    # throwaway replay rebuilt the session twice for a single append, and appending
    # before checking would validate a submission the state already carries. The
    # ordering check belongs to accepting a submission, so it runs on the session as
    # it stands, before the event exists.
    session = replay(state)
    session.check_call_ready(result.call_id, node_path)

    body = result.to_dict()
    body["node_path"] = node_path
    state.append(EVENT_EXECUTION_RESULT, body)
    # `submitted=False`: the event has already been checked above, and replaying it
    # must not re-litigate an order that was valid when it was taken in.
    session.record_execution_result(result, node_path, submitted=False)
    state.save(Path(args.state))

    payload = envelope(
        "record",
        verdict=verdict_for_task_status(result.status),
        detail={"call_id": result.call_id, "node_path": node_path,
                "status": result.status.value},
        errors=result.errors,
    )
    return payload, payload["exit_code"]


def _declaring_node(args: argparse.Namespace, session: AcceptanceSession,
                    declared_id: str, what: str) -> str:
    """Resolve which node an item or check submission belongs to.

    The submission may name the node itself, or ``--stage`` may, and only then is a
    bare id resolved by search -- and only when exactly one node declares it.
    """

    document = _load_json(args.result, "result")
    declared = document.get("node_path") if isinstance(document, dict) else None
    named = declared or getattr(args, "stage", None)
    if named:
        return str(named)
    return _owning_node(session, declared_id, what)


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
    owning = _declaring_node(args, session, item.item_id, "execution item")
    announce("node_path", owning)

    body = item.to_dict()
    body["node_path"] = owning
    state.append(EVENT_EXECUTION_ITEM, body)
    # Apply to the session already built above rather than rebuilding it: the
    # declaration lookup needed a session, but the append does not invalidate it.
    session.record_execution_item(owning, item)
    state.save(Path(args.state))

    payload = envelope(
        "item",
        verdict=verdict_for_check_status(item.status),
        detail={
            "item_id": item.item_id,
            "status": item.status.value,
            "node_path": owning,
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
    owning = _declaring_node(args, session, check.check_id, "acceptance check")
    announce("node_path", owning)

    body = check.to_dict()
    body["node_path"] = owning
    state.append(EVENT_CHECK, body)
    # Same as `item`: the session that resolved the owning node is still current.
    session.record_check_result(owning, check)
    state.save(Path(args.state))

    payload = envelope(
        "check",
        verdict=verdict_for_check_status(check.status),
        detail={
            "check_id": check.check_id,
            "status": check.status.value,
            "node_path": owning,
        },
        errors=(check.reason,) if check.reason else (),
    )
    return payload, payload["exit_code"]


def command_stage(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Evaluate one node against its frozen checklists and close it.

    ``--stage`` names a node by **path**, because a ``node_id`` is unique only among
    siblings and so cannot name one node on its own. The path may address a STAGE or
    a composite: closing a composite judges its whole subtree and reports the
    roll-up.

    Closing a node is idempotent: asking again returns the verdict already recorded.
    The hazard of a repeated host change is guarded where the call is reported, not
    here -- see `command_record`.
    """

    state = SessionState.load(Path(args.state))
    session = replay(state)

    path = args.stage
    closed_before = path in state.closed_nodes
    result = session.complete_node(path)
    if result.status in CLOSED_STATUSES and not closed_before:
        state.append(EVENT_NODE_CLOSED, {"node_path": path})
    state.save(Path(args.state))

    detail = result.to_dict()
    detail["side_effects_recorded"] = session.has_side_effects(path)
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
    closed = set(session.completed_node_paths)

    payload = envelope(
        "status",
        verdict=verdict_for_task_status(result.status),
        detail={
            "state": str(args.state),
            "ready": session.ready,
            "revision_id": session.workflow.revision_id,
            "revision_count": len(state.revisions),
            "completed_calls": list(session.completed_call_ids),
            "completed_nodes": list(session.completed_node_paths),
            "remaining_nodes": [
                path
                for path in session.workflow.stage_paths
                if path in session.workflow.required_paths and path not in closed
            ],
            "blocked_reasons": list(session.gate.blocked_reasons),
            "workflow": _workflow_summary(session, state),
        },
        errors=session.gate.blocked_reasons,
    )
    return payload, payload["exit_code"]


def _workflow_summary(session: AcceptanceSession, state: SessionState) -> dict[str, Any]:
    """Describe the bound Workflow: its identity, its nodes, and what each needs.

    Enough for the Agent to act without opening the Workflow file again: which node
    is closed, which calls it declared, and which checks must be proven. Every node
    is listed, not only the leaves, because a composite is closeable too and its
    verdict is the one its parent reads.
    """

    closed = set(session.completed_node_paths)
    touched = set(session.nodes_with_side_effects)
    return {
        "workflow_id": session.workflow.workflow_id,
        "revision": session.workflow.revision,
        "guidance": session.workflow.guidance,
        "route": session.workflow.route.value if session.workflow.route else None,
        "supersedes_workflow_id": session.workflow.supersedes_workflow_id,
        "replaced": [
            entry.get("revision_id")
            for entry in state.revisions
        ],
        "nodes": [
            {
                "node_path": path,
                "node_id": node.node_id,
                "kind": node.kind.value,
                "purpose": node.purpose,
                "required": node.required,
                "closed": path in closed,
                "side_effects_recorded": path in touched,
                "calls": [
                    {"call_id": call.call_id, "target": call.target.to_dict()}
                    for call in node.declared_calls
                ],
                "execution_checklist": [
                    {"item_id": item.item_id, "required": item.required}
                    for item in (node.stage.execution_checklist if node.stage else ())
                ],
                "acceptance_checklist": [
                    {"check_id": wrapper.check_id,
                     "operator": wrapper.check.operator.value,
                     "required": wrapper.check.required}
                    for wrapper in node.declared_checks
                ],
            }
            for path, node in session.workflow.nodes
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
    parser.add_argument(
        "--stage",
        help="node PATH (required by 'stage'; optional for item/check, to name the "
             "node when a bare item or check id is declared more than once)",
    )
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
    except (
        SessionStateError,
        SkillIntegrityError,
        WorkflowDeserializationError,
        TreeIntegrityError,
        WorkflowError,
    ) as exc:
        payload, code = unusable(args.command, str(exc), context=_CONTEXT)
    except Exception as exc:  # noqa: BLE001 - see below
        # The contract is that every invocation prints one JSON envelope. An
        # unexpected exception must still honour it: a traceback on stdout leaves
        # a caller with nothing to parse and no way to tell a bug from bad input.
        # The type is reported so the failure stays diagnosable.
        payload, code = unusable(
            args.command,
            f"unexpected {type(exc).__name__}: {exc}",
            context=_CONTEXT,
        )
    emit(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
