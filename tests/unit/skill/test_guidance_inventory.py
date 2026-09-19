"""`guidance/` 的实际内容、`guidance/index.md`、完整性门，三者必须一致。

`guidance/procedural-scene/` 曾经谁都不认识：不在 index 清单里，不在完整性门里，
也没有任何测试会发现 —— 一份完整的指引，加进去等于没加。
`docs/ADDING_GUIDANCE.md` 第 4 步要求登记两处，但只靠记性。

这三个测试把那一步变成机械的。
"""

from __future__ import annotations

import pathlib
import re

import pytest

from integrity_gate import check_package

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
GUIDANCE = REPO_ROOT / "guidance"
INDEX = GUIDANCE / "index.md"


def _inventory() -> set[str]:
    """`guidance/` 下每一份指引的名字，目录形态带尾斜杠。"""

    return {
        f"{path.name}/" if path.is_dir() else path.name
        for path in GUIDANCE.iterdir()
        if path.name != "index.md"
    }


def _listed() -> set[str]:
    """`index.md` 清单里列出的名字。"""

    text = INDEX.read_text(encoding="utf-8")
    section = text.split("## Guidance", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"^- `([^`]+)`", section, re.MULTILINE))


def test_every_guidance_is_listed_in_the_inventory():
    missing = sorted(_inventory() - _listed())

    assert not missing, (
        f"guidance/ holds {missing} but guidance/index.md does not list them; "
        "docs/ADDING_GUIDANCE.md step 4 requires the inventory to name every one")


def test_the_inventory_names_nothing_that_is_gone():
    stale = sorted(_listed() - _inventory())

    assert not stale, (
        f"guidance/index.md lists {stale}, which guidance/ does not hold")


def test_every_guidance_entry_document_is_required_by_the_integrity_gate():
    """The gate is what stops a prompt asset from silently disappearing.

    A directory needs its ENTRY document named, not the directory: the gate checks
    `is_file()`, so a directory path would never pass.
    """

    checked = set(check_package(REPO_ROOT).checked)
    wanted = {
        f"guidance/{name}README.md" if name.endswith("/") else f"guidance/{name}"
        for name in _inventory()
    }
    wanted.add("guidance/index.md")

    missing = sorted(wanted - checked)

    assert not missing, (
        f"the integrity gate does not require {missing}; an unregistered prompt "
        "asset can be deleted without the gate noticing")


def test_a_directory_guidance_has_an_entry_document():
    """`guidance/<name>/` is read through its entry document, so one must exist."""

    entry_names = ("README.md", "index.md", "SKILL.md", "GUIDANCE.md")

    for name in sorted(_inventory()):
        if not name.endswith("/"):
            continue
        directory = GUIDANCE / name
        present = [entry for entry in entry_names if (directory / entry).is_file()]
        assert present, (
            f"guidance/{name} has no entry document; guidance/index.md names "
            f"{entry_names[0]} first, and index.md's own example lists the accepted "
            f"names as {entry_names}")


@pytest.mark.parametrize("name", ["index.md"])
def test_the_inventory_is_not_empty(name):
    """A guard on the parsing above: an inventory that reads as empty would make
    the first two tests pass vacuously."""

    assert _listed(), "the inventory section parsed as empty"
    assert _inventory(), "guidance/ parsed as empty"
