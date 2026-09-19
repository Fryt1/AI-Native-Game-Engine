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

#: A markdown link target: `[label](target)`. Backticked paths were checked and
#: link targets were not, which is backwards -- a link is what a reader clicks, and
#: both files in the since-deleted `references/` tree pointed two levels too high.
LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.as_posix())
def test_every_markdown_link_resolves(doc):
    """A link that goes nowhere is worse than no link: it looks like the way in.

    The target is resolved against the document's own directory, which is how a
    reader's browser resolves it. An absolute URL, a bare anchor, and a `mailto:`
    are not filesystem paths and are skipped. A relative target that climbs out of
    the repository is NOT skipped: that is exactly what a link with one `..` too
    many looks like, and skipping it is what let two links in the since-deleted
    `references/` tree point two levels too high unnoticed.
    """

    unresolved = []

    for target in sorted(set(LINK_PATTERN.findall(doc.read_text(encoding="utf-8")))):
        if target.startswith(("http://", "https://", "mailto:", "#", "/")):
            continue
        path = target.split("#", 1)[0]
        if not path:
            continue
        resolved = (doc.parent / path).resolve()
        if not resolved.exists():
            unresolved.append(target)

    assert not unresolved, (
        f"{doc.relative_to(REPO_ROOT).as_posix()} has links that resolve to nothing: "
        f"{unresolved}")


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.as_posix())
def test_every_referenced_path_exists(doc):
    """A doc pointing at a file that is not there wastes the reader's time.

    A path is accepted when it resolves from the repository root, from the
    document's own directory, or as a suffix of a real path -- docs shorten
    `src/ainative/model/tools.py` to `model/tools.py` on purpose.

    A path with `..` in it used to be skipped outright, which meant the relative
    links were the only ones never checked -- and every link in the since-deleted
    `references/` tree was wrong by two directory levels for as long as that
    exemption existed. A relative link is resolved against the document's own
    directory and must land on something; only one that climbs out of the
    repository is skipped.
    """

    text = doc.read_text(encoding="utf-8")
    unresolved = []

    for raw in sorted(set(PATH_PATTERN.findall(text))):
        candidate = raw.replace("\\", "/")
        if candidate.startswith(("http", "C:")):
            continue
        if ".." in candidate:
            resolved = (doc.parent / candidate).resolve()
            if not resolved.is_relative_to(REPO_ROOT):
                continue
            if not resolved.exists():
                unresolved.append(raw)
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


def test_every_top_level_directory_is_one_of_the_owned_categories():
    """A directory is a claim about who reads a file, so the set is closed.

    `references/` held two files for a long time and justified neither: what a
    host's MCP server can do is decided by the running server, so no document here
    can state it, and the submitted-result shapes belonged beside the Workflow
    schema. Both facts had a home; the directory did not. Adding a third was easier
    than asking, which is exactly why this test exists -- `docs/MAINTENANCE.md`
    says a document that fits no row means the fact is not this repository's, not
    that a directory is missing.
    """

    allowed = {"docs", "guidance", "src", "templates", "tests", "artifacts"}

    present = {
        path.name for path in REPO_ROOT.iterdir()
        if path.is_dir()
        and not path.name.startswith(".")
        and path.name not in {"__pycache__", "node_modules"}
    }

    assert present <= allowed, (
        f"unowned top-level directories: {sorted(present - allowed)}. Each one is a "
        "claim that some fact needs its own home; check docs/MAINTENANCE.md first")


def test_the_documented_ownership_matches_the_tree():
    """AGENTS.md draws the tree, so it must draw the one that exists.

    The directory listing is prose, and prose drifts: this is what let the tree in
    `AGENTS.md` keep naming a directory after it was deleted.
    """

    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    start = agents.index("```text\n<repository root>/")
    drawing = agents[start:agents.index("```", start + 10)]

    for name in ("guidance/", "templates/", "src/ainative/", "tests/", "docs/", "artifacts/"):
        assert name in drawing, f"AGENTS.md draws no {name}"

    assert "references/" not in drawing, "AGENTS.md still draws a directory that is gone"


def test_the_data_structure_section_draws_every_model_class_it_should():
    """The drawing is the reader's map, so the main shapes must all appear.

    A structure missing from the drawing is invisible, and nothing about the names
    that ARE present would notice. This is the half that can be checked robustly:
    the document draws field lists as `├── call_id / status`, not as `Class.field`,
    so a per-field assertion against the model has no subject matter -- and a shape
    parser over the ASCII trees misattributes `ChecklistSummary` (named without a
    drawing) and the directory tree at the end.
    """

    import dataclasses

    from ainative import model as model_module

    text = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    section = text.split("## 三、数据结构", 1)[1].split("\n## ", 1)[0]

    expected = (
        "TaskContract", "WorkflowTree", "WorkflowNode", "StageBody",
        "AcceptanceCheck", "ToolCall", "ExecutionResult", "StageResult", "TaskResult",
    )

    missing = [name for name in expected if name not in section]

    assert not missing, f"docs/ARCHITECTURE.md's data-structure drawing omits: {missing}"
    assert all(dataclasses.is_dataclass(getattr(model_module, name)) for name in expected), (
        "this list names something the model no longer defines")


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
