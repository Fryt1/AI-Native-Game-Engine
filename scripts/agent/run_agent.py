"""Inspect Skill guidance; a concrete plan must be supplied by the Agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ainative.agent import WorkflowGuide
from ainative.orchestration.contracts import TaskContract, TaskRoute


def load_task(path: Path) -> TaskContract:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["route"] = TaskRoute(raw["route"])
    if "preserve_relations" in raw:
        raw["preserve_relations"] = frozenset(raw["preserve_relations"])
    if "acceptable_loss" in raw:
        raw["acceptable_loss"] = frozenset(raw["acceptable_loss"])
    return TaskContract(**raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task", type=Path)
    parser.add_argument("--plan-only", action="store_true", help="kept as a readable alias for guidance-only output")
    args = parser.parse_args()
    task = load_task(args.task)
    session = WorkflowGuide().load_skill(task)
    payload = {
        "skill_id": session.skill_id,
        "route": session.selection.route.value,
        "workflow_id": session.selection.workflow_id,
        "profile": session.selection.profile,
        "selection": session.selection.to_dict(),
        "plan": None,
        "plan_owner": "agent",
        "plan_required": True,
        "selection_document": str(session.selection_document),
        "workflow_document": str(session.workflow_document),
        "knowledge_index_document": str(session.knowledge_index_document),
        "plan_template_document": str(session.plan_template_document),
        "plan_schema_document": str(session.plan_schema_document),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
