"""End-to-end: the shipped rich guidance resolves, and its script checks records.

Two things are asserted together because together they are the point of allowing a
guidance directory at all:

1. the loader resolves ``procedural-scene`` as a **directory**, reads its entry
   document, and lists every file it carries;
2. the script that directory ships is a **checker**, not a generator: it accepts a
   conforming record, rejects a non-conforming one, and takes no side effect.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ainative.model.task import TaskContract, TaskRoute
from ainative.session_api.skill import AINativeSkill

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE = REPO_ROOT / "guidance" / "procedural-scene"
SCRIPT = PACKAGE / "scripts" / "check_evidence.py"

GOOD_RECORD = {
    "scene_id": "city_pbr",
    "stage": "generate",
    "seed": 20260906,
    "measurements": {"total_triangles": 5308540, "city_objects": 60},
}


@pytest.fixture(scope="module")
def resolved():
    task = TaskContract(task_id="t", objective="o",
                        route=TaskRoute.HOST_OPERATION,
                        guidance="procedural-scene")
    return AINativeSkill(package_root=REPO_ROOT).load(task).guidance_package


def test_the_rich_guidance_resolves_as_a_directory(resolved):
    assert resolved is not None
    assert resolved.is_directory is True
    assert resolved.entry.name == "README.md"


def test_the_entry_document_states_the_lifecycle(resolved):
    text = resolved.read_entry()

    assert "## 生命周期" in text
    for stage in ("探活宿主", "生成", "网格完整性", "环境", "渲染"):
        assert stage in text


def test_the_package_lists_every_file_it_carries(resolved):
    inventory = resolved.describe()

    assert inventory["form"] == "directory"
    assert set(inventory["files"]) == {
        "README.md",
        "docs/recovery.md",
        "docs/why-no-thresholds.md",
        "schema/evidence.schema.json",
        "scripts/check_evidence.py",
        "data/known-good.json",
    }


def test_the_shipped_schema_is_enforceable_by_the_shipped_script():
    """A schema using a keyword the script cannot enforce must fail loudly."""

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--schema-only"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "enforceable" in result.stdout


def test_the_script_accepts_a_conforming_record(tmp_path: Path):
    record = tmp_path / "ok.json"
    record.write_text(json.dumps(GOOD_RECORD), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(record)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "conforms" in result.stdout


@pytest.mark.parametrize(("label", "mutate"), [
    ("an undeclared measurement",
     lambda r: r["measurements"].__setitem__("made_up_metric", 1)),
    ("a missing required field",
     lambda r: r.pop("stage")),
    ("an unknown stage",
     lambda r: r.__setitem__("stage", "not_a_stage")),
    ("a negative count",
     lambda r: r["measurements"].__setitem__("total_triangles", -1)),
    ("the wrong type",
     lambda r: r["measurements"].__setitem__("city_objects", "sixty")),
    ("coverage missing its total",
     lambda r: r.__setitem__("scan_coverage", {"analysed": 6})),
])
def test_the_script_rejects_a_non_conforming_record(tmp_path: Path, label, mutate):
    del label
    record = json.loads(json.dumps(GOOD_RECORD))
    mutate(record)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(record), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False,
    )

    assert result.returncode == 1, f"should have been rejected: {result.stdout}"
    assert "problem" in result.stdout


def test_the_script_is_a_checker_and_takes_no_side_effect(tmp_path: Path):
    """It writes nothing: the record's directory is unchanged after a run."""

    record = tmp_path / "ok.json"
    record.write_text(json.dumps(GOOD_RECORD), encoding="utf-8")
    before = {p.name for p in tmp_path.iterdir()}

    subprocess.run([sys.executable, str(SCRIPT), str(record)],
                   capture_output=True, text=True, encoding="utf-8", check=False)

    assert {p.name for p in tmp_path.iterdir()} == before


def test_the_baseline_records_where_its_numbers_came_from():
    """A baseline with no provenance invites the next author to invent one."""

    baseline = json.loads((PACKAGE / "data" / "known-good.json").read_text(encoding="utf-8"))

    assert baseline["runs"], "a baseline needs at least one run"
    assert baseline["cautions"], "a baseline must state what it warns about"
    assert any("needs_human" in c for c in baseline["cautions"]), (
        "the baseline must record the judgement no threshold could settle")
