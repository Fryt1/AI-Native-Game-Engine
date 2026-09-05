"""Agent-chain tracing: record inputs/outputs across Skill loading, WorkflowPlan,
Stage calls, deterministic acceptance, and final results.

The trace recorder is an optional observer. It does not create or execute any
call; it only serializes structured data that already exists in the runtime.
This keeps the architecture invariant: the Agent owns the plan and the loop,
Python validates/records/aggregates, and nothing here decides the next call.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

TRACE_DIR = Path(os.environ.get("AINATIVE_TRACE_DIR", Path(__file__).resolve().parents[3] / "artifacts" / "traces"))


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


@dataclass(slots=True)
class TraceEvent:
    """One structured event on the Agent chain."""

    run_id: str
    event: str
    timestamp: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "event": self.event,
            "timestamp": self.timestamp,
            "data": self.data,
        }


class AgentTrace:
    """Collects events and writes them to one JSONL file per run.

    Events are appended in call order so a viewer can replay the full chain:
    task -> skill/selection -> plan -> gate -> per-call input/output ->
    checklist results -> StageResult -> TaskResult.
    """

    def __init__(self, run_id: str | None = None, trace_dir: Path | None = None) -> None:
        self.run_id = run_id or f"trace-{uuid.uuid4().hex[:12]}"
        self.trace_dir = Path(trace_dir) if trace_dir else TRACE_DIR
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.trace_dir / f"{self.run_id}.jsonl"
        self._events: list[TraceEvent] = []

    def open(self) -> AgentTrace:
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        return self

    def close(self) -> None:
        pass

    def __enter__(self) -> Self:
        return self.open()

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- recording --

    def emit(self, event: str, **data: Any) -> None:
        record = TraceEvent(self.run_id, event, _now(), data)
        self._events.append(record)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def snapshot(self) -> dict[str, Any]:
        """Return collected events (useful when a session never persists)."""
        return {
            "run_id": self.run_id,
            "path": str(self.path),
            "events": [event.to_dict() for event in self._events],
        }

    # -- convenience event helpers with stable names --

    def record_task(self, task: Any) -> None:
        self.emit("task.input", task=task.to_dict())

    def record_skill(self, session: Any) -> None:
        selection = session.selection.to_dict() if hasattr(session, "selection") else {}
        self.emit(
            "skill.selected",
            skill_id=getattr(session, "skill_id", None),
            package_root=str(getattr(session, "package_root", "")),
            selection=selection,
            selection_document=str(getattr(session, "selection_document", "")),
            workflow_document=str(getattr(session, "workflow_document", "")),
            knowledge_index_document=str(getattr(session, "knowledge_index_document", "")),
            plan_template_document=str(getattr(session, "plan_template_document", "")),
            plan_schema_document=str(getattr(session, "plan_schema_document", "")),
        )

    def record_plan(self, plan: Any) -> None:
        self.emit("plan.input", plan=plan.to_dict())

    def record_gate(self, gate: Any) -> None:
        self.emit(
            "gate.result",
            ready=gate.ready,
            blocked_reasons=list(gate.blocked_reasons),
            warnings=list(gate.warnings),
            next_action=gate.next_action,
        )

    def record_tool_issues(self, issues: tuple[Any, ...]) -> None:
        self.emit("plan.tool_issues", issues=[issue.to_dict() for issue in issues])

    def record_call_input(self, call: Any) -> None:
        self.emit("call.input", call=call.to_dict())

    def record_call_result(self, result: Any) -> None:
        self.emit("call.result", result=result.to_dict())

    def record_checklist(self, event: str, summary: Any) -> None:
        self.emit(event, summary=summary.to_dict())

    def record_stage_result(self, stage: Any) -> None:
        self.emit("stage.result", stage=stage.to_dict())

    def record_task_result(self, result: Any) -> None:
        self.emit("task.result", result=result.to_dict())

    def record_human_input(self, prompt: str, decision: str | None = None) -> None:
        data: dict[str, Any] = {"prompt": prompt}
        if decision is not None:
            data["decision"] = decision
        self.emit("human.input", **data)
