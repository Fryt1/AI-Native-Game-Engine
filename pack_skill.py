"""Pack this project into a distributable skill archive.

`install_skill.py` copies the project into a skill root on this machine. This packs
the same contents into one file that can be handed to someone else, who unpacks it
into their own skill root. Both take their file list from the same place, so the two
cannot disagree about what the skill contains -- a packer with its own idea of the
bundle would ship something the installer would never produce.

The archive holds one top-level directory named after the skill, so extracting it
into a skill root yields the layout discovery expects:

    ~/.agents/skills/ai-native-game-engine/SKILL.md

The archive is a copy of the source at a revision, not a view onto it: a skill that
worked only while the checkout was nearby would not be distributable, and shipping
the engine means the recipient can run the commands the body names.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
INSTALLER = REPO_ROOT / "install_skill.py"


def _installer():
    """Load install_skill.py, which owns what belongs in a skill.

    Imported rather than duplicated: the packer and the installer must agree on the
    file list, and two lists would drift the first time one was edited.
    """

    spec = importlib.util.spec_from_file_location("install_skill", INSTALLER)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {INSTALLER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pack(output: Path | None = None) -> Path:
    """Write the skill archive and return its path."""

    install = _installer()
    name = install.skill_name()
    revision = install.revision()

    if output is None:
        output = REPO_ROOT / "dist" / f"{name}-{revision}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)

    files = install.sources()
    marker = (
        f"source: {REPO_ROOT}\nrevision: {revision}\n"
        f"packed by pack_skill.py -- unpack into a skill root\n"
    )

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for source, relative in files:
            # The name/ prefix is what makes `unzip` into a skill root produce the
            # layout discovery resolves.
            archive.write(source, f"{name}/{relative.as_posix()}")
        archive.writestr(f"{name}/{install.MARKER}", marker)

    size = output.stat().st_size
    print(f"packed {name} at {revision}")
    print(f"  {output}")
    print(f"  {len(files)} files, {size} bytes")
    print(f"  sha256 {hashlib.sha256(output.read_bytes()).hexdigest()[:16]}")
    print()
    # The archive's single top-level directory is already the `<name>/` discovery
    # expects, so extracting into any skill root is the whole install. Destinations
    # are named by ROLE rather than by a path: this machine's home directory in an
    # instruction meant for someone else is both wrong and unhelpful.
    print("  A recipient extracts it into a skill root and is done:")
    print(f"    python -c \"import zipfile;zipfile.ZipFile(r'{output}')"
          f".extractall(r'<skill root>')\"")
    print()
    print("  <skill root> is a directory a harness scans:")
    print("    <project>/.agents/skills   for sessions working in that project")
    print("    ~/.agents/skills           for every session on the machine")
    return output


def verify(archive: Path) -> int:
    """Unpack the archive somewhere isolated and check it is a usable skill.

    Checks the things discovery and the loading order depend on: frontmatter
    discovery can read, the entry point present, and the engine present so the
    commands in the body can run. A pack that omits any of these looks fine until
    someone tries to use it.
    """

    install = _installer()
    name = install.skill_name()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with zipfile.ZipFile(archive) as zipped:
            bad = zipped.testzip()
            if bad is not None:
                print(f"  corrupt entry: {bad}")
                return 1
            zipped.extractall(root)

        unpacked = root / name
        if not unpacked.is_dir():
            print(f"  the archive has no {name}/ directory at its root")
            return 1

        problems: list[str] = []

        skill_md = unpacked / "SKILL.md"
        if not skill_md.is_file():
            problems.append("SKILL.md is missing")
        else:
            text = skill_md.read_text(encoding="utf-8")
            if not text.startswith("---\n"):
                problems.append("SKILL.md has no frontmatter")
            elif f"name: {name}" not in text[: text.index("\n---", 4)]:
                problems.append("the declared name does not match the directory")

        # The loading order names these, and the body tells an Agent to run the
        # engine; a pack missing any of them is not usable on its own.
        for required in ("pyproject.toml", "src/ainative/__init__.py",
                         "templates/workflow.schema.json",
                         "docs/cli.md", "docs/DEPENDENCIES.md", "integrity_gate.py"):
            if not (unpacked / required).exists():
                problems.append(f"{required} is missing")

        for absent in (".venv", "__pycache__", "tests", "artifacts"):
            if (unpacked / absent).exists():
                problems.append(f"{absent} should not be in a packed skill")

        if problems:
            print(f"  {archive} is not a usable skill:")
            for problem in problems:
                print(f"    {problem}")
            return 1

        count = len([p for p in unpacked.rglob("*") if p.is_file()])
        print(f"  {archive.name}: {count} files, a usable skill")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "archive", type=Path, nargs="?",
        help="with --verify, the archive to inspect; otherwise unused")
    parser.add_argument(
        "--out", type=Path, default=None,
        help="where to write the archive (default: dist/<name>-<revision>.zip)")
    parser.add_argument(
        "--verify", action="store_true",
        help="unpack an archive and report whether it is a usable skill")
    args = parser.parse_args()

    if args.verify:
        if args.archive is None:
            parser.error("--verify needs an archive path")
        return verify(args.archive)

    pack(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
