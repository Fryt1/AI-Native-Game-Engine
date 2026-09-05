"""Promote a machine- and human-verified draft into workflows/."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

try:
    from .validate_workflow import validate_workflow
except ImportError:  # direct `python scripts/workflows/promote_workflow.py`
    from validate_workflow import validate_workflow

ROOT = Path(__file__).resolve().parents[2]


def _read_status(path: Path, key: str) -> str | None:
    if not path.is_file():
        return None
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get(key))
    except json.JSONDecodeError:
        return None


def promote_workflow(draft: Path, *, replace: bool = False) -> Path:
    report = validate_workflow(draft)
    if not report.ok:
        raise ValueError("draft is invalid: " + "; ".join((*report.missing, *report.issues)))
    machine_status = _read_status(draft / "verification" / "machine-report.json", "status")
    human_status = _read_status(draft / "verification" / "human-review.json", "status")
    if machine_status != "passed":
        raise ValueError("machine-report.json must contain status=passed")
    if human_status not in {"approved", "not_required"}:
        raise ValueError("human-review.json must contain status=approved or status=not_required")
    destination = ROOT / "workflows" / draft.parent.name
    if destination.exists() and not replace:
        raise FileExistsError(f"published workflow already exists: {destination}")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(draft, destination)
    (destination / "verification" / "publication.json").write_text(
        json.dumps({"status": "published", "source": str(draft)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    print(promote_workflow(args.draft.resolve(), replace=args.replace))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
