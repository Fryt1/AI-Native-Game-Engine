from ainative.model import TaskContract, TaskRoute
from ainative.session_api import AcceptanceGuide


def test_a_task_without_guidance_verifies_the_package_and_reads_no_document():
    task = TaskContract(
        task_id="agent-task",
        objective="Edit a UE5 mesh in Blender and return it",
        route=TaskRoute.ASSET_TRANSFER,
        direction="ue5_to_blender_to_ue5",
        source_context={"app": "ue5"},
        target_context={"app": "ue5"},
    )

    session = AcceptanceGuide().load_skill(task)

    assert session.skill_id == "ai-native-game-engine"
    assert session.route is TaskRoute.ASSET_TRANSFER
    assert session.guidance is None
    assert session.guidance_document is None


def test_a_named_guidance_document_is_resolved():
    """The Agent names the guidance; there is no whitelist to satisfy."""

    task = TaskContract(
        task_id="named-guidance",
        objective="Round-trip a mesh",
        route=TaskRoute.ASSET_TRANSFER,
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
        route=TaskRoute.ASSET_TRANSFER,
        guidance="does-not-exist",
    )

    import pytest

    from ainative.session_api import SkillIntegrityError

    with pytest.raises(SkillIntegrityError, match="named guidance does not exist"):
        AcceptanceGuide().load_skill(task)


def test_route_names_are_canonical():
    assert TaskRoute.HOST_OPERATION.value == "host_operation"
    assert TaskRoute.ASSET_TRANSFER.value == "asset_transfer"
    assert TaskRoute.ARTIFACT_PIPELINE.value == "artifact_pipeline"
