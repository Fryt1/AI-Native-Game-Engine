"""The installed skill must be complete and self-consistent.

The whole project installs, because the whole project is the skill: SKILL.md tells
the Agent to run `python -m ainative.session`, and that program is what makes the
instructions checkable rather than advisory. Two hazards follow, and this file
covers both.

First, a body that names a file the install does not carry sends the Agent to a path
that is not there. The check is the join between the two halves: every
repository-relative path a bundled document names must itself be bundled. A path
resolving in the checkout proves nothing, because the checkout is not where the
Agent reads it.

Second, an install that carries the wrong things. Build outputs, local state, and
caches would make the installed bundle machine-specific; the tests below pin what is
excluded and what must be present for the engine to run.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
INSTALLER = REPO_ROOT / "install_skill.py"


def _installer():
    spec = importlib.util.spec_from_file_location("install_skill", INSTALLER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _carried() -> set[str]:
    return {pathlib.PurePosixPath(relative).as_posix()
            for _source, relative in _installer().sources()}


#: A repository-relative path written as `docs/cli.md`. A bare filename such as
#: `result-contract.md` is skipped: the documents use those as prose names for a file
#: whose full path appears elsewhere, not as something to open.
PATH_PATTERN = re.compile(r"`((?:[a-z_]+/)+[a-z_.-]+\.(?:md|json|py))`")

#: Paths a bundled document names while addressing a MAINTAINER rather than the
#: Agent reading the skill. Each is listed with the reason it is not shipped.
#:
#: Both name files under `tests/`, which belongs to the source rather than the
#: product. The sentence in each case describes how this repository is maintained,
#: so it is addressed to whoever edits it, not to whoever runs the skill.
MAINTAINER_ONLY_REFERENCES = {
    # DEPENDENCIES.md says the repository ships no host fixture and points at the
    # sample Task Contract under tests/ to show what it ships instead.
    "tests/support/task-cross-host.json",
    # ADDING_GUIDANCE.md tells a maintainer which test enforces the registration
    # step it just described.
    "tests/unit/skill/test_guidance_inventory.py",
}


def _bundled_texts() -> dict[str, str]:
    """Return the installed documents, keyed by POSIX path inside the bundle."""

    texts: dict[str, str] = {}
    for source, relative in _installer().sources():
        if source.suffix in {".md", ".json"}:
            texts[pathlib.PurePosixPath(relative).as_posix()] = source.read_text(
                encoding="utf-8")
    return texts


def test_the_bundle_carries_every_file_it_names():
    bundled = _bundled_texts()
    # The full install list, not just the documents: a document may name an engine
    # module, and that module is carried too.
    carried = _carried()

    unresolved: list[str] = []
    for name, text in bundled.items():
        for referenced in sorted(set(PATH_PATTERN.findall(text))):
            if referenced in carried or referenced in MAINTAINER_ONLY_REFERENCES:
                continue
            # A path a document names may deliberately live outside the skill. Flag
            # it only when the file IS in the repository, which means the bundle
            # could have carried it and chose not to.
            if (REPO_ROOT / referenced).exists():
                unresolved.append(f"{name} names {referenced}")

    assert not unresolved, (
        "the installed skill would send an Agent to a path it does not contain: "
        f"{unresolved}")


def test_every_maintainer_only_reference_is_still_real():
    """The exception list must not outlive the references it excuses."""

    for referenced in MAINTAINER_ONLY_REFERENCES:
        assert (REPO_ROOT / referenced).exists(), (
            f"{referenced} is excused as a maintainer reference but no longer exists; "
            "remove it from MAINTAINER_ONLY_REFERENCES")


def test_the_bundle_carries_the_engine():
    """The program the instructions name has to be in the install.

    Without `src/`, an Agent on a machine that has only the skill reads "run
    `python -m ainative.session`" and has nothing to run. The instructions would be
    advisory, which is the one thing this project exists not to be.
    """

    carried = _carried()

    assert "src/ainative/__init__.py" in carried, "the engine did not install"
    assert "pyproject.toml" in carried, (
        "the installed copy must be pip-installable on its own")


def test_the_bundle_carries_the_instructions_and_their_resources():
    carried = _carried()

    for required in (
        "SKILL.md",
        "templates/workflow.schema.json",
        "templates/result-contract.md",
        "docs/cli.md",
        "docs/DEPENDENCIES.md",
        "guidance/index.md",
        "integrity_gate.py",
        "install_skill.py",
    ):
        assert required in carried, f"the install omits {required}"


def test_the_bundle_carries_no_build_output_or_local_state():
    """An installed skill is a copy, so anything machine-specific would travel.

    Caches and a virtualenv would also make the install differ per machine while
    `--check` reported it as drift.
    """

    carried = _carried()

    for pattern in (".venv/", "__pycache__/", ".pytest_cache/", ".ruff_cache/",
                    "artifacts/", ".git/"):
        offenders = [name for name in carried if pattern in name]
        assert not offenders, f"the install carries {pattern}: {offenders[:3]}"

    assert not [name for name in carried if name.endswith(".pyc")]


def test_the_bundle_carries_no_tests():
    """This repository's tests belong to the source, not to the product."""

    carried = _carried()

    assert not [name for name in carried if name.startswith("tests/")]


def test_the_skill_name_is_read_from_the_frontmatter():
    """Discovery resolves `<name>/SKILL.md`, so the directory must match the name."""

    module = _installer()
    text = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert text.startswith("---\n")
    assert f"name: {module.skill_name()}" in text[: text.index("\n---", 4)]


@pytest.mark.parametrize("name", ["src", "guidance", "templates", "docs"])
def test_the_bundled_directories_exist(name: str):
    assert (REPO_ROOT / name).is_dir(), f"the installer names a missing directory: {name}"
