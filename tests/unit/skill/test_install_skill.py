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

import contextlib
import importlib.util
import io
import pathlib
import re
import tempfile

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


def test_every_top_level_script_is_in_the_bundle():
    """A script a reader would expect in the skill must actually travel with it.

    `pack_skill.py` was left out when it was added, because a hand-maintained list
    does not notice a new sibling. Both scripts are part of how this project is
    distributed, and a recipient who receives only the archive should be able to
    repack it or reinstall from it without fetching the repository.
    """

    carried = _carried()
    scripts = {
        path.name for path in REPO_ROOT.glob("*.py")
        if path.is_file()
    }

    missing = sorted(scripts - {name.split("/")[-1] for name in carried})
    assert not missing, (
        f"these top-level scripts are in the repository but not in the skill: "
        f"{missing}. Add them to BUNDLE_FILES in install_skill.py, or exclude them "
        "by name with a reason if they are not part of the skill")


def test_the_default_target_is_the_projects_own_skill_root():
    """Project roots outrank user roots, so the default installs where it belongs.

    A harness scans `<projectRoot>/.agents/skills` for sessions working in that
    project, and the user's own root for every session on the machine. The default is
    the project's: this skill IS this repository, so a copy of it belongs with the
    repository rather than in one person's home directory.

    Runs `main()` with no arguments, which is the documented `python
    install_skill.py`, and checks where the files landed.
    """

    import sys

    module = _installer()
    expected = REPO_ROOT / ".agents" / "skills" / module.skill_name()
    existed = expected.is_dir()

    original_argv = sys.argv
    sys.argv = ["install_skill.py"]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            code = module.main()
    finally:
        sys.argv = original_argv

    assert code == 0
    assert expected.is_dir(), (
        "the default install did not land in the project's own skill root")
    assert existed or expected.is_dir()


def test_the_install_is_gitignored():
    """The install duplicates the repository, so committing it would double it.

    `.agents/` holds a copy of every file here. Tracked, the repository would carry
    two of everything, and the copy would drift against the original in history.
    """

    import subprocess

    done = subprocess.run(
        ["git", "check-ignore", "-q", ".agents"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        encoding="utf-8", errors="replace")
    assert done.returncode == 0, (
        ".agents/ is not gitignored; the installed skill would be committed as a "
        "second copy of the repository")


def test_the_skill_name_is_read_from_the_frontmatter():
    """Discovery resolves `<name>/SKILL.md`, so the directory must match the name."""

    module = _installer()
    text = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert text.startswith("---\n")
    assert f"name: {module.skill_name()}" in text[: text.index("\n---", 4)]


def test_the_installer_warns_against_installing_the_engine_from_the_copy():
    """Installing the copy repoints a working checkout's engine at a snapshot.

    An editable install names ONE source tree. Running `pip install -e` against the
    installed copy therefore stops the checkout's `src/` from being what executes --
    silently, because every command still works. The symptom is that edits stop
    taking effect, which reads as a caching bug rather than an install mistake.

    The installer printed exactly that command as advice before this was caught. The
    warning is the fix, so it is pinned here.
    """

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        module = _installer()
        module.install(pathlib.Path(tempfile.mkdtemp()))

    printed = output.getvalue()
    assert "already installed" in printed, (
        "the installer no longer says a checkout needs no install of the copy")
    assert "would point the engine at this snapshot" in printed, (
        "the installer no longer says why installing the copy is wrong")


@pytest.mark.parametrize("name", ["src", "guidance", "templates", "docs"])
def test_the_bundled_directories_exist(name: str):
    assert (REPO_ROOT / name).is_dir(), f"the installer names a missing directory: {name}"
