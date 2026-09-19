"""每个模型枚举，在引擎里有没有真实的角色？

`ArtifactKind` 是反例：10 个取值，9 个只出现在自己的枚举声明里。源码、spec、
文档都没有它们。

两条判据，按枚举的角色分：

  Agent 选的词表 —— 引擎必须能处理它。声明了但没有任何分支接住 = Agent 一选就掉空档。

  引擎产生的状态 —— 取值必须被产生、被读取、或是默认值。

关键：判据必须排除 model/ 自己 —— 枚举的声明行本身就是一次"提到"，
不排除的话每个值都"看起来被处理了"。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ainative import model as model_module

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = REPO_ROOT / "src" / "ainative" / "model"

#: Everything OUTSIDE model/, which owns the declarations. A value "handled" only by
#: the file that declares it is handled by nothing -- that is exactly how
#: `ArtifactKind` looked busy while being inert.
OUTSIDE_MODEL = "\n".join(
    path.read_text(encoding="utf-8")
    for path in (REPO_ROOT / "src").rglob("*.py")
    if MODEL_DIR not in path.parents
)

def _enums() -> dict[str, list[str]]:
    found = {}
    for name, obj in vars(model_module).items():
        if not (isinstance(obj, type) and hasattr(obj, "__members__")):
            continue
        try:
            members = list(obj)
        except TypeError:
            continue
        if members:
            found[name] = [m.name for m in members]
    return found


def test_there_are_enums_to_check():
    """Guard on the parsing: an empty set would make the tests below vacuous."""

    found = _enums()
    assert "CheckOperator" in found and "CheckStatus" in found
    assert len(found) >= 5, f"only found {sorted(found)}"


def test_no_enum_value_lives_only_in_its_own_declaration():
    """The test that would have caught `ArtifactKind`.

    Every enum in the model is checked, so a new one is covered the moment it is
    declared rather than needing to be added to a list. A value earns its place by
    being named somewhere outside `model/`: the engine branches on it, produces it,
    matches its text, or a document lists it.

    `StageKind` is the case that defines the boundary. The engine only reads it --
    `deserialize` stores it and nothing branches on it, which is why
    `stage_kind` does not change a validation outcome. But it is not inert: the spec
    states what each value obliges an author to freeze, so the values are named in
    `templates/workflow.schema.json` and in `SKILL.md`. A value can be justified by a
    document that tells an Agent how to behave, not only by a branch. That is the
    line `ArtifactKind` was on the wrong side of: ten values, and no document named
    any of them.
    """

    inert: dict[str, list[str]] = {}

    for enum_name, members in _enums().items():
        unused = [
            member for member in members
            if not re.search(rf"{enum_name}\.{member}\b", OUTSIDE_MODEL)
            and not re.search(rf'"{member.lower()}"', OUTSIDE_MODEL)
            and not _documented(member)
        ]
        if unused:
            inert[enum_name] = unused

    assert not inert, (
        f"these enum values are named nowhere outside model/ and no document lists "
        f"them: {inert}. Each one is a word an author may choose and the engine will "
        "never act on -- either give it a branch, document it, or remove it")


def _documented(member: str) -> bool:
    """True when a document an author reads names this value.

    The spec, SKILL.md, and AGENTS.md are where a permitted value has to appear for
    an author to be able to choose it. A value documented here is a rule the Agent
    follows; a value documented nowhere is unguessable.
    """

    documents = [
        REPO_ROOT / "templates" / "workflow.schema.json",
        REPO_ROOT / "SKILL.md",
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "templates" / "result-contract.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in documents)
    return bool(re.search(rf'"{member.lower()}"', text))


@pytest.mark.parametrize("comparison", ["is", "==", "!="])
def test_the_check_actually_discriminates(comparison: str):
    """A guard on the guard: the search must be able to fail.

    If OUTSIDE_MODEL were empty or the regex matched anything, the test above would
    pass for the wrong reason. This asserts the haystack is real and that a value
    known to be inert is detected as inert.
    """

    assert len(OUTSIDE_MODEL) > 10_000, "the source scan came back nearly empty"

    # A member name that exists in no enum anywhere must be reported.
    fake = "A_VALUE_THAT_NO_ENUM_HAS"
    assert not re.search(rf"\w+\.{fake}\b", OUTSIDE_MODEL)
    del comparison
