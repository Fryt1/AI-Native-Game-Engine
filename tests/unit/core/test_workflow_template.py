"""The shipped Workflow template must stay loadable.

`templates/workflow-plan-template.json` is what an Agent copies to start a
Workflow. If the model changes and this file is not updated, the template
silently becomes a broken starting point — so it is validated here, not trusted.
"""

import json
import pathlib

import pytest

from ainative.reading import validate_workflow_structure, workflow_from_dict

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "templates" / "workflow-plan-template.json"
GUIDANCE_TEMPLATE = REPO_ROOT / "templates" / "workflow-template.md"


def test_the_workflow_template_parses_and_validates():
    document = json.loads(TEMPLATE.read_text(encoding="utf-8"))

    workflow = workflow_from_dict(document)
    validate_workflow_structure(workflow)

    assert workflow.guidance
    assert workflow.stages
    assert workflow.calls


def test_the_workflow_template_carries_no_removed_fields():
    """Guard against a restored field creeping back into the template."""

    raw = TEMPLATE.read_text(encoding="utf-8")
    removed = (
        "profile",
        "authority_id",
        "validation_items",
        "input_keys",
        "output_keys",
        "toolset_id",
        "tool_id",
        "server_id",
        "tool_name",
        "usage",
        "transfer_backend",
        "blender_call_surface",
        "modification_method",
        "host_app",
        "host_call_surface",
        "plan_id",
        "supersedes_plan_id",
    )
    document = json.loads(raw)
    flat = json.dumps(document)

    for name in removed:
        assert f'"{name}"' not in flat, (
            f"{name} no longer exists in the model; remove it from the template"
        )


def test_every_template_call_uses_the_unified_target_shape():
    """One call shape covers MCP and project Tools: target{owner,name}."""

    document = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    calls = [
        call
        for step in document["steps"]
        for stage in step["stages"]
        for call in stage["calls"]
    ]

    assert calls
    for call in calls:
        assert set(call) <= {"call_id", "kind", "target", "arguments", "depends_on"}
        assert call["target"]["owner"]
        assert call["target"]["name"]


def test_the_guidance_template_exists_and_is_not_a_workflow():
    """The prose template describes a lifecycle; it must not contain a Workflow shape."""

    text = GUIDANCE_TEMPLATE.read_text(encoding="utf-8")

    assert text.startswith("# Workflow Template")
    # It must not ship a fill-in Workflow, which would duplicate the JSON template.
    assert "execution_checklist:" not in text
    assert '"calls"' not in text


def test_the_template_route_is_a_real_route():
    document = json.loads(TEMPLATE.read_text(encoding="utf-8"))

    assert document["route"] in {"host_operation", "asset_transfer", "artifact_pipeline"}


@pytest.mark.parametrize("field", ["workflow_id", "guidance", "route", "steps"])
def test_the_template_declares_each_required_top_level_field(field):
    document = json.loads(TEMPLATE.read_text(encoding="utf-8"))

    assert field in document


# --- the eight stability rules -------------------------------------------------
#
# These were recoverable only from git history once templates/ was deleted. They
# are rules an Agent must follow on every Workflow, so they are pinned in two
# places: the template that explains them, and SKILL.md that the Agent reads
# first. Losing either is a regression.

RULES = [
    "freezes an execution checklist and an acceptance",
    "supports at least one execution or acceptance item",
    "never hard-codes a call source",
    "before its first side effect",
    "does not automatically satisfy a semantic",
    "deterministic operators",
    "cannot be converted to `pass`",
    "revision is immutable",
]

NOTES = REPO_ROOT / "templates" / "workflow-plan-template.md"
SKILL = REPO_ROOT / "SKILL.md"


@pytest.mark.parametrize("rule", RULES)
def test_the_workflow_notes_state_every_stability_rule(rule):
    text = NOTES.read_text(encoding="utf-8")

    assert rule in text, f"stability rule missing from {NOTES.name}: {rule!r}"


@pytest.mark.parametrize("rule", RULES)
def test_skill_md_states_every_stability_rule(rule):
    """SKILL.md is what the Agent reads first, so the rules must survive there too."""

    text = SKILL.read_text(encoding="utf-8")

    assert rule in text, f"stability rule missing from SKILL.md: {rule!r}"


def test_the_notes_do_not_reintroduce_removed_fields():
    text = NOTES.read_text(encoding="utf-8")

    for name in ("profile:", "authority_id:", "toolset_id:", "tool_id:", "server_id:", "usage:"):
        assert name not in text, f"{name} no longer exists in the model"
