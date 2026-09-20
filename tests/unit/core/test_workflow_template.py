"""The shipped spec and template must stay loadable, and must agree.

`templates/workflow.schema.json` is the definition of the Workflow data structure:
what is allowed, what is required, and what each field means.

`templates/workflow-template.json` is the skeleton an author fills in. It was deleted
once on the reasoning that a template and a schema describe the same thing and two
descriptions drift. They do not describe the same thing -- a schema states constraints
and a template shows the minimal shape that satisfies them, which for a 264-line spec
with dense prose is not something an author can read off. What the two CAN do is
disagree, so the tests below check the template against the schema rather than trusting
either alone.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

from ainative.model.checklists import CheckStatus

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "templates" / "workflow.schema.json"
TEMPLATE_PATH = REPO_ROOT / "templates" / "workflow-template.json"
SKILL = REPO_ROOT / "SKILL.md"

OPERATORS = [
    "manual", "tool_succeeded", "exists", "truthy",
    "equals", "set_equals", "count_equals", "within_tolerance",
]


@pytest.fixture(scope="module")
def schema_text() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def schema(schema_text: str) -> dict:
    return json.loads(schema_text)


@pytest.fixture(scope="module")
def template_text() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def test_the_schema_is_loadable_and_is_json_schema(schema: dict):
    assert schema["$schema"].startswith("https://json-schema.org/")
    assert schema["$id"]
    assert schema["type"] == "object"


def test_the_schema_declares_each_required_top_level_field(schema: dict):
    for field in ("workflow_id", "root"):
        assert field in schema["required"], f"{field} must be required"
        assert field in schema["properties"], f"{field} must be declared"


@pytest.mark.parametrize("operator", OPERATORS)
def test_the_schema_states_every_operator(schema_text: str, operator: str):
    """The Agent picks an operator, so the spec must list them all."""

    assert f'"{operator}"' in schema_text, f"the schema omits the operator {operator!r}"


def test_the_schema_no_longer_declares_a_route(schema: dict, schema_text: str):
    """`route` was a label whose only reader compared it against the task's.

    It was not a behavioral branch: every value contributed the same context, and
    the judgment code never read it. The schema's own description recorded that
    four independent authors split 3-1 on the same task, which is the measurement
    that settled it. Removing the field means a document carrying one now fails the
    spec, which is the point -- an unknown property is rejected, not ignored.
    """

    assert "route" not in schema["properties"]
    assert "route" not in schema["required"]
    assert '"host_operation"' not in schema_text
    assert '"asset_transfer"' not in schema_text
    assert '"artifact_pipeline"' not in schema_text


def test_every_optional_schema_field_can_actually_be_written(schema: dict):
    """A declared field nothing ever writes is a form with no one to fill it in.

    `replacement_reason` was one: in the schema, in the model, read from JSON, and
    emitted by `to_dict` -- but never assigned by any production code. `supersede`
    records why a revision was abandoned in the archived revision's `reason` key
    instead, so the document field was a second spelling of one fact with only one
    of them live. It was removed.

    This checks that every optional top-level field the schema declares is named
    somewhere in `src/` outside the model module -- the reader, the writer, or the
    CLI. A field that appears ONLY in `model/tree.py` (its declaration and its
    `to_dict`) has no producer, which is how `replacement_reason` survived.
    """

    import re

    repo = REPO_ROOT
    sources = {
        path.relative_to(repo).as_posix(): path.read_text(encoding="utf-8")
        for path in (repo / "src").rglob("*.py")
    }

    orphans = []
    for name in schema["properties"]:
        if name in schema["required"]:
            continue
        # Everything outside the model tree, which owns declaration and to_dict.
        outside = "\n".join(
            text for rel, text in sources.items() if "/model/" not in rel)
        if not re.search(rf"\b{name}\b", outside):
            orphans.append(name)

    assert not orphans, (
        f"the schema declares {orphans}, which src/ never names outside the model: "
        "either nothing writes them, or the check needs widening on purpose")


def test_the_schema_states_every_verdict_the_engine_can_return(schema: dict):
    """The words a composite check compares against are the engine's own.

    Two blind authors, given this schema and asked for a composite check, wrote
    ``expected: "succeeded"`` and ``expected: ["building_1", ...]``. The engine
    compares a descendant's :class:`CheckStatus`, so neither can ever pass. A spec
    that leaves the vocabulary out does not merely omit information -- it teaches
    a value that is silently wrong.
    """

    declared = set(schema["$defs"]["verdict"]["enum"])
    actual = {member.value for member in CheckStatus}

    assert declared == actual, (
        f"the spec names {sorted(declared)} but the engine returns {sorted(actual)}")


def test_the_schema_confines_a_composite_check_to_a_verdict(schema: dict):
    """The constraint, not just the prose, has to be there.

    A description alone is advisory: it did not stop either blind author. The
    reference is what makes the schema checker reject the bad value.
    """

    expected = schema["$defs"]["nodeCheck"]["properties"]["expected"]

    assert expected.get("$ref") == "#/$defs/verdict", (
        "a composite check's expected value must be constrained, not just described")
    assert expected.get("description"), "the constraint must also explain itself"


def test_the_schema_keeps_the_two_node_kinds_exclusive(schema: dict):
    """`kind` discriminates, and exactly one branch may match."""

    node = schema["$defs"]["node"]
    assert "oneOf" in node, "the node must be a discriminated union"

    def resolve(branch: dict) -> dict:
        reference = branch.get("$ref")
        if not reference:
            return branch
        target: object = schema
        for segment in reference[2:].split("/"):
            target = target[segment]  # type: ignore[index]
        return target  # type: ignore[return-value]

    kinds = {resolve(b)["properties"]["kind"]["const"] for b in node["oneOf"]}
    assert kinds == {"stage", "workflow"}, kinds


def test_the_schema_pins_the_composite_check_source(schema: dict):
    """A composite reads a descendant, never a call.

    Pinned to null rather than merely unused: allowing a string here would let a
    document carry a call reference the engine can never honour.
    """

    node_check = schema["$defs"]["nodeCheck"]["properties"]
    assert node_check["source_call_id"]["type"] == "null"
    assert "source_node" in node_check


def test_the_schema_forbids_a_separator_in_an_id(schema: dict):
    """A '/' in a node id forges a path that walk emits and resolve cannot reach."""

    pattern = schema["$defs"]["nodeId"]["pattern"]
    assert "/" not in pattern[2:-3], pattern
    assert pattern.startswith("^[") and pattern.endswith("]+$"), pattern


def test_the_schema_carries_no_removed_fields(schema_text: str):
    """Guard against a deleted concept creeping back into the spec.

    ``steps`` and ``stages`` are on this list because the two-level flat model was
    replaced by the recursive node: a return of either name means the old shape is
    back.
    """

    for name in (
        "profile", "authority_id", "validation_items", "input_keys", "output_keys",
        "toolset_id", "tool_id", "server_id", "tool_name", "usage",
        "transfer_backend", "blender_call_surface", "modification_method",
        "host_app", "host_call_surface", "plan_id", "supersedes_plan_id",
        "steps", "stages",
    ):
        assert f'"{name}"' not in schema_text, (
            f"{name} no longer exists in the model; remove it from the spec")


# --------------------------------------------------------------------------- #
# The stability rules
# --------------------------------------------------------------------------- #
#
# These are rules an Agent must follow on every Workflow. They used to live in two
# places: the notes template that explained them, and SKILL.md that the Agent reads
# first. The notes template is gone, so SKILL.md is the single place, and this
# asserts it still carries all of them. Losing one is a regression.

RULES = [
    "freezes an execution checklist and an acceptance",
    "supports at least one execution or acceptance item",
    "never hard-codes a call source",
    "before its first side effect",
    "does not automatically satisfy a semantic",
    "deterministic operators",
    "cannot be converted to",
    "revision is immutable",
]


@pytest.mark.parametrize("rule", RULES)
def test_skill_md_states_every_stability_rule(rule: str):
    text = SKILL.read_text(encoding="utf-8")
    assert rule in text, f"stability rule missing from SKILL.md: {rule!r}"


# --------------------------------------------------------------------------- #
# The template
# --------------------------------------------------------------------------- #
#
# The template's job is to be COPIED. Two ways that goes wrong, and neither is
# visible from the template alone:
#
#   1. it shows a field the spec forbids, or omits one it requires -- every author
#      who copies it inherits the error
#   2. its shape is not actually openable once filled in
#
# So the tests here check it against the spec, and one fills it in and runs the
# engine. The second is the one that matters: `nodeCheck` has no `call_ids`, and the
# first draft of this template had one, which the spec check caught.


def _placeholders(text: str) -> list[str]:
    return re.findall(r"<([^<>]+)>", text)


def test_the_template_is_json(template_text: str):
    json.loads(template_text)


def _every_property(schema: dict) -> set[str]:
    """Every property name the spec declares, at any depth.

    Walking only each `$defs` entry's top-level `properties` misses the ones nested
    inside a `oneOf` branch -- `target.owner` and `target.name` live there -- and the
    check then reports the template as wrong when it is not.
    """

    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                found.update(properties)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    return found


def test_every_property_the_template_shows_exists_in_the_spec(
        schema: dict, template_text: str):
    """A property the spec does not define is rejected by `open`.

    Checked by name against every property the spec declares at any depth: the
    branches differ in what is REQUIRED, not in what they allow, except for the
    composite/leaf split that test_the_template_shows_both_node_kinds covers.
    """

    allowed = _every_property(schema)
    shown = set(re.findall(r'"([a-z_]+)":', template_text))
    unknown = sorted(shown - allowed)
    assert not unknown, (
        f"the template shows properties the spec does not define: {unknown}. "
        "An author copying this produces a document `open` refuses")


def test_the_template_shows_both_node_kinds(schema: dict, template_text: str):
    """A leaf and a composite, because they carry different fields.

    The composite branch has no `stage` and may carry `acceptance_checklist`; the leaf
    has the opposite. A template showing only one teaches half the structure.
    """

    assert '"kind": "workflow"' in template_text
    assert '"kind": "stage"' in template_text
    assert '"children"' in template_text
    assert '"stage"' in template_text


def test_the_template_shows_every_required_field_of_a_stage(schema: dict, template_text: str):
    """`calls`, `execution_checklist`, and `acceptance_checklist` are all required.

    A template that omits one produces a document that is not a stage at all.
    """

    for required in schema["$defs"]["stageBody"]["required"]:
        assert f'"{required}"' in template_text, (
            f"the template omits {required}, which the spec requires of every stage")


def test_the_template_shows_both_kinds_of_execution_item(template_text: str):
    """An item derived from calls, and one only a person can settle.

    `call_ids: []` is how a human judgement enters the record -- the spec says so --
    and an author who never sees the empty form will not know it is legal.
    """

    assert '"call_ids": ["<call-id>"]' in template_text
    assert '"call_ids": []' in template_text


def test_the_template_shows_both_kinds_of_acceptance_check(template_text: str):
    """A deterministic check reading a call, and a manual one awaiting a person."""

    assert '"operator": "equals"' in template_text
    assert '"operator": "manual"' in template_text
    assert '"source_call_id"' in template_text
    assert '"source_node"' in template_text


def test_the_template_uses_only_real_operators(schema: dict, template_text: str):
    """An operator the spec does not define cannot pass any check."""

    operators = set(schema["$defs"]["operator"]["enum"])
    operators |= set(schema["$defs"]["nodeCheck"]["properties"]["operator"]["enum"])

    shown = set(re.findall(r'"operator":\s*"([a-z_]+)"', template_text))
    assert shown <= operators, f"the template shows unknown operators: {shown - operators}"


def test_the_template_carries_no_removed_field(schema_text: str, template_text: str):
    """The template must not resurrect the flat model either."""

    for name in ("steps", "stages", "route", "toolset_id", "server_id", "plan_id"):
        assert f'"{name}"' not in template_text, (
            f"the template still shows {name}, which no longer exists")


def test_the_template_names_every_placeholder_it_expects_filled(template_text: str):
    """Placeholders are the template's whole content.

    A bare value with no placeholder reads as a default to keep, which is how a
    placeholder-shaped field survives into a real document.
    """

    placeholders = _placeholders(template_text)
    assert len(placeholders) >= 10, (
        "the template has too few placeholders to be a skeleton an author fills in")
    # Every id-bearing field must be a placeholder rather than an example value.
    for field in ("node_id", "purpose", "call_id", "item_id", "check_id",
                  "workflow_id", "stage_kind"):
        assert re.search(rf'"{field}":\s*"<', template_text), (
            f"{field} carries a literal value instead of a placeholder")


def test_the_body_points_at_the_template(template_text: str):
    """A template the body never names is one no author opens.

    This is the failure the template shipped with: it was added to `templates/` and
    SKILL.md went on describing only the schema, so an Agent reading the loading
    order would copy nothing and hand-write a document instead. The template was
    correct and unused.
    """

    skill = SKILL.read_text(encoding="utf-8")

    assert "workflow-template.json" in skill, (
        "SKILL.md never names the template, so nothing tells an author to copy it")


def test_the_body_states_the_refusals_that_make_a_conversion_work(template_text: str):
    """The conversion rules an author needs, each one a way to get it wrong.

    A procedure written for a human is prose; this engine judges a document. The
    rules below are the join between the two, and each prevents a specific defect:
    a standard with no value behind it, a transcribed sequence treated as order, and
    domain knowledge restated as a checklist item.
    """

    del template_text
    skill = SKILL.read_text(encoding="utf-8")

    for rule in (
        "A sentence is not a check",
        "Their step is not your order",
        "Their knowledge stays theirs",
    ):
        assert rule in skill, f"the conversion rules omit: {rule!r}"

