"""Shared Python definitions for preflight check plugins.

This module is copied onto the plugin subprocess ``sys.path`` so checks can run
without importing the runtime package. The dataclasses here are small and
deliberately duplicated from the CLI surface so the plugin protocol stays
self-contained and importable inside the child process.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    """One deterministic preflight check result."""

    check_id: str
    ok: bool
    found: str = ""
    reason: str = ""


@dataclass(frozen=True, slots=True)
class PreflightReport:
    """Structured preflight result for one Workflow/requirements set."""

    workflow_id: str
    ok: bool
    checks: tuple[CheckOutcome, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def add(self, check: CheckOutcome) -> PreflightReport:
        return PreflightReport(
            workflow_id=self.workflow_id,
            ok=self.ok and check.ok,
            checks=self.checks + (check,),
            warnings=self.warnings,
            errors=self.errors,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "ok": self.ok,
            "checks": [asdict(check) for check in self.checks],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def emit(report: PreflightReport) -> None:
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))


def load_json_input() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw:
        return {}
    return json.loads(raw)