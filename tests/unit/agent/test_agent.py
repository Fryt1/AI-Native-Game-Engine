import pytest

from ainative.agent import WorkflowGuide, WorkflowPlanError
from ainative.orchestration.contracts import TaskContract, TaskRoute


def test_agent_supplies_task_contract_and_guide_only_loads_selected_workflow():
    task = TaskContract(
        task_id="agent-task",
        objective="Edit a UE5 mesh in Blender and return it",
        route=TaskRoute.ASSET_TRANSFER,
        direction="ue5_to_blender_to_ue5",
        source_context={"app": "ue5"},
        target_context={"app": "ue5"},
    )

    session = WorkflowGuide().load_skill(task)

    assert session.skill_id == "ai-native-workflow-orchestration"
    assert session.route is TaskRoute.ASSET_TRANSFER
    assert session.workflow_id == "asset-roundtrip"
    assert session.knowledge_index_document.is_file()
    assert session.plan_template_document.is_file()
    assert session.plan_schema_document.is_file()


def test_workflow_guide_has_no_default_prompt_interpreter():
    guide = WorkflowGuide()

    assert guide.interpreter is None
    with pytest.raises(WorkflowPlanError, match="No Agent-owned IntentInterpreter"):
        guide.task_from_prompt("处理一下这个模型", "intent-ambiguous")


def test_route_names_are_canonical():
    assert TaskRoute.HOST_OPERATION.value == "host_operation"
    assert TaskRoute.ASSET_TRANSFER.value == "asset_transfer"
    assert TaskRoute.ARTIFACT_PIPELINE.value == "artifact_pipeline"
