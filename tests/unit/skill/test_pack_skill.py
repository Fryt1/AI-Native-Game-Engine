"""A packed skill archive must be usable where it lands.

`install_skill.py` copies the project into a skill root on this machine;
`pack_skill.py` writes the same contents into one file for someone else. This
covers the packer: what it puts in the archive, and what a recipient must find when
they unpack it somewhere this repository does not exist.

The packer takes its file list from the installer deliberately. Two lists would
drift the first time one was edited, and the symptom -- an archive missing a file the
body names -- would surface only at the recipient.
"""

from __future__ import annotations

import importlib.util
import pathlib
import zipfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PACKER = REPO_ROOT / "pack_skill.py"
INSTALLER = REPO_ROOT / "install_skill.py"


def _module(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def archive(tmp_path_factory) -> pathlib.Path:
    """Pack once for the whole module: the archive is the subject of every test."""

    packer = _module(PACKER, "pack_skill")
    return packer.pack(tmp_path_factory.mktemp("dist") / "skill.zip")


@pytest.fixture(scope="module")
def entries(archive: pathlib.Path) -> set[str]:
    with zipfile.ZipFile(archive) as zipped:
        return {name.rstrip("/") for name in zipped.namelist()}


def test_the_archive_holds_one_top_level_skill_directory(archive: pathlib.Path, entries: set[str]):
    """Extracting into a skill root must produce `<name>/SKILL.md` directly.

    Discovery resolves one level: `<root>/<name>/SKILL.md`. An archive that nests
    deeper, or scatters files at the root, unpacks into something no harness finds.
    """

    installer = _module(INSTALLER, "install_skill")
    name = installer.skill_name()

    tops = {entry.split("/")[0] for entry in entries}
    assert tops == {name}, f"the archive has more than one top-level entry: {tops}"
    assert f"{name}/SKILL.md" in entries


def test_the_archive_carries_what_the_installer_carries(archive: pathlib.Path, entries: set[str]):
    """The two must agree, because the packer imports the installer's list."""

    installer = _module(INSTALLER, "install_skill")
    name = installer.skill_name()
    expected = {
        f"{name}/{relative.as_posix()}" for _source, relative in installer.sources()
    }
    marked = {entry for entry in entries if not entry.endswith(installer.MARKER)}

    assert marked == expected, (
        f"the archive and the installer disagree: "
        f"only in archive {sorted(marked - expected)[:3]}, "
        f"only in installer {sorted(expected - marked)[:3]}")


def test_the_archive_carries_the_engine_and_the_instructions(entries: set[str]):
    """The recipient must be able to run what the body tells them to run."""

    installer = _module(INSTALLER, "install_skill")
    name = installer.skill_name()

    for required in ("SKILL.md", "pyproject.toml", "src/ainative/__init__.py",
                     "templates/workflow.schema.json", "guidance/index.md",
                     "docs/cli.md", "docs/DEPENDENCIES.md", "integrity_gate.py"):
        assert f"{name}/{required}" in entries, f"the archive omits {required}"


def test_the_archive_carries_no_build_output_or_local_state(entries: set[str]):
    """An archive travels, so anything machine-specific would travel with it."""

    for pattern in (".venv/", "__pycache__/", ".pytest_cache/", ".ruff_cache/",
                    "artifacts/", ".git/", "tests/"):
        offenders = [entry for entry in entries if pattern in entry]
        assert not offenders, f"the archive carries {pattern}: {offenders[:3]}"


def test_the_archive_records_where_it_came_from(archive: pathlib.Path, entries: set[str]):
    """A packed skill is a build output; the recipient should be able to tell."""

    installer = _module(INSTALLER, "install_skill")
    marker = f"{installer.skill_name()}/{installer.MARKER}"

    assert marker in entries
    with zipfile.ZipFile(archive) as zipped:
        text = zipped.read(marker).decode("utf-8")
    assert "source:" in text and "revision:" in text


def test_verify_accepts_a_good_archive(archive: pathlib.Path):
    """`--verify` is what a recipient runs before trusting the file."""

    packer = _module(PACKER, "pack_skill")

    assert packer.verify(archive) == 0


def test_verify_rejects_an_archive_missing_the_engine(tmp_path: pathlib.Path, archive: pathlib.Path):
    """A pack without the engine loads and lists, then cannot run anything.

    Checks that `--verify` fails, rather than reporting success for an archive that
    only looks complete.
    """

    packer = _module(PACKER, "pack_skill")
    installer = _module(INSTALLER, "install_skill")
    name = installer.skill_name()

    stripped = tmp_path / "no-engine.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(stripped, "w") as target:
        for entry in source.namelist():
            if entry.startswith(f"{name}/src/"):
                continue
            target.writestr(entry, source.read(entry))

    assert packer.verify(stripped) == 1
