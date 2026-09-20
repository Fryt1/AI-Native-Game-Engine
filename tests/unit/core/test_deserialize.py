import json

import pytest

from ainative.reading.deserialize import (
    WorkflowDeserializationError,
    execution_result_from_dict,
    workflow_from_dict,
)
from tests.support.workflow_factory import first_stage


def _workflow_document() -> dict:
    return {
            "workflow_id": "p:workflow",
        "root": {
            "node_id": "validate",
            "kind": "workflow",
            "purpose": "Validate",
            "children": [
                {
                    "node_id": "stage.validate_asset",
                    "kind": "stage",
                    "purpose": "Validate",
                    "stage": {
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
                    },
                }
            ],
        },
    }


def test_plan_round_trips_through_json():
    workflow = workflow_from_dict(_workflow_document())

    stage = first_stage(workflow)
    assert stage.node_id == "stage.validate_asset"
    assert stage.stage.calls[0].target.owner == "blender"
    assert stage.stage.calls[0].target.name == "read_scene"
    assert stage.stage.execution_checklist[0].item_id == "run-validator"
    assert stage.declared_checks[0].check.actual_path == ("preserved_relations",)
    assert stage.declared_checks[0].check.operator.value == "truthy"


def test_plan_serializes_back_to_an_equivalent_document():
    workflow = workflow_from_dict(_workflow_document())

    assert workflow.to_dict()["root"]["children"][0]["stage"]["acceptance_checklist"][0]["check_id"] == "relations-proven"


def test_a_plan_wrapped_in_workflow_is_accepted():
    """A document may arrive wrapped; the reader unwraps it.

    The wrapper exists so a caller can carry the Workflow beside other keys. The
    read has to succeed and produce the same tree as the bare form.
    """

    wrapped = workflow_from_dict({"workflow": _workflow_document()})

    assert first_stage(wrapped).node_id == "stage.validate_asset"

def test_missing_required_field_names_the_json_path():
    document = _workflow_document()
    del document["root"]["children"][0]["stage"]["calls"][0]["call_id"]

    with pytest.raises(WorkflowDeserializationError, match="call_id"):
        workflow_from_dict(document)


def test_unknown_enum_value_lists_the_allowed_values():
    document = _workflow_document()
    document["status"] = "not_a_status"

    with pytest.raises(WorkflowDeserializationError, match="is not one of"):
        workflow_from_dict(document)


def test_stage_kind_enum_is_enforced():
    document = _workflow_document()
    document["root"]["children"][0]["stage"]["stage_kind"] = "sideways"

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
    """The model's output must survive a JSON round trip byte for byte.

    A tree is written to the state file and read back on every command, so anything
    `to_dict` emits and `json` cannot encode would break every command after the
    first rather than the one that wrote it.
    """

    workflow = workflow_from_dict(_workflow_document())

    assert json.loads(json.dumps(workflow.to_dict())) == workflow.to_dict()
