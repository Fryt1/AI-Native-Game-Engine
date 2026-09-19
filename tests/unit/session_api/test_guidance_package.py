"""Guidance may be a directory, not only a document.

Prose is the floor, not the ceiling. A domain skill may hold scripts, schemas, data
and templates beside its documents, and the loader must resolve either form under
one name so a lifecycle can be promoted from a document to a package without
changing how a task refers to it.

These tests build both forms in a temporary package and check the loader picks the
right one, reads the right entry, and lists what the package carries.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ainative.model.task import TaskContract
from ainative.session_api.skill import (
    ENTRY_NAMES,
    AINativeSkill,
    SkillIntegrityError,
)


def build_package(root: Path, guidance: dict[str, object]) -> Path:
    """Create a minimal Skill package whose guidance entries are as given.

    ``guidance`` maps a name to either a string (a single document's body) or a
    dict of relative path -> body (a directory).
    """

    (root / "guidance").mkdir(parents=True, exist_ok=True)
    for name, content in guidance.items():
        if isinstance(content, str):
            (root / "guidance" / f"{name}.md").write_text(content, encoding="utf-8")
            continue
        base = root / "guidance" / name
        for relative, body in content.items():
            target = base / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
    return root


@pytest.fixture
def package(tmp_path: Path) -> Path:
    """A package whose guidance comes in both forms."""

    # A gate that always passes: these tests are about guidance resolution.
    (tmp_path / "integrity_gate.py").write_text(
        "from dataclasses import dataclass\n"
        "@dataclass\nclass IntegrityReport:\n"
        "    ok: bool = True\n"
        "    package_root: str = ''\n"
        "    missing: tuple = ()\n"
        "    checked: tuple = ()\n"
        "def check_package(package_root):\n"
        "    return IntegrityReport()\n",
        encoding="utf-8",
    )
    return build_package(tmp_path, {
        "document-only": "# A lifecycle\n\nProse only.\n",
        "rich-skill": {
            "README.md": "# A rich domain skill\n\nRead me first.\n",
            "docs/lifecycle.md": "The lifecycle in detail.\n",
            "scripts/check.py": "print('a helper the Agent may run')\n",
            "schemas/params.json": json.dumps({"type": "object"}),
            "data/table.csv": "a,b\n1,2\n",
        },
        "no-entry": {"notes/anything.md": "no entry document here\n"},
    })


def task(guidance: str | None) -> TaskContract:
    return TaskContract(
        task_id="t", objective="o", guidance=guidance)


def skill(package: Path) -> AINativeSkill:
    return AINativeSkill(package_root=package)


# --------------------------------------------------------------------------- #
# Both forms resolve under one name
# --------------------------------------------------------------------------- #


def test_a_single_document_resolves_as_before(package: Path):
    session = skill(package).load(task("document-only"))

    assert session.guidance_package is not None
    assert session.guidance_package.is_directory is False
    assert session.guidance_document == package / "guidance" / "document-only.md"
    assert "Prose only" in session.guidance_package.read_entry()


def test_a_directory_resolves_using_its_entry_document(package: Path):
    session = skill(package).load(task("rich-skill"))
    resolved = session.guidance_package

    assert resolved is not None
    assert resolved.is_directory is True
    assert resolved.entry.name in ENTRY_NAMES
    assert resolved.entry.name == "README.md"
    assert "Read me first" in resolved.read_entry()


def test_a_directory_reports_everything_it_carries(package: Path):
    """The Agent must be able to find a script or a schema without the loader
    understanding any of them."""

    resolved = skill(package).resolve_guidance("rich-skill")[0]
    inventory = resolved.describe()

    assert inventory["form"] == "directory"
    assert set(inventory["files"]) == {
        "README.md", "docs/lifecycle.md", "scripts/check.py",
        "schemas/params.json", "data/table.csv",
    }
    assert inventory["directories"] == ["data", "docs", "schemas", "scripts"]


def test_the_entry_is_the_first_of_the_known_names_present(package: Path, tmp_path: Path):
    """Entry selection is by a fixed precedence, not by directory order."""

    root = build_package(tmp_path / "second", {
        "ordered": {"index.md": "index wins over the others\n",
                    "README.md": "readme\n",
                    "SKILL.md": "skill\n"},
    })
    (root / "integrity_gate.py").write_text(
        "from dataclasses import dataclass\n"
        "@dataclass\nclass IntegrityReport:\n"
        "    ok: bool = True\n"
        "    package_root: str = ''\n"
        "    missing: tuple = ()\n"
        "    checked: tuple = ()\n"
        "def check_package(package_root):\n"
        "    return IntegrityReport()\n",
        encoding="utf-8",
    )
    resolved = AINativeSkill(package_root=root).resolve_guidance("ordered")[0]

    expected = next(name for name in ENTRY_NAMES if name in {"index.md", "README.md", "SKILL.md"})
    assert resolved.entry.name == expected


def test_a_directory_without_an_entry_still_resolves_but_warns(package: Path):
    """A skill with no entry point is usable; the Agent is told, because it is
    usually an accident rather than a design."""

    resolved, warnings = skill(package).resolve_guidance("no-entry")

    assert resolved.entry.name == "anything.md"
    assert warnings, "a missing entry document should warn"
    assert "no entry document" in warnings[0]


def test_a_directory_is_preferred_over_a_document_of_the_same_name(
        package: Path, tmp_path: Path):
    """So a lifecycle can be promoted from a document to a package without the
    task changing how it refers to it."""

    (package / "guidance" / "promoted.md").write_text("the old document\n",
                                                      encoding="utf-8")
    promoted = package / "guidance" / "promoted"
    promoted.mkdir()
    (promoted / "README.md").write_text("the new package\n", encoding="utf-8")

    resolved = skill(package).resolve_guidance("promoted")[0]

    assert resolved.is_directory is True
    assert "new package" in resolved.read_entry()
    _ = tmp_path


def test_an_unknown_name_names_both_forms_it_tried(package: Path):
    with pytest.raises(SkillIntegrityError) as caught:
        skill(package).resolve_guidance("does-not-exist")

    message = str(caught.value)
    assert "does-not-exist/" in message and "does-not-exist.md" in message


def test_no_guidance_named_loads_nothing(package: Path):
    session = skill(package).load(task(None))

    assert session.guidance is None
    assert session.guidance_document is None
    assert session.guidance_package is None
    assert session.warnings == ()
