"""Validate a reusable Workflow Definition package before execution or promotion."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkflowReport:
    ok: bool
    workflow_root: str
    missing: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()


def validate_workflow(root: Path) -> WorkflowReport:
    required = ("WORKFLOW.md", "plan.template.yaml", "requirements.yaml")
    missing = tuple(name for name in required if not (root / name).is_file())
    issues: list[str] = []
    plan = root / "plan.template.yaml"
    if plan.is_file():
        text = plan.read_text(encoding="utf-8")
        if "calls:" not in text:
            issues.append("plan.template.yaml must declare Stage calls")
        if "kind: tool" not in text and "kind: mcp" not in text:
            issues.append("plan.template.yaml must contain at least one ToolCall or McpCall")
        if "tool_call" in text:
            issues.append("plan.template.yaml contains the removed tool_call contract")
    requirements = root / "requirements.yaml"
    if requirements.is_file() and "requires:" not in requirements.read_text(encoding="utf-8"):
        issues.append("requirements.yaml must declare requires")
    return WorkflowReport(
        ok=not missing and not issues,
        workflow_root=str(root),
        missing=missing,
        issues=tuple(issues),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workflow_root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = validate_workflow(args.workflow_root.resolve())
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print("OK" if report.ok else "INVALID: " + "; ".join((*report.missing, *report.issues)))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
