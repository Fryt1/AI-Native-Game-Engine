import pytest

from ainative.orchestration.contracts import (
    BlenderCallSurface,
    ProfileName,
    TaskContract,
    TaskRoute,
    TransferBackendKind,
)
from ainative.orchestration.planning import UnsupportedProfile, select_workflow


def test_workflow_selection_returns_context_without_steps_or_tools():
    task = TaskContract(
        task_id="native-1",
        objective="Modify a Blender mesh",
        route=TaskRoute.HOST_OPERATION,
    )

    selection = select_workflow(task)

    assert selection.route is TaskRoute.HOST_OPERATION
    assert selection.profile == ProfileName.DEFAULT.value
    assert selection.authority_id == "host-operation"
    assert selection.transfer_backend is None
    assert selection.blender_call_surface is BlenderCallSurface.CLI_PYTHON
    assert selection.modification_method == "native_host_operation"


def test_cross_host_selection_chooses_assetsbridge_for_preservation():
    task = TaskContract(
        task_id="roundtrip-1",
        objective="Edit a UE5 mesh and return it to the source asset",
        route=TaskRoute.ASSET_TRANSFER,
        direction="ue5_to_blender_to_ue5",
        preserve_relations=frozenset({"asset_identity", "material_slots", "transform"}),
    )

    selection = select_workflow(task)

    assert selection.transfer_backend is TransferBackendKind.ASSETSBRIDGE
    assert selection.blender_call_surface is BlenderCallSurface.ADDON
    assert selection.modification_method == "assetsbridge_compatible_asset_edit"


def test_direct_transfer_selection_keeps_explicit_loss_policy():
    task = TaskContract(
        task_id="direct-1",
        objective="Send a mesh file to UE5",
        route=TaskRoute.ASSET_TRANSFER,
        preferred_backend=TransferBackendKind.DIRECT,
        acceptable_loss=frozenset({"asset_identity"}),
        preserve_relations=frozenset({"asset_identity"}),
    )

    selection = select_workflow(task)

    assert selection.transfer_backend is TransferBackendKind.DIRECT
    assert selection.blender_call_surface is BlenderCallSurface.CLI_PYTHON
    assert selection.modification_method == "direct_transfer_safe_asset_edit"


def test_unknown_profile_is_rejected_before_agent_plan_is_authored():
    task = TaskContract(
        task_id="bad-profile",
        objective="Modify a Blender mesh",
        route=TaskRoute.HOST_OPERATION,
        profile="unsupported",
    )

    with pytest.raises(UnsupportedProfile):
        select_workflow(task)


def test_selection_targets_ue5_without_constructing_stages():
    task = TaskContract(
        task_id="ue5-object-1",
        objective="Move an Actor in a UE5 level",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
        metadata={"operation": "set-actor-transform"},
    )

    selection = select_workflow(task)

    assert selection.host_app == "ue5"
    assert selection.host_call_surface == "ue5-python"
    assert selection.blender_call_surface is None


def test_level_template_selection_only_selects_the_workflow_document():
    task = TaskContract(
        task_id="ue5-level-template",
        objective="Create a UE5 Level from the default template",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
        metadata={
            "operation": "create_level_from_template",
            "template": "/Engine/Maps/Templates/Template_Default",
            "target": "/Game/DefaultLightingLevel",
        },
    )

    selection = select_workflow(task)

    assert selection.workflow_id == "host-operation"
    assert selection.host_call_surface == "ue5-python"
    assert not hasattr(selection, "steps")
