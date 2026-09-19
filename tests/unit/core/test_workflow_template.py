"""The shipped spec must stay loadable, and must still state what an author needs.

`templates/workflow.schema.json` is the definition of the Workflow data structure.
It replaces the JSON and Markdown templates that used to sit beside it: a template
and a schema describe the same thing, and two descriptions of one thing drift. The
schema is the one an Agent or an AI can be checked against, so it is the one kept.

These tests assert the schema still carries the vocabulary an author must know --
every operator, every route -- because a value missing from the spec is a value the
author cannot discover.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from ainative.model.checklists import CheckStatus

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "templates" / "workflow.schema.json"
SKILL = REPO_ROOT / "SKILL.md"

OPERATORS = [
    "manual", "tool_succeeded", "exists", "truthy",
    "equals", "set_equals", "count_equals", "within_tolerance",
]
ROUTES = ["host_operation", "asset_transfer", "artifact_pipeline"]


@pytest.fixture(scope="module")
def schema_text() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def schema(schema_text: str) -> dict:
    return json.loads(schema_text)


def test_the_schema_is_loadable_and_is_json_schema(schema: dict):
    assert schema["$schema"].startswith("https://json-schema.org/")
    assert schema["$id"]
    assert schema["type"] == "object"


def test_the_schema_declares_each_required_top_level_field(schema: dict):
    for field in ("workflow_id", "route", "root"):
        assert field in schema["required"], f"{field} must be required"
        assert field in schema["properties"], f"{field} must be declared"


@pytest.mark.parametrize("operator", OPERATORS)
def test_the_schema_states_every_operator(schema_text: str, operator: str):
    """The Agent picks an operator, so the spec must list them all."""

    assert f'"{operator}"' in schema_text, f"the schema omits the operator {operator!r}"


@pytest.mark.parametrize("route", ROUTES)
def test_the_schema_states_every_route(schema_text: str, route: str):
    assert f'"{route}"' in schema_text, f"the schema omits the route {route!r}"


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
