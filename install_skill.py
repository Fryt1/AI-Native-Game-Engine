"""Install this project as a skill into an agent's skill root.

The repository is the source; a skill root is an install location, the way
`site-packages` differs from a checkout. This script is the step between them.

The skill installs what DRIVING the engine needs, not what developing it needs. The
engine travels, because SKILL.md tells the Agent to run `python -m ainative.session`
and that program is what makes the instructions checkable rather than advisory. The
documents an Agent reads travel. The documents a maintainer reads do not: an Agent
handed ARCHITECTURE.md, MAINTENANCE.md, or this repository's own AGENTS.md has been
given weight it will never act on, and a recipient installing the skill is not
maintaining it.

What lands in the skill root is a copy, not a link, so the installed skill keeps
working when the checkout moves or disappears. Engine changes reach it by
reinstalling, which is what `--check` is for: it reports drift rather than repairing
it silently, because the installed copy is a build output and edits there are lost.
"""

from __future__ import annotations

import argparse
import filecmp
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SKILL_MD = REPO_ROOT / "SKILL.md"

#: Copied into the skill root. Directories are walked recursively.
#:
#: `docs` is a file list rather than the whole directory: SKILL.md's loading order
#: reaches exactly two documents there, and the rest of `docs/` is maintainer
#: material. A directory here would pull all of it in.
BUNDLE_DIRS = ("src", "templates")

#: Copied from the repository root.
BUNDLE_FILES = (
    # The body the Agent reads, and what its loading order reaches.
    "SKILL.md",
    "integrity_gate.py",
    "docs/cli.md",
    "docs/DEPENDENCIES.md",
    # The engine must be installable from the copy on a machine with no checkout.
    "pyproject.toml",
    # Both directions of distribution, so a recipient can reinstall or repack.
    "install_skill.py",
    "pack_skill.py",
    "LICENSE",
)

#: Present in the repository, deliberately absent from the skill. Each is a decision
#: rather than an omission, and the tests check that every top-level document is
#: either bundled or listed here.
DEVELOPMENT_ONLY = {
    "AGENTS.md": "instructions for editing this repository, not for using the skill",
    "README.md": "the repository's front page: install, architecture, contributing",
    "docs/ARCHITECTURE.md": "how the engine is built, for whoever changes it",
    "docs/MAINTENANCE.md": "placement tables and change-ownership for maintainers",
    "docs/VALIDATION_REPORT.md": "verification evidence recorded for this revision",
}

#: Never copied. Build outputs and local state, not part of the skill.
EXCLUDED_DIRS = {
    ".git", ".github", ".venv", ".pytest_cache", ".ruff_cache", "__pycache__",
    "artifacts", ".agents", "node_modules", "dist", "build", "tests",
}
#: Build output that `pip install -e .` drops INSIDE the source tree, so a
#: directory-name exclusion does not catch it. It held six files -- PKG-INFO,
#: SOURCES.txt, entry_points.txt and friends -- describing one machine's install,
#: and it travelled into the archive until a listing was read closely enough.
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".egg-info", ".egg-link"}
EXCLUDED_NAMES = {"uv.lock", ".gitignore", ".installed-from", "PKG-INFO", "SOURCES.txt"}

#: Written into the installed copy so a reader can tell it is generated.
MARKER = ".installed-from"


def skill_name() -> str:
    """Return the skill name from SKILL.md's frontmatter.

    Read rather than hardcoded, so the directory and the declared name cannot drift
    apart: discovery resolves `<name>/SKILL.md`, and a mismatch means the skill is
    never found.
    """

    text = SKILL_MD.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SystemExit("SKILL.md does not open with YAML frontmatter")
    frontmatter = text[4:text.index("\n---", 4)]
    match = re.search(r"^name:\s*(\S+)\s*$", frontmatter, re.MULTILINE)
    if match is None:
        raise SystemExit("SKILL.md declares no name")
    return match.group(1)


def revision() -> str:
    """Return the source revision, or a placeholder outside a Git checkout."""

    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace")
    except OSError:
        return "unknown"
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else "unknown"


def _excluded(path: Path) -> bool:
    """Return whether a file inside a bundled directory is left out.

    Matched on every path PART, not just the file's own name: build output such as
    `src/*.egg-info/` is a directory, and its files look ordinary (`.txt`, `.py`) from
    the inside. Checking only the basename let six of them travel into the archive.
    """

    parts = path.relative_to(REPO_ROOT).parts
    for part in parts:
        if part in EXCLUDED_NAMES or part in EXCLUDED_DIRS:
            return True
        if Path(part).suffix in EXCLUDED_SUFFIXES:
            return True
    return False


def sources() -> list[tuple[Path, Path]]:
    """Return (source, relative destination) for every file that installs."""

    pairs: list[tuple[Path, Path]] = []

    for name in BUNDLE_FILES:
        source = REPO_ROOT / name
        if not source.is_file():
            raise SystemExit(f"the bundle names a file that is not there: {name}")
        pairs.append((source, Path(name)))

    for name in BUNDLE_DIRS:
        directory = REPO_ROOT / name
        if not directory.is_dir():
            raise SystemExit(f"the bundle names a directory that is not there: {name}")
        for path in sorted(directory.rglob("*")):
            if path.is_file() and not _excluded(path):
                pairs.append((path, path.relative_to(REPO_ROOT)))

    return pairs


def install(destination: Path) -> int:
    """Copy the project into the skill root, replacing any previous install."""

    target = destination / skill_name()
    if target.exists():
        shutil.rmtree(target)

    for source, relative in sources():
        to = target / relative
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, to)

    (target / MARKER).write_text(
        f"source: {REPO_ROOT}\nrevision: {revision()}\n"
        "generated by install_skill.py -- edits here are overwritten on reinstall\n",
        encoding="utf-8")

    files = [p for p in target.rglob("*") if p.is_file() and p.name != MARKER]
    size = sum(p.stat().st_size for p in files)
    print(f"installed {skill_name()} -> {target}")
    print(f"  {len(files)} files, {size} bytes")
    print("  a harness working in this project scans this root; the install is a")
    print("  build output and is gitignored -- rerun this script after pulling")
    print()
    # The engine is a Python package and `-e` points an install at one source tree.
    # Installing the COPY would repoint a working checkout at a snapshot: edits in
    # the repository would then have no effect on what runs, which is the opposite
    # of what a developer wants and is invisible until something behaves oddly.
    print("  If you are working in this checkout, the engine is already installed")
    print("  from it: `pip install -e .` at the repository root. This copy needs")
    print("  no install, and installing it would point the engine at this snapshot.")
    print()
    print("  A machine that has only the skill has no repository to install from,")
    print("  so it installs the engine from the copy:")
    print(f"    pip install -e \"{target}\"")
    return 0


def check(destination: Path) -> int:
    """Report whether the installed copy matches the source."""

    target = destination / skill_name()
    if not target.is_dir():
        print(f"not installed: {target}")
        return 1

    differing: list[str] = []
    missing: list[str] = []
    for source, relative in sources():
        to = target / relative
        if not to.is_file():
            missing.append(relative.as_posix())
        elif not filecmp.cmp(source, to, shallow=False):
            differing.append(relative.as_posix())

    expected = {relative for _source, relative in sources()}
    installed = {
        p.relative_to(target) for p in target.rglob("*")
        if p.is_file() and p.name != MARKER
    }
    extra = sorted(p.as_posix() for p in installed - expected)

    if not (differing or missing or extra):
        print(f"{target} matches the source at {revision()}")
        return 0

    for label, entries in (("differs", differing), ("missing", missing),
                           ("not in the source", extra)):
        for entry in entries[:10]:
            print(f"  {label}: {entry}")
        if len(entries) > 10:
            print(f"  {label}: ... and {len(entries) - 10} more")
    print(f"\n{target} does not match the source; reinstall to refresh it")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest", type=Path, default=REPO_ROOT / ".agents" / "skills",
        help="the skill root to install into (default: the project's own "
             "<root>/.agents/skills, which a harness scans while working in this "
             "project; pass ~/.agents/skills to make it available everywhere)")
    parser.add_argument(
        "--check", action="store_true",
        help="report whether the installed copy matches the source")
    args = parser.parse_args()

    destination = args.dest.expanduser().resolve()
    if args.check:
        return check(destination)

    destination.mkdir(parents=True, exist_ok=True)
    return install(destination)


if __name__ == "__main__":
    sys.exit(main())
