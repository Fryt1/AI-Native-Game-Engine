"""Durable session state for the Agent-driven acceptance loop.

Each CLI invocation is a separate process, so the loop needs a state file. The
state is *only* what the Agent submitted, in the order it submitted it: the task,
the current Workflow revision, an ordered event log of evidence, and the
revisions this one replaced.

The order matters. A call may not be recorded before the node it depends on has
closed, so replaying a flat set of results would re-trigger dependency failures
the Agent already satisfied. Keeping one chronological log makes replay faithful
to what actually happened.

**Every event names the node it belongs to, by path.** A ``node_id`` is unique
only among siblings, so an event carrying a bare id could not be attributed to one
node once two subtrees declare the same name. The path is stored rather than
re-derived for the same reason.

A Workflow revision is immutable. When the Agent replaces it, the old revision and
the evidence recorded against it move to `revisions` rather than being discarded:
that history is the audit trail of what was actually attempted.

@see ainative.cli.commands for the command surface.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ainative.model.tree import WorkflowTree
from ainative.reading.deserialize import (
    check_result_from_dict,
    execution_item_result_from_dict,
    execution_result_from_dict,
    workflow_from_dict,
)

STATE_VERSION = 1

EVENT_EXECUTION_RESULT = "execution_result"
EVENT_EXECUTION_ITEM = "execution_item"
EVENT_CHECK = "check"
EVENT_NODE_CLOSED = "node_closed"


class SessionStateError(RuntimeError):
    """The session state file cannot be read or written."""


@dataclass(slots=True)
class SessionState:
    """The current Workflow revision plus the evidence submitted against it."""

    task: dict[str, Any]
    workflow: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)
    revisions: list[dict[str, Any]] = field(default_factory=list)

    def append(self, event_type: str, payload: dict[str, Any]) -> None:
        """Append one submitted evidence event.

        @param event_type: one of the ``EVENT_*`` constants.
        @param payload: the event body, which must carry ``node_path`` for every
            type except a raw call result (attributed through its call id).
        """

        self.events.append({"type": event_type, "payload": payload})

    @property
    def closed_nodes(self) -> list[str]:
        """Return the node paths the Agent has closed, in order."""

        return [
            str(event["payload"]["node_path"])
            for event in self.events
            if event.get("type") == EVENT_NODE_CLOSED
        ]

    @property
    def has_progress(self) -> bool:
        """True once the Agent has recorded anything or replaced a revision.

        `open` refuses to overwrite a state that has progress, because doing so
        would silently discard evidence. Replacing a Workflow is `supersede`.
        """

        return bool(self.events or self.revisions)

    def supersede(self, workflow: dict[str, Any], reason: str) -> tuple[str, ...]:
        """Replace the current revision, archiving the old one and its evidence.

        A node whose definition is unchanged carries forward, and so do the events
        recorded against it: the new revision declares the same work with the same
        proof, so the earlier verdict still means something. Every other event is
        archived, because its call ids belong to a node that no longer exists in
        the same form.

        @param workflow: the replacement Workflow document.
        @param reason: why the previous revision was abandoned.
        @returns the node paths that carried forward.
        """

        carried = set(self.carried_over_nodes(workflow))
        archived, forwarded = self._split_events(workflow, carried)

        self.revisions.append({
            "workflow": self.workflow,
            "events": archived,
            "revision_id": self.current_revision_id,
            "reason": reason,
            "superseded_by": revision_id_of(workflow),
            "carried_over": sorted(carried),
            "side_effect_nodes": list(_nodes_with_side_effects(self.workflow, archived)),
        })
        self.workflow = workflow
        self.events = forwarded
        return tuple(sorted(carried))

    def _split_events(
        self,
        workflow: dict[str, Any],
        carried: set[str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Split the event log into what is archived and what carries forward.

        Events are attributed to a node by the *new* revision's declarations: a
        call event belongs to whichever node declares that call id, and the other
        kinds carry their own node path. Events belonging to a carried-over node
        carry forward; everything else is archived.

        @param workflow: the replacement Workflow document.
        @param carried: node paths whose definition is unchanged.
        @returns the archived events and the events that carry forward.
        """

        replacement = _read_workflow(workflow)
        if replacement is None:
            return list(self.events), []

        def owning_node(payload: dict[str, Any], event_type: str) -> str | None:
            if event_type == EVENT_NODE_CLOSED:
                return str(payload.get("node_path", "")) or None
            declared = payload.get("node_path")
            if declared:
                return str(declared)
            call_id = payload.get("call_id")
            return replacement.path_of_call(str(call_id)) if call_id else None

        archived: list[dict[str, Any]] = []
        forwarded: list[dict[str, Any]] = []
        for event in self.events:
            payload = event.get("payload", {})
            owner = owning_node(payload, str(event.get("type", "")))
            (forwarded if owner in carried else archived).append(event)
        return archived, forwarded

    def carried_over_nodes(self, workflow: dict[str, Any]) -> tuple[str, ...]:
        """Return the node paths whose definition is unchanged since a prior revision.

        A node carries over only when an earlier revision declared a node at the
        same path *and* with the same content fingerprint. The same path is not
        enough: if the goal, the checklists, or the calls changed, the old verdict
        says nothing about the new node.
        """

        candidate = _read_workflow(workflow)
        if candidate is None:
            return ()

        previous: dict[str, str] = {}
        for entry in [*self.revisions, {"workflow": self.workflow, "events": self.events}]:
            document = _read_workflow(entry["workflow"])
            if document is None:
                continue
            previous.update(document.fingerprints())

        current = candidate.fingerprints()
        return tuple(
            path for path, fingerprint in current.items()
            if previous.get(path) == fingerprint
        )

    def calls_already_run(self) -> dict[tuple[str, str], tuple[str, str]]:
        """Return, per ``(node path, call id)``, the revision that ran it and what it did.

        Keyed by the pair, not by the call id alone. A call id is scoped to the
        STAGE that declares it -- two sibling towers may each declare a ``build``
        -- so keying by the bare id would refuse the second tower's perfectly
        distinct host change. It is the same call in the same node that is a
        repeat, and only that.

        Includes every revision, current and archived, because a call that ran once
        has already touched the host even if the revision carrying it was later
        replaced. An archived event that predates ``node_path`` is resolved through
        its own revision's Workflow; when that is ambiguous the path is left empty,
        which fails closed rather than open.

        The second element is the CALL DIGEST as declared when the call ran: its
        target and arguments, which is what the host saw. The repeat guard compares
        it against the call's digest now, because a call whose declaration changed
        is a different host change however familiar its id looks. Without this, an
        Agent that fixed a broken call and re-ran it was refused as a repeat and had
        no way forward but a manual override.

        @returns a mapping of ``(node path, call id)`` to ``(revision id, digest)``.
        """

        recorded: dict[tuple[str, str], tuple[str, str]] = {}

        def collect(workflow_document: Any, events: list[dict[str, Any]], label: str) -> None:
            workflow = _read_workflow(workflow_document)
            for event in events:
                if event.get("type") != EVENT_EXECUTION_RESULT:
                    continue
                payload = event.get("payload")
                if not isinstance(payload, dict) or not payload.get("call_id"):
                    continue
                call_id = str(payload["call_id"])
                node_path = payload.get("node_path")
                if not node_path and workflow is not None:
                    node_path = workflow.path_of_call(call_id)
                recorded.setdefault(
                    (str(node_path or ""), call_id),
                    (label, _declared_digest(workflow, call_id, node_path)),
                )

        for entry in self.revisions:
            collect(entry.get("workflow"), entry.get("events", []),
                    str(entry.get("revision_id") or "archived"))
        collect(self.workflow, self.events, str(self.current_revision_id or "current"))
        return recorded

    @property
    def side_effect_nodes(self) -> tuple[str, ...]:
        """Return every node, across all revisions, that has touched the world.

        A node is listed once any of its calls was recorded. Python cannot see the
        host, so it cannot know whether the edit landed; what it knows is that the
        call ran against a live host. Re-running such a node is not the same as
        running it the first time.
        """

        seen: list[str] = []
        for revision_id, nodes in self._side_effects_by_revision().items():
            if revision_id is None:
                continue
            for path in nodes:
                if path not in seen:
                    seen.append(path)
        return tuple(seen)

    def _side_effects_by_revision(self) -> dict[str | None, tuple[str, ...]]:
        """Return the nodes that recorded calls, per revision id."""

        result: dict[str | None, tuple[str, ...]] = {
            self.current_revision_id: _nodes_with_side_effects(self.workflow, self.events)
        }
        for entry in self.revisions:
            result[entry.get("revision_id")] = _nodes_with_side_effects(
                entry["workflow"], entry.get("events", [])
            )
        return result

    @property
    def current_revision_id(self) -> str | None:
        """Return the current revision's id, or None when it cannot be read."""

        try:
            return workflow_from_dict(self.workflow).revision_id
        except Exception:  # noqa: BLE001 - only used for reporting
            return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": STATE_VERSION,
            "task": self.task,
            "workflow": self.workflow,
            "revisions": self.revisions,
            "events": self.events,
        }

    @classmethod
    def from_dict(cls, document: Any) -> SessionState:
        """Read a state document.

        @param document: the parsed JSON state.
        @returns the state.
        @throws SessionStateError when the document is not a valid state file.
        """

        if not isinstance(document, dict):
            raise SessionStateError("state file must contain an object")
        if document.get("version") != STATE_VERSION:
            raise SessionStateError(f"unsupported state version: {document.get('version')!r}")
        for key in ("task", "workflow"):
            if not isinstance(document.get(key), dict):
                raise SessionStateError(f"state file is missing '{key}'")
        events = document.get("events", [])
        if not isinstance(events, list):
            raise SessionStateError("state file 'events' must be a list")
        for index, event in enumerate(events):
            if not isinstance(event, dict) or "type" not in event or not isinstance(event.get("payload"), dict):
                raise SessionStateError(f"state file events[{index}] is malformed")
        revisions = document.get("revisions", [])
        if not isinstance(revisions, list):
            raise SessionStateError("state file 'revisions' must be a list")
        for index, entry in enumerate(revisions):
            if not isinstance(entry, dict) or not isinstance(entry.get("workflow"), dict):
                raise SessionStateError(f"state file revisions[{index}] is malformed")
        return cls(
            task=document["task"],
            workflow=document["workflow"],
            events=list(events),
            revisions=list(revisions),
        )

    @classmethod
    def load(cls, path: Path) -> SessionState:
        """Read a state file from disk."""

        if not path.is_file():
            raise SessionStateError(f"session state does not exist: {path}")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SessionStateError(f"session state is not valid JSON: {exc}") from exc
        return cls.from_dict(document)

    def save(self, path: Path) -> None:
        """Write this state to disk atomically."""

        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def workflow_object(self) -> WorkflowTree:
        """Return the stored Workflow as a framework contract."""

        return workflow_from_dict(self.workflow)

    def event_objects(self) -> list[tuple[str, Any, str | None]]:
        """Return the event log as typed contracts, in submitted order.

        @returns triples of event type, typed payload, and the node path the event
            belongs to (None for a raw call result, which is attributed through
            its call id). The path is carried alongside rather than inside the
            typed payload because the payload types are the Agent's submission
            format and do not carry engine bookkeeping.
        @throws SessionStateError when an event payload cannot be read.
        """

        typed: list[tuple[str, Any, str | None]] = []
        for index, event in enumerate(self.events):
            event_type = event["type"]
            payload = event["payload"]
            path = f"events[{index}].payload"
            declared = payload.get("node_path")
            owner = str(declared) if declared else None
            if event_type == EVENT_EXECUTION_RESULT:
                typed.append((event_type, execution_result_from_dict(payload, path), owner))
            elif event_type == EVENT_EXECUTION_ITEM:
                typed.append((event_type, execution_item_result_from_dict(payload, path), owner))
            elif event_type == EVENT_CHECK:
                typed.append((event_type, check_result_from_dict(payload, path), owner))
            elif event_type == EVENT_NODE_CLOSED:
                typed.append((event_type, str(payload["node_path"]), owner))
            else:
                raise SessionStateError(f"unknown event type at events[{index}]: {event_type!r}")
        return typed


def revision_id_of(workflow_document: dict[str, Any]) -> str | None:
    """Return a Workflow document's revision id, or None when it cannot be read."""

    workflow = _read_workflow(workflow_document)
    return workflow.revision_id if workflow is not None else None


def _read_workflow(document: Any) -> WorkflowTree | None:
    """Read a Workflow document, or None when it cannot be read.

    Used only for reporting and comparison, never for validation: a state file
    that holds an unreadable archived revision should still load, because the
    evidence for the current revision is unaffected.
    """

    if not isinstance(document, dict):
        return None
    try:
        return workflow_from_dict(document)
    except Exception:  # noqa: BLE001 - reported as None, not raised
        return None


def _declared_digest(workflow: WorkflowTree | None, call_id: str, node_path: Any) -> str:
    """Return how the revision DECLARED a call, as a digest of what it would do.

    Read from the revision that recorded the call, not from the current one: the
    question is what the host saw when the call ran.

    An empty string means "no declaration could be read". The guard treats that as
    a difference, so a call whose declaration cannot be established is reported
    again only when the Agent says so -- failing closed, because the alternative is
    applying a host change twice on the strength of a document that would not parse.
    """

    if workflow is None:
        return ""
    node = workflow.node_at(str(node_path)) if node_path else None
    if node is None:
        return ""
    declared = next(
        (call for call in node.declared_calls if call.call_id == call_id), None)
    return declared.digest if declared is not None else ""


def _nodes_with_side_effects(
    workflow_document: dict[str, Any],
    events: list[dict[str, Any]],
) -> tuple[str, ...]:
    """Return the node paths that recorded a call, in declaration order.

    A node is included once any call it declares appears in the event log. The
    call ran against a live host, so the node may already have changed it.
    """

    workflow = _read_workflow(workflow_document)
    if workflow is None:
        return ()

    recorded = {
        str(event["payload"]["call_id"])
        for event in events
        if event.get("type") == EVENT_EXECUTION_RESULT
        and isinstance(event.get("payload"), dict)
        and "call_id" in event["payload"]
    }
    return tuple(
        path
        for path, node in workflow.stages
        if any(call.call_id in recorded for call in node.declared_calls)
    )
