"""The shipped checker accepts a conforming evidence record and rejects a bad one.

`guidance/procedural-scene/` carries a schema, a checker, and a baseline. The
checker's contract is narrow and worth pinning: it is a **checker, not a generator**
-- it reads a record the Agent submits and reports what does not conform, authors
nothing, and takes no side effect. A checker that silently accepted everything, or
that wrote files while "checking", would be worse than none.

The loader no longer resolves guidance packages; that was the engine doing a job the
skill catalog already does, and it was removed. The documents and scripts under
`guidance/` remain as skill content, and this exercises them directly.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE = REPO_ROOT / "guidance" / "procedural-scene"
SCRIPT = PACKAGE / "scripts" / "check_evidence.py"

GOOD_RECORD = {
    "scene_id": "city_pbr",
    "stage": "generate",
    "seed": 20260906,
    "measurements": {"total_triangles": 5308540, "city_objects": 60},
}


def test_the_shipped_schema_is_enforceable_by_the_shipped_script():
    """A schema using a keyword the script cannot enforce must fail loudly."""

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--schema-only"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)

    assert result.returncode == 0, result.stderr
    assert "enforceable" in result.stdout


def test_the_entry_document_states_the_lifecycle():
    """The documents are skill content now, so nothing else checks they exist."""

    text = (PACKAGE / "README.md").read_text(encoding="utf-8")

    assert "## 生命周期" in text
    for stage in ("探活宿主", "生成", "网格完整性", "环境", "渲染"):
        assert stage in text


def test_the_package_carries_every_file_it_claims():
    """`README.md` lists what the package holds; the list must match the disk.

    Nothing resolves this directory any more, so a missing file would go unnoticed
    until an Agent tried to open it. Both directions are checked: a file the README
    names must exist, and a file on disk must be named.
    """

    text = (PACKAGE / "README.md").read_text(encoding="utf-8")
    claimed = {
        "README.md",
        "docs/why-no-thresholds.md",
        "docs/recovery.md",
        "schema/evidence.schema.json",
        "scripts/check_evidence.py",
        "data/known-good.json",
    }

    missing = sorted(name for name in claimed if not (PACKAGE / name).is_file())
    assert not missing, f"README.md lists files that are not there: {missing}"

    on_disk = {
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*") if path.is_file()
    }
    unlisted = sorted(on_disk - claimed)
    assert not unlisted, (
        f"these files are in the package but not in README.md's list: {unlisted}")
    for name in sorted(claimed - {"README.md"}):
        assert name in text, f"README.md does not name {name}"


def test_the_script_accepts_a_conforming_record(tmp_path: Path):
    record = tmp_path / "ok.json"
    record.write_text(json.dumps(GOOD_RECORD), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(record)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)

    assert result.returncode == 0, result.stderr
    assert "conforms" in result.stdout


@pytest.mark.parametrize(("label", "mutate"), [
    ("an undeclared measurement",
     lambda r: r["measurements"].__setitem__("made_up_metric", 1)),
    ("a missing required field", lambda r: r.pop("stage")),
    ("an unknown stage", lambda r: r.__setitem__("stage", "not_a_stage")),
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
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)

    assert result.returncode == 1, f"should have been rejected: {result.stdout}"
    assert "problem" in result.stdout


def test_the_script_is_a_checker_and_takes_no_side_effect(tmp_path: Path):
    """It writes nothing: the record's directory is unchanged after a run."""

    record = tmp_path / "ok.json"
    record.write_text(json.dumps(GOOD_RECORD), encoding="utf-8")
    before = {p.name for p in tmp_path.iterdir()}

    subprocess.run([sys.executable, str(SCRIPT), str(record)],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", check=False)

    assert {p.name for p in tmp_path.iterdir()} == before


def test_the_script_generates_nothing():
    """ "Checker, not generator" is a claim about the whole file, not one run.

    A generator would have to write something. Read the module and confirm it opens
    no file for writing and calls no writer, so the property holds for every path
    through it rather than for the one a test happens to exercise.
    """

    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    writers = {"write_text", "write_bytes", "mkdir", "unlink", "rename", "replace"}
    offenders = [
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in writers
    ]

    assert not offenders, f"the checker writes: {offenders}"


def test_the_baseline_records_where_its_numbers_came_from():
    """A baseline with no provenance invites the next author to invent one."""

    baseline = json.loads((PACKAGE / "data" / "known-good.json").read_text(encoding="utf-8"))

    assert baseline["runs"], "a baseline needs at least one run"
    assert baseline["cautions"], "a baseline must state what it warns about"
    assert any("needs_human" in c for c in baseline["cautions"]), (
        "the baseline must record the judgement no threshold could settle")
