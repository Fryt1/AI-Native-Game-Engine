from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StageKind(StrEnum):
    """Behavioral mode used to compose and evaluate a dynamic Stage."""

    CHANGE = "change"
    INVESTIGATION = "investigation"
    PLANNING = "planning"


class CheckStatus(StrEnum):
    """Evidence-backed outcome for one execution or acceptance item."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NEEDS_HUMAN = "needs_human"


class CheckOperator(StrEnum):
    """Small deterministic checks; complex checks remain normal Tools."""

    MANUAL = "manual"
    TOOL_SUCCEEDED = "tool_succeeded"
    EXISTS = "exists"
    TRUTHY = "truthy"
    EQUALS = "equals"
    SET_EQUALS = "set_equals"
    COUNT_EQUALS = "count_equals"
    WITHIN_TOLERANCE = "within_tolerance"


@dataclass(frozen=True, slots=True)
class ExecutionChecklistItem:
    """One item that must be handled to avoid omitting Stage work."""

    item_id: str
    description: str
    required: bool = True
    call_ids: tuple[str, ...] = ()
    evidence_required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "description": self.description,
            "required": self.required,
            "call_ids": list(self.call_ids),
            "evidence_required": self.evidence_required,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class AcceptanceCheck:
    """One frozen condition that defines whether a Stage is complete."""

    check_id: str
    description: str
    required: bool = True
    call_ids: tuple[str, ...] = ()
    source_call_id: str | None = None
    actual_path: tuple[str, ...] = ()
    operator: CheckOperator = CheckOperator.MANUAL
    expected: Any = None
    tolerance: float | None = None
    evidence_required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def referenced_call_ids(self) -> tuple[str, ...]:
        ids = list(self.call_ids)
        if self.source_call_id and self.source_call_id not in ids:
            ids.append(self.source_call_id)
        return tuple(ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "description": self.description,
            "required": self.required,
            "call_ids": list(self.call_ids),
            "source_call_id": self.source_call_id,
            "actual_path": list(self.actual_path),
            "operator": self.operator.value,
            "expected": self.expected,
            "tolerance": self.tolerance,
            "evidence_required": self.evidence_required,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class ExecutionItemResult:
    """Structured evidence result for one execution checklist item."""

    item_id: str
    status: CheckStatus
    call_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "status": self.status.value,
            "call_ids": list(self.call_ids),
            "evidence_refs": list(self.evidence_refs),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Structured evidence result for one Stage acceptance condition."""

    check_id: str
    status: CheckStatus
    actual: Any = None
    expected: Any = None
    evidence_refs: tuple[str, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "status": self.status.value,
            "actual": self.actual,
            "expected": self.expected,
            "evidence_refs": list(self.evidence_refs),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ChecklistSummary:
    """Deterministic counts used to decide one Stage outcome."""

    total: int = 0
    required: int = 0
    passed: int = 0
    warned: int = 0
    failed: int = 0
    unknown: int = 0
    needs_human: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "required": self.required,
            "passed": self.passed,
            "warned": self.warned,
            "failed": self.failed,
            "unknown": self.unknown,
            "needs_human": self.needs_human,
        }
