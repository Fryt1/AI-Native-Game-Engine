from ainative.agent import HeuristicIntentInterpreter, WorkflowGuide
from ainative.orchestration.contracts import TaskRoute, TransferBackendKind


def test_heuristic_agent_interpretation_selects_roundtrip_route():
    task = HeuristicIntentInterpreter().interpret("把 UE5 的模型拿到 Blender 修改，保留材质槽和 Transform，回到原资产", "intent-1")

    assert task.route is TaskRoute.ASSET_TRANSFER
    assert task.preserve_relations == frozenset({"asset_identity", "material_slots", "transform"})
    assert task.preferred_backend is None


def test_heuristic_agent_interpretation_can_explicitly_choose_direct():
    task = HeuristicIntentInterpreter().interpret("直接导出 GLB 给 UE5，不需要回原资产", "intent-2")

    assert task.route is TaskRoute.ASSET_TRANSFER
    assert task.preferred_backend is TransferBackendKind.DIRECT


def test_agent_host_loads_skill_without_generating_a_plan():
    agent = WorkflowGuide()
    task = HeuristicIntentInterpreter().interpret("修改 Blender 模型", "intent-3")

    session = agent.load_skill(task)

    assert session.skill_id == "ai-native-workflow-orchestration"
    assert session.route is TaskRoute.HOST_OPERATION
    assert session.workflow_id == "native-blender-operation"
    assert session.knowledge_index_document.is_file()
    assert session.plan_template_document.is_file()
    assert session.plan_schema_document.is_file()
    assert not hasattr(session, "plan")
    assert not hasattr(agent, "run")
    assert not hasattr(agent, "run_prompt")


def test_heuristic_agent_interpretation_routes_ue5_actor_operation_to_host_operation():
    task = HeuristicIntentInterpreter().interpret("把 UE5 里面的 Actor 移动到指定位置", "intent-ue5-object")

    assert task.route is TaskRoute.HOST_OPERATION
    assert task.direction == "none"


def test_heuristic_agent_interpretation_selects_ue5_level_template_operation():
    task = HeuristicIntentInterpreter().interpret("使用 UE5 默认光照模板新建并打开一个关卡", "intent-ue5-level-template")

    assert task.route is TaskRoute.HOST_OPERATION
    assert task.target_context == {"app": "ue5"}
    assert task.metadata["operation"] == "create_level_from_template"
    assert task.metadata["read_operation"] == "inspect_level"


def test_route_names_are_canonical():
    assert TaskRoute.HOST_OPERATION.value == "host_operation"
    assert TaskRoute.ASSET_TRANSFER.value == "asset_transfer"
    assert TaskRoute.ARTIFACT_PIPELINE.value == "artifact_pipeline"
