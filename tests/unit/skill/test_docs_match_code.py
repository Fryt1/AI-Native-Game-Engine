"""The docs describe this code, so they are checked against it.

`AGENTS.md` drifted twice: it listed seven CLI commands when there were eight,
and claimed the repository still retained a "transfer file protocol" that had
been deleted with `TransferManifest`. Both were only found by reading it and
checking by hand.

These tests do that checking mechanically. They run in CI, so a doc that stops
describing the code fails the build instead of misleading the next reader.
"""

import pathlib
import re

import pytest

from ainative.cli.commands import COMMANDS
from ainative.cli.output import Verdict
from ainative.model import CheckOperator, CheckStatus, StageKind, TaskRoute

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

# Documents an Agent or maintainer reads. `artifacts/` is excluded: it holds
# historical run records, which are allowed to describe an older repository.
def _docs() -> list[pathlib.Path]:
    return sorted(
        p for p in REPO_ROOT.rglob("*.md")
        if "__pycache__" not in p.parts
        and ".venv" not in p.parts
        and "artifacts" not in p.parts
    )


DOCS = _docs()

# Docs that enumerate the command surface, so they must name every command.
COMMAND_LISTING_DOCS = [
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "README.md",
    REPO_ROOT / "SKILL.md",
    REPO_ROOT / "docs" / "cli.md",
]

# Names removed from the model. A doc mentioning one is describing the past...
REMOVED_NAMES = [
    "ExecutionPlan",
    "WorkflowPlan",
    "WorkflowSelection",
    "PlanStatus",
    "PlanError",
    "StepPlan",
    "CallKind",
    "project_tool",
    "active_plan_revision",
    "preferred_workflow_id",
    "plan_id",
    "plan_status",
    "supersedes_plan_id",
    "TransferManifest",
    "TransferBackendKind",
    "AssetsBridge",
    "RouteAuthority",
    "authority_id",
    "ToolsetRegistry",
    "select_workflow",
    "ALLOWED_WORKFLOWS",
    "replan_plan",
    "validate_plan_structure",
    "plan_from_dict",
]

# ...except in the one place whose job is to name them as things not to bring
# back. `AGENTS.md`'s engineering rules must be able to say "do not reintroduce
# CapabilityBinding" without tripping this test.
BANNED_NAME_EXCEPTIONS = {
    "AGENTS.md": {"CapabilityBinding"},
}


# --- the command surface -------------------------------------------------------


@pytest.mark.parametrize("doc", COMMAND_LISTING_DOCS, ids=lambda p: p.name)
def test_every_command_is_named(doc):
    """A doc that lists commands must list all of them."""

    text = doc.read_text(encoding="utf-8")

    missing = [
        name for name in COMMANDS
        if not re.search(rf"`{re.escape(name)}`|\b{re.escape(name)}\b", text)
    ]

    assert not missing, f"{doc.name} does not mention: {missing}"


def test_the_command_count_is_not_stated_as_a_stale_number():
    """A hard-coded count is a claim that goes stale; none should exist."""

    for doc in DOCS:
        text = doc.read_text(encoding="utf-8")
        for match in re.finditer(r"(\w+) (?:commands|CLI commands)\b", text):
            word = match.group(1)
            assert not word.isdigit(), f"{doc.name} states a command count: {match.group(0)!r}"


# --- removed concepts ----------------------------------------------------------


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.as_posix())
def test_no_doc_describes_a_removed_concept(doc):
    """Naming a deleted type misleads a reader into looking for it."""

    text = doc.read_text(encoding="utf-8")
    allowed = BANNED_NAME_EXCEPTIONS.get(doc.name, set())
    found = [
        name for name in REMOVED_NAMES
        if name not in allowed and re.search(rf"\b{re.escape(name)}\b", text)
    ]

    assert not found, f"{doc.relative_to(REPO_ROOT).as_posix()} still names: {found}"


# --- referenced paths ----------------------------------------------------------


PATH_PATTERN = re.compile(r"`([A-Za-z0-9_][A-Za-z0-9_./\\-]*\.(?:py|md|json|toml|yml|yaml))`")


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.as_posix())
def test_every_referenced_path_exists(doc):
    """A doc pointing at a file that is not there wastes the reader's time.

    A path is accepted when it resolves from the repository root, from the
    document's own directory, or as a suffix of a real path -- docs shorten
    `src/ainative/model/tools.py` to `model/tools.py` on purpose.
    """

    text = doc.read_text(encoding="utf-8")
    unresolved = []

    for raw in sorted(set(PATH_PATTERN.findall(text))):
        candidate = raw.replace("\\", "/")
        if candidate.startswith(("http", "C:")) or ".." in candidate:
            continue
        if (REPO_ROOT / candidate).exists() or (doc.parent / candidate).exists():
            continue
        if "/" in candidate and any(REPO_ROOT.rglob(candidate)):
            continue
        if "/" not in candidate:
            continue
        unresolved.append(raw)

    assert not unresolved, f"{doc.relative_to(REPO_ROOT).as_posix()} references missing: {unresolved}"


# --- the vocabularies ----------------------------------------------------------


def test_the_verdict_vocabulary_is_stated_where_the_envelope_is():
    """A reader who learns the envelope must also learn the words it can carry."""

    for name in ("AGENTS.md", "docs/cli.md", "SKILL.md"):
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        missing = [v.value for v in Verdict if f"`{v.value}`" not in text]
        assert not missing, f"{name} omits verdicts: {missing}"


def test_the_checklist_outcomes_are_stated_in_the_skill():
    """The Agent writes checklist results, so it must know the vocabulary."""

    text = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
    missing = [s.value for s in CheckStatus if f"`{s.value}`" not in text]

    assert not missing, f"SKILL.md omits checklist outcomes: {missing}"


def test_the_stage_operators_are_stated_in_the_template():
    """The Agent picks an operator, so the template must list them all."""

    text = (REPO_ROOT / "templates/workflow-plan-template.md").read_text(encoding="utf-8")
    missing = [op.value for op in CheckOperator if op.value not in text]

    assert not missing, f"the template omits operators: {missing}"


def test_the_stage_kinds_and_routes_are_stated_where_they_are_chosen():
    skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
    template = (REPO_ROOT / "templates/workflow-plan-template.md").read_text(encoding="utf-8")

    assert not [k.value for k in StageKind if k.value not in skill], "SKILL.md omits a Stage kind"
    assert not [r.value for r in TaskRoute if r.value not in template], "the template omits a route"
