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

# Documents an Agent or maintainer reads. Generated and ignored trees are skipped
# by rule rather than by name: a dot-directory (`.venv`, `.pytest_cache`,
# `.ruff_cache`, `.git`) and `artifacts/`, which holds historical run records that
# are allowed to describe an older repository. Naming them one at a time is how
# `.pytest_cache/README.md` stayed in the set, which made the size of this suite
# depend on whether it had been run before.
def _docs() -> list[pathlib.Path]:
    return sorted(
        p for p in REPO_ROOT.rglob("*.md")
        if not any(
            part.startswith(".") or part in {"__pycache__", "artifacts"}
            for part in p.relative_to(REPO_ROOT).parts
        )
    )


DOCS = _docs()

#: A bare drive letter followed by a separator: `C:\...` or `C:/...`. A document
#: carrying one names the machine it was written on, and reads as broken to anyone
#: else. The lookbehind is what keeps a URL scheme out: in `https://` the `s` sits
#: after a letter, so it is not a drive letter, while `D:\` at the start of a word
#: is.
ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.as_posix())
def test_no_doc_names_a_machine_specific_location(doc):
    """Every path in a document must be relative to the repository root.

    A machine-specific path is worse than a broken one: it looks authoritative, so
    a reader assumes it is the answer rather than a leftover. `AGENTS.md` carried a
    dozen of them -- the loading order, the directory tree, the ownership list, and
    both example blocks all began with one machine's checkout -- and every one of
    them was wrong for everybody else.

    Paths inside a fenced block are checked too. That is where the examples live,
    and an example is the thing a reader copies.
    """

    offenders = [
        (number, line.strip())
        for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1)
        if ABSOLUTE_PATH.search(line)
    ]

    assert not offenders, (
        f"{doc.relative_to(REPO_ROOT).as_posix()} names a machine-specific path; "
        f"write it relative to the repository root instead: {offenders}")

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


def test_the_stage_operators_are_stated_in_the_schema():
    """The Agent picks an operator, so the spec must list them all.

    The operator vocabulary moved from the deleted notes template to the schema,
    which is the definition of the data structure.
    """

    text = (REPO_ROOT / "templates" / "workflow.schema.json").read_text(encoding="utf-8")
    missing = [op.value for op in CheckOperator if f'"{op.value}"' not in text]

    assert not missing, f"the schema omits operators: {missing}"


def test_the_stage_kinds_and_routes_are_stated_where_they_are_chosen():
    skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
    schema = (REPO_ROOT / "templates" / "workflow.schema.json").read_text(encoding="utf-8")

    assert not [k.value for k in StageKind if k.value not in skill], "SKILL.md omits a Stage kind"
    assert not [r.value for r in TaskRoute if f'"{r.value}"' not in schema], (
        "the schema omits a route")


def test_the_readme_agent_api_example_still_runs():
    """A code example is the most rottable statement a document can make.

    Nothing type-checks it, no test imports it, and renaming a method leaves it
    looking authoritative while it no longer runs. README's Agent-facing section
    names four calls and two attributes; this is the one place they meet the real
    signatures. It asserts the API the README advertises, not the README's prose --
    the prose is checked by the tests above.
    """

    from ainative.model import (
        CallTarget,
        ExecutionResult,
        TaskContract,
        TaskRoute,
        TaskStatus,
    )
    from ainative.session_api import AcceptanceGuide
    from tests.support.workflow_factory import call, stage_spec, step, workflow_for

    task = TaskContract(task_id="readme", objective="run the README example",
                        route=TaskRoute.HOST_OPERATION)
    workflow = workflow_for(task, (
        step("step-1", "a phase", (
            stage_spec("validate-asset", "validate", "check",
                       (call("ue5", "set_actor_transform", "a1"),)),)),))

    guide = AcceptanceGuide()
    session = guide.start(task, workflow)

    execution_result = ExecutionResult(
        call_id="a1", status=TaskStatus.SUCCEEDED,
        target=CallTarget(owner="ue5", name="set_actor_transform"),
        outputs={"done": True},
    )
    session.record_execution_result(execution_result)

    node_result = session.complete_node("/step-1/validate-asset/")
    assert node_result.node_path == "/step-1/validate-asset/", (
        "README says a StageResult carries the node_path it closed")

    assert session.finish().status is TaskStatus.SUCCEEDED

    view = execution_result.evidence_view()
    for key in ("status", "target", "preserved_relations", "lost_relations",
                "artifact_count", "artifacts", "warnings", "errors"):
        assert key in view, f"README names {key} as first-class evidence"
    assert "done" in view, "README says a check can also address any key in outputs"
