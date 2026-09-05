"""Create a draft Workflow Definition package."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRAFTS = ROOT / "artifacts" / "scratch" / "workflow-drafts"


def create_workflow(workflow_id: str, revision: str = "r1") -> Path:
    root = DRAFTS / workflow_id / revision
    if root.exists():
        raise FileExistsError(f"workflow draft already exists: {root}")
    root.mkdir(parents=True)
    (root / "WORKFLOW.md").write_text(
        f"# {workflow_id}\n\nDescribe the reusable guidance, invariants, allowed call sources, and recovery policy.\n",
        encoding="utf-8",
    )
    (root / "plan.template.yaml").write_text(
        "version: 1\nworkflow_id: " + workflow_id + "\nsteps: []\n",
        encoding="utf-8",
    )
    (root / "requirements.yaml").write_text(
        "version: 1\nworkflow_id: " + workflow_id + "\nrequires:\n  project_tools: []\n  mcp_tools: []\n",
        encoding="utf-8",
    )
    for name in ("examples", "tests", "verification"):
        (root / name).mkdir()
    return root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workflow_id")
    parser.add_argument("--revision", default="r1")
    args = parser.parse_args()
    print(create_workflow(args.workflow_id, args.revision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
