"""Loading the Skill verifies the package, and nothing else.

`load_skill` used to resolve the guidance a task named: it scanned
`guidance/<name>.md` or `guidance/<name>/`, refused a name that did not exist, and
held an inventory of what a package carried. All of that was removed -- a name the
catalog does not list is a name the model never sees, so the engine was maintaining a
second answer to a question the skill mechanism already answers.

What remains is the integrity gate, which is a fact only this process can observe: a
missing prompt asset would leave an Agent following instructions that are no longer
there.
"""

from __future__ import annotations

import pathlib

import pytest

from ainative.model import TaskContract
from ainative.session_api import AcceptanceGuide, SkillIntegrityError

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def test_loading_verifies_the_package():
    task = TaskContract(
        task_id="agent-task",
        objective="Edit a UE5 mesh in Blender and return it",
        direction="ue5_to_blender_to_ue5",
        source_context={"app": "ue5"},
        target_context={"app": "ue5"},
    )

    session = AcceptanceGuide().load_skill(task)

    assert session.skill_id == "ai-native-game-engine"
    assert session.package_root.is_dir()
    assert session.task is task


def test_a_package_with_a_missing_prompt_asset_is_refused(tmp_path):
    """The gate fails closed, and names what is missing.

    A package that has lost a document is a package whose instructions are gone. The
    error has to say which file, because the caller's next move is to restore it.

    The gate file itself is copied in so the failure comes from the required-file
    list rather than from the gate being absent -- those are different errors and
    only one of them is the subject here.
    """

    import shutil

    from ainative.session_api.skill import AINativeSkill

    shutil.copy2(REPO_ROOT / "integrity_gate.py", tmp_path / "integrity_gate.py")
    task = TaskContract(task_id="t", objective="o")
    guide = AcceptanceGuide(skill=AINativeSkill(package_root=tmp_path))

    with pytest.raises(SkillIntegrityError, match="missing Skill files"):
        guide.load_skill(task)


def test_a_task_no_longer_carries_a_guidance_name():
    """The field is gone, so naming a lifecycle is not a task-level act.

    Asserted rather than assumed: the removal is the point, and a field that came
    back would restore the duplicate inventory with it.
    """

    task = TaskContract(task_id="t", objective="o")

    assert not hasattr(task, "guidance")
    assert not hasattr(task.to_dict(), "guidance")
    assert "guidance" not in task.to_dict()
