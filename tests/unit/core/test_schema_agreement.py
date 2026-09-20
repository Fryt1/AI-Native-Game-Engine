"""The schema and the engine's validator must agree about the same document.

They are two expressions of one definition: the schema is what an author reads and
what an AI generates against, and the validator is what the engine enforces before
a side effect. If they disagree, a document can pass the schema and be rejected by
the engine -- or worse, pass both while breaking a rule neither states.

This checks three things:

1. the schema accepts a document the engine accepts;
2. the schema **rejects** the two addressing defects the engine's validator missed
   (an id containing the path separator, and an absolute ``source_node``);
3. every rule the validator can emit has a schema counterpart, or an explicit note
   saying why it is a semantic rule the schema cannot express.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ainative.model.checklists import (
    AcceptanceCheck,
    CheckOperator,
    ExecutionChecklistItem,
)
from ainative.model.tools import CallTarget, ToolCall
from ainative.model.tree import (
    NodeCheck,
    NodeKind,
    StageBody,
    WorkflowNode,
    WorkflowTree,
)
from ainative.reading.deserialize import workflow_from_dict
from ainative.reading.schema import SchemaError, is_valid, load_schema, validate
from ainative.reading.tree_validate import validate_tree_structure

SCHEMA_PATH = Path("templates/workflow.schema.json")
TARGET = CallTarget(owner="blender", name="execute_blender_code")


@pytest.fixture(scope="module")
def schema() -> dict:
    return load_schema(SCHEMA_PATH)


def stage_document(node_id: str = "mass") -> dict:
    """A minimal well-formed STAGE node as a document."""

    call_id = f"call_{node_id}"
    return {
        "node_id": node_id,
        "kind": "stage",
        "purpose": f"build {node_id}",
        "stage": {
            "calls": [{"call_id": call_id,
                       "target": {"owner": "blender", "name": "execute_blender_code"}}],
            "execution_checklist": [
                {"item_id": f"{node_id}_done", "description": "handled",
                 "call_ids": [call_id]},
            ],
            "acceptance_checklist": [
                {"check_id": f"{node_id}_ok", "description": "proven",
                 "operator": "truthy", "source_call_id": call_id,
                 "actual_path": ["ok"]},
            ],
        },
    }


def workflow_document(root: dict) -> dict:
    return {"workflow_id": "probe", "root": root}


# --------------------------------------------------------------------------- #
# Agreement on a good document
# --------------------------------------------------------------------------- #


def test_the_schema_accepts_a_document_the_validator_accepts(schema):
    """A document both agree on."""

    root = WorkflowNode(
        node_id="city", kind=NodeKind.WORKFLOW, purpose="the city",
        children=(
            stage_node("layout"),
            WorkflowNode(
                node_id="buildings", kind=NodeKind.WORKFLOW, purpose="every building",
                depends_on=("../layout",),
                children=(stage_node("mass"),),
                acceptance_checklist=(composite_check("built", "mass"),),
            ),
        ),
    )
    validate_tree_structure(WorkflowTree(workflow_id="probe", root=root))

    document = workflow_document({
        "node_id": "city", "kind": "workflow", "purpose": "the city",
        "children": [
            stage_document("layout"),
            {
                "node_id": "buildings", "kind": "workflow",
                "purpose": "every building", "depends_on": ["layout"],
                "children": [stage_document("mass")],
                "acceptance_checklist": [
                    {"check_id": "built", "description": "built",
                     "operator": "equals", "expected": "pass", "source_node": "mass"}],
            },
        ],
    })
    validate(document, schema)


def stage_node(node_id: str, *, depends_on: tuple[str, ...] = ()) -> WorkflowNode:
    call_id = f"call_{node_id}"
    return WorkflowNode(
        node_id=node_id, kind=NodeKind.STAGE, purpose=f"build {node_id}",
        depends_on=depends_on,
        stage=StageBody(
            calls=(ToolCall(call_id, TARGET),),
            execution_checklist=(ExecutionChecklistItem(
                f"{node_id}_done", "handled", call_ids=(call_id,)),),
            acceptance_checklist=(NodeCheck(AcceptanceCheck(
                f"{node_id}_ok", "proven", operator=CheckOperator.TRUTHY,
                source_call_id=call_id, actual_path=("ok",))),),
        ),
    )


def composite_check(check_id: str, source_node: str) -> NodeCheck:
    """A composite check compares one descendant's verdict with ``equals``."""

    return NodeCheck(AcceptanceCheck(
        check_id, "proven", operator=CheckOperator.EQUALS, expected="pass",
        metadata={"source_node": source_node}))


# --------------------------------------------------------------------------- #
# The two defects the validator missed
# --------------------------------------------------------------------------- #


def test_the_schema_rejects_a_node_id_containing_the_path_separator(schema):
    """Defect 1: ``a/b`` produces a path ``walk`` emits but ``resolve`` cannot reach.

    The engine's validator accepted this. The schema's ``nodeId`` pattern rejects
    it, so the definition is stricter than the enforcement was -- which is the
    direction that matters: the schema is what an author reads.
    """

    document = workflow_document({
        "node_id": "city", "kind": "workflow", "purpose": "the city",
        "children": [
            {"node_id": "a/b", "kind": "workflow", "purpose": "sneaky",
             "children": [stage_document("x")]},
        ],
    })
    assert not is_valid(document, schema)
    with pytest.raises(SchemaError) as caught:
        validate(document, schema)
    # The message must name the id, not just say every alternative failed: an
    # author told "matched 0 alternatives" goes looking at the node kind.
    assert "node_id" in str(caught.value), str(caught.value)
    assert "does not match" in str(caught.value), str(caught.value)


def test_the_schema_rejects_an_absolute_source_node(schema):
    """Defect 2: a leading '/' resolves relatively and means different nodes."""

    document = workflow_document({
        "node_id": "city", "kind": "workflow", "purpose": "the city",
        "children": [stage_document("mass")],
        "acceptance_checklist": [
            {"check_id": "reads", "description": "reads", "operator": "equals",
             "expected": "pass", "source_node": "/mass"},
        ],
    })
    assert not is_valid(document, schema)


@pytest.mark.parametrize("bad_id", ["a/b", "a:b", "a b", "", "a" * 65])
def test_the_schema_rejects_ids_that_break_addressing(schema, bad_id):
    """Every id form that would make the path convention ambiguous.

    ``a.b`` was on this list and is not any more. The hazard is the path
    separator: a path is built by joining ids with ``/``, so an id containing
    ``/`` produces a path that ``walk()`` emits and ``resolve()`` cannot reach.
    Nothing parses ``.`` out of a path, so banning it was a convention, not a
    requirement -- and it forbade ids the rest of the suite naturally writes.
    """

    document = workflow_document({
        "node_id": "city", "kind": "workflow", "purpose": "the city",
        "children": [stage_document("x")],
    })
    document["root"]["children"][0]["node_id"] = bad_id
    assert not is_valid(document, schema), f"{bad_id!r} should be rejected"


def test_the_schema_accepts_a_dotted_id_because_nothing_parses_it(schema):
    """The other half of the rule above, pinned so the relaxation is deliberate."""

    document = workflow_document({
        "node_id": "city", "kind": "workflow", "purpose": "the city",
        "children": [stage_document("stage.mass")],
    })

    assert is_valid(document, schema)

    tree = workflow_from_dict(document)
    node = tree.node_at("/stage.mass/")
    assert node is not None, "a dotted id must still resolve through its path"


# --------------------------------------------------------------------------- #
# The schema must accept what the validator accepts, on well-formed input
# --------------------------------------------------------------------------- #


def test_the_schema_accepts_every_well_formed_shape_the_engine_builds(schema):
    """A deeper, wider document with every optional field present."""

    document = {
        "workflow_id": "probe",
        "revision": 1,
        "warnings": ["a warning carried from the node invariants"],
        "root": {
            "node_id": "city", "kind": "workflow", "purpose": "the city",
            "required": True,
            "metadata": {"seed": 7},
            "children": [
                {
                    "node_id": "buildings", "kind": "workflow",
                    "purpose": "buildings",
                    "children": [
                        {
                            "node_id": "wing", "kind": "workflow", "purpose": "wing",
                            "children": [stage_document("mass")],
                            "acceptance_checklist": [
                                {"check_id": "wing_built", "description": "built",
                                 "operator": "equals", "expected": "pass",
                                 "source_node": "mass"}],
                        },
                    ],
                    "acceptance_checklist": [
                        {"check_id": "all_built", "description": "built",
                         "operator": "equals", "expected": "pass",
                         "source_node": "wing/mass"},
                    ],
                },
                {
                    "node_id": "render", "kind": "stage", "purpose": "render",
                    "depends_on": ["buildings"],
                    "stage": {
                        "calls": [{
                            "call_id": "render_stills",
                            "target": {"owner": "blender",
                                       "name": "execute_blender_code"},
                            "arguments": {"width": 1920},
                        }],
                        "execution_checklist": [
                            {"item_id": "rendered", "description": "rendered",
                             "call_ids": ["render_stills"], "required": True},
                        ],
                        "acceptance_checklist": [
                            {"check_id": "wide_enough", "description": "width",
                             "operator": "within_tolerance",
                             "source_call_id": "render_stills",
                             "actual_path": ["width"], "expected": 1920,
                             "tolerance": 8},
                        ],
                    },
                },
            ],
        },
    }
    validate(document, schema)


# --------------------------------------------------------------------------- #
# Schema/validator rule correspondence
# --------------------------------------------------------------------------- #


#: Rules the validator emits that the schema cannot express, with the reason. Every
#: rule it emits must appear here or be enforced structurally by the schema, so
#: adding a rule on one side forces a decision on the other.
#:
#: C1, C2, N1 and N2 are absent because the schema enforces them structurally:
#: `additionalProperties: false` plus `oneOf` on `kind` means a stage node cannot
#: carry `children`, a workflow node cannot carry `stage`, and each check type
#: accepts only its own source field. The validator re-checks them so the engine
#: fails closed even if a document bypasses the schema.
SEMANTIC_ONLY_RULES = {
    "N3": "conditional on 'required': an optional node may omit checklists",
    "N4": "a composite needs children; the schema requires the key but permits []",
    "N5": "depends_on must name a sibling; the schema cannot see sibling sets",
    "N6": "dependency cycles need a graph walk",
    "C3": "source_node must resolve to a descendant; needs the tree",
    "V1": "every call must support a checklist item; a cross-field rule",
    "V2": "references must resolve to declared calls; a cross-field rule",
    "V3": "within_tolerance needs a tolerance; conditional on the operator",
    "V5": "actual_path must not be empty for a reading operator; conditional on "
          "the operator, which needs if/then the checker does not implement",
}

#: Rules enforced by the schema's own structure, listed so the correspondence is
#: explicit rather than implied by the validator's re-checking them.
STRUCTURALLY_ENFORCED = {
    "C1": "a stage check cannot carry source_node: callCheck closes its properties",
    "C2": "a workflow check cannot carry source_call_id: nodeCheck has no such need",
    "C4": "a composite observes a verdict word: nodeCheck pins its operator to equals/manual",
    "N1": "a stage node cannot have children: stageNode closes its properties",
    "N2": "a workflow node cannot carry a stage body: workflowNode closes its own",
}


def test_schema_and_validator_rule_sets_are_accounted_for():
    """Every validator rule is either schema-enforced or declared semantic-only."""

    import re

    source = Path("src/ainative/reading/tree_validate.py").read_text(encoding="utf-8")
    emitted: set[str] = set()
    for match in re.finditer(r"TreeIssue\(", source):
        hit = re.search(r"[\"']([A-Z]\d+)[\"']", source[match.end():match.end() + 400])
        if hit:
            emitted.add(hit.group(1))

    assert emitted, "no rules discovered; the discovery pattern is wrong"

    unaccounted = sorted(emitted - set(SEMANTIC_ONLY_RULES)
                         - set(STRUCTURALLY_ENFORCED))
    assert not unaccounted, (
        f"these validator rules are neither enforced by the schema nor listed as "
        f"semantic-only: {unaccounted}. Decide which side owns each one.")


@pytest.mark.parametrize(("rule", "document"), [
    (
        "C1: a stage check carrying source_node",
        workflow_document({
            "node_id": "city", "kind": "workflow", "purpose": "city",
            "children": [{
                **stage_document("mass"),
                "stage": {
                    **stage_document("mass")["stage"],
                    "acceptance_checklist": [
                        {"check_id": "k", "description": "d", "operator": "truthy",
                         "source_call_id": "call_mass", "source_node": "mass"}],
                },
            }],
        }),
    ),
    (
        "C2: a workflow check carrying source_call_id",
        workflow_document({
            "node_id": "city", "kind": "workflow", "purpose": "city",
            "children": [stage_document("mass")],
            "acceptance_checklist": [
                {"check_id": "k", "description": "d", "operator": "equals",
                 "expected": "pass", "source_call_id": "call_mass"}],
        }),
    ),
    (
        "N1: a stage node with children",
        workflow_document({
            "node_id": "city", "kind": "workflow", "purpose": "city",
            "children": [{**stage_document("mass"),
                          "children": [stage_document("x")]}],
        }),
    ),
    (
        "N2: a workflow node carrying a stage body",
        workflow_document({
            "node_id": "city", "kind": "workflow", "purpose": "city",
            "children": [stage_document("mass")],
            "stage": stage_document("mass")["stage"],
        }),
    ),
])
def test_the_schema_structurally_enforces_the_kind_rules(schema, rule, document):
    """C1, C2, N1 and N2 are enforced by the schema's shape, not by a check.

    Asserting this rather than claiming it: if `additionalProperties` were relaxed
    or the `oneOf` branches overlapped, the schema would stop enforcing these and
    only the engine's validator would catch them.
    """

    del rule
    assert not is_valid(document, schema)


def test_the_schema_confines_a_composite_check_to_a_verdict_operator(schema):
    """C4 is enforced by ``nodeCheck``'s own operator enum, not by prose.

    A composite observes exactly one descendant's verdict -- a single word. Only
    ``equals`` can compare it and only ``manual`` observes nothing, so every other
    operator is an accidental constant: ``truthy`` on a verdict word always passes.
    If the enum were relaxed, a document would pass the schema and then be rejected
    by the engine.
    """

    document = workflow_document({
        "node_id": "city", "kind": "workflow", "purpose": "city",
        "children": [stage_document("mass")],
        "acceptance_checklist": [
            {"check_id": "built", "description": "built", "operator": "truthy",
             "source_node": "mass"}],
    })

    assert not is_valid(document, schema)


def test_the_schema_enforces_the_id_rules_the_validator_does_not():
    """The schema is deliberately stricter on id shape than the validator was.

    This records the gap rather than hiding it: the validator accepts these, so a
    document can reach the engine with an id that breaks path addressing. Until the
    validator is fixed, the schema is the only place the rule lives.
    """

    sneaky = WorkflowTree(workflow_id="probe", root=WorkflowNode(
        node_id="city", kind=NodeKind.WORKFLOW, purpose="city",
        children=(WorkflowNode(node_id="a/b", kind=NodeKind.WORKFLOW, purpose="ab",
                               children=(stage_node("x"),)),),
    ))
    # The validator accepts it: that is the gap, asserted so it cannot be forgotten.
    validate_tree_structure(sneaky)

    document = json.loads(json.dumps(sneaky.to_dict()))
    assert not is_valid(document, load_schema(SCHEMA_PATH)), (
        "the schema must reject what the validator wrongly accepts")


def test_the_field_an_evidence_error_names_is_one_a_document_mentions():
    """A result document has no schema, so the error is the only pointer to it.

    The Workflow schema describes the Workflow, not the results submitted against
    it, so nothing in the spec can tell an author that a submitted result carries
    `evidence_refs`. That field decides whether a manual item or check can pass at
    all -- and its absence is reported one command LATER, so the author has no
    other signal to follow. The error text has to name it, and a document has to
    name it too, or the method has a dead end in it.
    """

    import re

    from ainative.acceptance.evaluator import require_check_evidence
    from ainative.model.checklists import (
        AcceptanceCheck,
        CheckOperator,
        CheckResult,
        CheckStatus,
    )

    check = AcceptanceCheck(check_id="signed", description="a human signed off",
                            operator=CheckOperator.MANUAL, evidence_required=True)
    downgraded = require_check_evidence(
        check, CheckResult(check_id="signed", status=CheckStatus.PASS))

    assert downgraded.status is CheckStatus.UNKNOWN, (
        "a pass with no evidence must not stand")
    assert "evidence_refs" in downgraded.reason, (
        f"the author is not told which field to fill: {downgraded.reason!r}")

    root = Path(__file__).resolve().parents[3]
    documents = [
        path for path in root.rglob("*.md")
        if not any(part.startswith(".") or part in {"__pycache__", "artifacts"}
                   for part in path.relative_to(root).parts)
    ]
    mentioned = [path.relative_to(root).as_posix() for path in documents
                 if re.search(r"\bevidence_refs\b", path.read_text(encoding="utf-8"))]

    assert mentioned, (
        "no document names `evidence_refs`, and no result document has a schema, "
        "so the field the error demands is undiscoverable")


def test_a_constraint_beside_a_ref_is_rejected_not_silently_dropped(tmp_path):
    """``_resolve`` returns the ``$ref`` target and discards every sibling.

    A sibling annotation loses nothing. A sibling *constraint* would stop being
    enforced while the spec still read as if it were -- the same silent no-op as
    a field the model drops, one layer down.
    """

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": {"verdict": {"enum": ["pass", "fail"]}},
        "type": "object",
        "properties": {"result": {"$ref": "#/$defs/verdict", "maxLength": 4}},
    }
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(schema), encoding="utf-8")

    with pytest.raises(ValueError) as caught:
        load_schema(path)

    assert "maxLength" in str(caught.value)


def test_an_annotation_beside_a_ref_loads_and_the_reference_is_still_enforced(tmp_path):
    """The shipped spec relies on this: ``expected`` carries both.

    Annotations being allowed is only safe if the reference itself is not being
    skipped, so this asserts both halves.
    """

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": {"verdict": {"enum": ["pass", "fail"]}},
        "type": "object",
        "properties": {"result": {"$ref": "#/$defs/verdict",
                                  "description": "explains itself to a reader"}},
    }
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(schema), encoding="utf-8")

    loaded = load_schema(path)

    assert is_valid({"result": "pass"}, loaded)
    assert not is_valid({"result": "succeeded"}, loaded), (
        "the $ref must still constrain; only the annotation may be discarded")
