from ainative.model import TaskContract
from ainative.session_api import AcceptanceGuide


def test_a_task_without_guidance_verifies_the_package_and_reads_no_document():
    task = TaskContract(
        task_id="agent-task",
        objective="Edit a UE5 mesh in Blender and return it",
        direction="ue5_to_blender_to_ue5",
        source_context={"app": "ue5"},
        target_context={"app": "ue5"},
    )

    session = AcceptanceGuide().load_skill(task)

    assert session.skill_id == "ai-native-game-engine"
    assert session.guidance is None
    assert session.guidance_document is None


def test_a_named_guidance_document_is_resolved():
    """The Agent names the guidance; there is no whitelist to satisfy."""

    task = TaskContract(
        task_id="named-guidance",
        objective="Round-trip a mesh",
        guidance="asset-roundtrip",
    )

    session = AcceptanceGuide().load_skill(task)

    assert session.guidance == "asset-roundtrip"
    assert session.guidance_document is not None
    assert session.guidance_document.name == "asset-roundtrip.md"


def test_an_unknown_guidance_name_is_rejected_not_ignored():
    task = TaskContract(
        task_id="bad-guidance",
        objective="Round-trip a mesh",
        guidance="does-not-exist",
    )

    import pytest

    from ainative.session_api import SkillIntegrityError

    with pytest.raises(SkillIntegrityError, match="named guidance does not exist"):
        AcceptanceGuide().load_skill(task)
