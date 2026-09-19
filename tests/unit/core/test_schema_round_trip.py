"""A document written to the schema must reach the model intact.

The schema is what an AI reads and what an author follows. The model is what the
engine evaluates. A field the schema declares but the model cannot see is worse
than a missing field: the document passes every check and then silently reads
nothing.

This caught exactly that: ``source_node`` is a property on a node check in the
schema, but the model read it out of ``metadata``, so a composite's descendant
reference never arrived.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ainative.acceptance.tree_evaluator import evaluate_tree
from ainative.model.results import ExecutionResult, TaskStatus
from ainative.model.tools import CallTarget
from ainative.model.tree import NodeKind, walk
from ainative.reading.deserialize import workflow_from_dict
from ainative.reading.schema import is_valid, load_schema
from ainative.reading.tree_validate import validate_tree_structure

SCHEMA = Path("templates/workflow.schema.json")


@pytest.fixture(scope="module")
def schema() -> dict:
    return load_schema(SCHEMA)


def document() -> dict:
    """A two-level tree written the way the schema describes it."""

    return {
        "workflow_id": "probe",
        "root": {
            "node_id": "city",
            "kind": "workflow",
            "purpose": "the city",
            "children": [
                {
                    "node_id": "buildings",
                    "kind": "workflow",
                    "purpose": "every building",
                    "children": [
                        {
                            "node_id": "mass",
                            "kind": "stage",
                            "purpose": "build the mass",
                            "stage": {
                                "calls": [{
                                    "call_id": "build",
                                    "target": {"owner": "blender",
                                               "name": "execute_blender_code"},
                                }],
                                "execution_checklist": [{
                                    "item_id": "built",
                                    "description": "the mass is built",
                                    "call_ids": ["build"],
                                }],
                                "acceptance_checklist": [{
                                    "check_id": "grounded",
                                    "description": "the mass sits on the ground",
                                    "operator": "truthy",
                                    "source_call_id": "build",
                                    "actual_path": ["on_ground"],
                                }],
                            },
                        },
                    ],
                    "acceptance_checklist": [{
                        "check_id": "buildings.built",
                        "description": "the buildings are complete",
                        "operator": "equals",
                        "expected": "pass",
                        "source_node": "mass",
                    }],
                },
            ],
            "acceptance_checklist": [{
                "check_id": "city.complete",
                "description": "the scene is complete",
                "operator": "equals",
                "expected": "pass",
                "source_node": "buildings",
            }],
        },
    }


def test_the_document_conforms_to_the_schema(schema: dict):
    assert is_valid(document(), schema)


def test_the_descendant_reference_survives_the_round_trip(schema: dict):
    """The field the schema declares must be visible to the model."""

    del schema
    tree = workflow_from_dict(document())

    buildings = next(node for path, node in walk(tree.root)
                     if node.node_id == "buildings")
    assert buildings.acceptance_checklist, "the composite kept no check"
    assert buildings.acceptance_checklist[0].source_node == "mass", (
        "the schema declares source_node as a field; the model must read it")

    city = tree.root
    assert city.acceptance_checklist[0].source_node == "buildings"


def test_a_document_written_to_the_schema_validates_and_evaluates():
    """The whole path: schema-conforming document to a verdict."""

    tree = workflow_from_dict(document())
    validate_tree_structure(tree)

    mass = next(path for path, node in walk(tree.root) if node.node_id == "mass")
    results = {
        (mass, "build"): ExecutionResult(
            call_id="build", status=TaskStatus.SUCCEEDED,
            target=CallTarget(owner="blender", name="execute_blender_code"),
            outputs={"on_ground": True}),
    }
    verdict = evaluate_tree(tree, results)

    assert verdict.status.value == "pass", verdict.reason


def test_the_metadata_spelling_also_still_works():
    """A document may put the reference in metadata, which is where it is stored.

    Both spellings must agree; the schema's is the documented one, and this pins
    the storage spelling so a change to either is caught.
    """

    payload = document()
    check = payload["root"]["children"][0]["acceptance_checklist"][0]
    check.pop("source_node")
    check["metadata"] = {"source_node": "mass"}

    tree = workflow_from_dict(payload)
    buildings = next(node for path, node in walk(tree.root)
                     if node.node_id == "buildings")

    assert buildings.acceptance_checklist[0].source_node == "mass"


def test_a_missing_source_node_is_caught_by_the_validator_not_ignored():
    """A composite check with no descendant must fail loudly."""

    payload = document()
    payload["root"]["children"][0]["acceptance_checklist"][0].pop("source_node")

    tree = workflow_from_dict(payload)
    with pytest.raises(Exception) as caught:
        validate_tree_structure(tree)
    assert "source_node" in str(caught.value)


def test_the_model_does_not_drop_a_field_the_schema_requires(schema: dict):
    """A required field the model drops is silent, which is the whole hazard.

    The document passes every check and the engine reads nothing, so the failure
    shows up later as a wrong verdict rather than as an error. ``source_node`` was
    the defect this was written for; ``route`` was an earlier one, since removed
    from the schema entirely.

    This reads ``schema['required']`` rather than naming fields, so adding a
    required field to the spec extends this test instead of needing a new one.
    """

    rebuilt = workflow_from_dict(document()).to_dict()
    dropped = [name for name in schema.get("required", ()) if name not in rebuilt]

    assert not dropped, (
        f"the model dropped schema-required field(s) {dropped}; a document that "
        "conforms to the spec must not lose anything on the way in")


def test_the_model_emits_documents_the_schema_accepts(schema: dict):
    """The direction nothing guarded.

    ``test_the_model_does_not_drop_a_field_the_schema_requires`` guards one way
    round: a field the schema requires must survive the model. Nothing guarded the
    other -- a field the MODEL emits that the schema forbids. Injecting
    ``"priority": 7`` into ``WorkflowTree.to_dict()`` passed all 355 tests, which
    means the engine could start emitting documents its own ``open`` refuses, since
    the schema closes every object with ``additionalProperties: false``.

    One document is enough to bind it: a field added anywhere in ``to_dict`` has to
    appear on a node this document contains, and an unknown key is rejected
    wherever it appears.
    """

    tree = workflow_from_dict(document())

    assert is_valid(tree.to_dict(), schema), (
        "the model emitted a document the spec rejects: "
        f"{tree.to_dict()}")


def test_a_stage_node_keeps_its_kind_through_the_round_trip():
    tree = workflow_from_dict(document())
    kinds = {node.node_id: node.kind for _path, node in walk(tree.root)}

    assert kinds["city"] is NodeKind.WORKFLOW
    assert kinds["buildings"] is NodeKind.WORKFLOW
    assert kinds["mass"] is NodeKind.STAGE


def test_a_stages_checks_live_in_its_body_and_not_on_the_node():
    """Pin the invariant that makes ``declared_checks`` necessary.

    A STAGE's checks are in its ``stage`` body. The node-level list is empty for a
    STAGE -- not an error, just empty -- so any consumer that reads it evaluates
    nothing and reports a pass.
    """

    tree = workflow_from_dict(document())
    mass = next(node for _path, node in walk(tree.root) if node.node_id == "mass")

    assert mass.acceptance_checklist == (), (
        "a STAGE must not mirror its checks onto the node; "
        "if this ever changes, the silent-empty-read hazard is gone and this test "
        "should be replaced rather than deleted")
    assert [check.check_id for check in mass.declared_checks] == ["grounded"]


def test_a_failing_stage_level_check_actually_fails_the_stage():
    """The decisive direction: a dropped check would leave this passing.

    The earlier tests assert a *pass*, which a dropped check also produces. This
    one asserts a *fail*, which only an evaluated check can produce.
    """

    payload = document()
    check = payload["root"]["children"][0]["children"][0]["stage"][
        "acceptance_checklist"][0]
    check["operator"] = "equals"
    check["expected"] = "the mass is not built"

    tree = workflow_from_dict(payload)
    validate_tree_structure(tree)

    mass = next(path for path, node in walk(tree.root) if node.node_id == "mass")
    results = {
        (mass, "build"): ExecutionResult(
            call_id="build", status=TaskStatus.SUCCEEDED,
            target=CallTarget(owner="blender", name="execute_blender_code"),
            outputs={"on_ground": True}),
    }
    verdict = evaluate_tree(tree, results)

    assert verdict.status.value == "fail", (
        "the stage's own check was not evaluated: " + verdict.reason)
