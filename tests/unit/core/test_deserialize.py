import json

import pytest

from ainative.reading.deserialize import (
    WorkflowDeserializationError,
    execution_result_from_dict,
    workflow_from_dict,
)


def _plan_document() -> dict:
    return {
        "guidance": "asset-roundtrip",
        "route": "asset_transfer",
                "workflow_id": "p:workflow",
        "steps": [
            {
                "step_id": "validate",
                "purpose": "Validate",
                "stages": [
                    {
                        "stage_id": "stage.validate_asset",
                        "purpose": "Validate",
                        "operation": "validate",
                        "stage_kind": "change",
                        "calls": [
                            {
                                "call_id": "v1",
                                "target": {"owner": "blender", "name": "read_scene"},
                            }
                        ],
                        "execution_checklist": [
                            {"item_id": "run-validator", "description": "run", "call_ids": ["v1"]}
                        ],
                        "acceptance_checklist": [
                            {
                                "check_id": "relations-proven",
                                "description": "proven",
                                "operator": "truthy",
                                "source_call_id": "v1",
                                "actual_path": ["preserved_relations"],
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_plan_round_trips_through_json():
    workflow = workflow_from_dict(_plan_document())

    assert workflow.guidance == "asset-roundtrip"
    assert workflow.route.value == "asset_transfer"
    stage = workflow.stage_requests[0]
    assert stage.stage_id == "stage.validate_asset"
    assert stage.calls[0].target.owner == "blender"
    assert stage.calls[0].target.name == "read_scene"
    assert stage.execution_checklist[0].item_id == "run-validator"
    assert stage.acceptance_checklist[0].actual_path == ("preserved_relations",)
    assert stage.acceptance_checklist[0].operator.value == "truthy"


def test_plan_serializes_back_to_an_equivalent_document():
    workflow = workflow_from_dict(_plan_document())

    assert workflow.to_dict()["steps"][0]["stages"][0]["acceptance_checklist"][0]["check_id"] == "relations-proven"


def test_a_plan_wrapped_in_workflow_is_accepted():
    workflow = workflow_from_dict({"workflow": _plan_document()})

    assert workflow.guidance == "asset-roundtrip"


def test_missing_required_field_names_the_json_path():
    document = _plan_document()
    del document["steps"][0]["stages"][0]["calls"][0]["target"]

    with pytest.raises(WorkflowDeserializationError, match="target"):
        workflow_from_dict(document)


def test_unknown_enum_value_lists_the_allowed_values():
    document = _plan_document()
    document["route"] = "not_a_route"

    with pytest.raises(WorkflowDeserializationError, match="is not one of"):
        workflow_from_dict(document)


def test_stage_kind_enum_is_enforced():
    document = _plan_document()
    document["steps"][0]["stages"][0]["stage_kind"] = "sideways"

    with pytest.raises(WorkflowDeserializationError, match="stage_kind"):
        workflow_from_dict(document)


def test_non_object_plan_is_rejected():
    with pytest.raises(WorkflowDeserializationError, match="expected an object"):
        workflow_from_dict([])


def test_execution_result_carries_relations_as_evidence():
    result = execution_result_from_dict(
        {
            "call_id": "v1",
            "status": "succeeded",
            "preserved_relations": ["asset_identity"],
            "lost_relations": ["material_slots"],
        },
        "result",
    )

    assert result.status.value == "succeeded"
    assert result.preserved_relations == frozenset({"asset_identity"})

    view = result.evidence_view()
    assert view["preserved_relations"] == ["asset_identity"]
    assert view["lost_relations"] == ["material_slots"]
    assert view["status"] == "succeeded"


def test_execution_result_evidence_view_exposes_tool_outputs():
    result = execution_result_from_dict(
        {"call_id": "v1", "status": "succeeded", "outputs": {"actor": "Cube"}},
        "result",
    )

    assert result.evidence_view()["actor"] == "Cube"


def test_execution_result_requires_a_status():
    with pytest.raises(WorkflowDeserializationError, match="missing required field 'status'"):
        execution_result_from_dict({"call_id": "v1"}, "result")


def test_execution_result_rejects_a_non_object_outputs_field():
    with pytest.raises(WorkflowDeserializationError, match="outputs"):
        execution_result_from_dict(
            {"call_id": "v1", "status": "succeeded", "outputs": ["not", "an", "object"]},
            "result",
        )


def test_serialized_plan_is_valid_json():
    workflow = workflow_from_dict(_plan_document())

    assert json.loads(json.dumps(workflow.to_dict()))["guidance"] == "asset-roundtrip"
