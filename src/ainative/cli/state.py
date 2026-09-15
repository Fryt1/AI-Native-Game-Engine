"""Durable session state for the Agent-driven acceptance loop.

Each CLI invocation is a separate process, so the loop needs a state file. The
state is *only* what the Agent submitted, in the order it submitted it: the task,
the Workflow, and an ordered event log of evidence.

The order matters. A call may not be recorded before the Stage it depends on has
closed, so replaying a flat set of results would re-trigger dependency failures
the Agent already satisfied. Keeping one chronological log makes replay faithful
to what actually happened.

@see ainative.cli.commands for the command surface.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ainative.model.workflow import Workflow
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
EVENT_STAGE_CLOSED = "stage_closed"


class SessionStateError(RuntimeError):
    """The session state file cannot be read or written."""


@dataclass(slots=True)
class SessionState:
    """The Workflow plus the ordered evidence an Agent has submitted."""

    task: dict[str, Any]
    workflow: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)

    def append(self, event_type: str, payload: dict[str, Any]) -> None:
        """Append one submitted evidence event.

        @param event_type: one of the ``EVENT_*`` constants.
        @param payload: the event body.
        """

        self.events.append({"type": event_type, "payload": payload})

    @property
    def closed_stages(self) -> list[str]:
        """Return the Stage ids the Agent has closed, in order."""

        return [
            str(event["payload"]["stage_id"])
            for event in self.events
            if event.get("type") == EVENT_STAGE_CLOSED
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": STATE_VERSION,
            "task": self.task,
            "workflow": self.workflow,
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
        return cls(
            task=document["task"],
            workflow=document.get("workflow", document.get("plan")),
            events=list(events),
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

    def workflow_object(self) -> Workflow:
        """Return the stored Workflow as a framework contract."""

        return workflow_from_dict(self.workflow)

    def event_objects(self) -> list[tuple[str, Any]]:
        """Return the event log as typed contracts, in submitted order.

        @returns pairs of event type and its typed payload.
        @throws SessionStateError when an event payload cannot be read.
        """

        typed: list[tuple[str, Any]] = []
        for index, event in enumerate(self.events):
            event_type = event["type"]
            payload = event["payload"]
            path = f"events[{index}].payload"
            if event_type == EVENT_EXECUTION_RESULT:
                typed.append((event_type, execution_result_from_dict(payload, path)))
            elif event_type == EVENT_EXECUTION_ITEM:
                typed.append((event_type, execution_item_result_from_dict(payload, path)))
            elif event_type == EVENT_CHECK:
                typed.append((event_type, check_result_from_dict(payload, path)))
            elif event_type == EVENT_STAGE_CLOSED:
                typed.append((event_type, str(payload["stage_id"])))
            else:
                raise SessionStateError(f"unknown event type at events[{index}]: {event_type!r}")
        return typed
