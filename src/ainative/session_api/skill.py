"""A Skill is loaded, not selected.

The repository *is* the Skill. Loading it means: verify the package is intact and
resolve the guidance the task named. The framework does not pick guidance for the
Agent, and there is no whitelist — the Agent may name any guidance that exists.
"""
from dataclasses import dataclass, field
from pathlib import Path

from ainative.model.task import TaskContract


class SkillIntegrityError(RuntimeError):
    """The Skill package cannot be safely loaded."""


@dataclass(frozen=True, slots=True)
class GuidancePackage:
    """One domain skill, resolved from whatever form it takes on disk.

    Guidance may be a single document or a directory holding documents, scripts,
    schemas and data. Prose is the **floor, not the ceiling**: a lifecycle that is
    only a document is the degenerate case of a skill, and nothing here should
    force a richer one into prose.

    ``entry`` is the document the Agent reads first. ``files`` is everything else
    the package carries, so an Agent can find a script or a schema it needs
    without the loader having to understand any of it.
    """

    name: str
    root: Path
    entry: Path
    files: tuple[Path, ...] = ()
    directories: tuple[Path, ...] = ()

    @property
    def is_directory(self) -> bool:
        return self.root != self.entry

    def read_entry(self) -> str:
        """Return the entry document's text."""

        return self.entry.read_text(encoding="utf-8")

    def describe(self) -> dict:
        """Return a compact inventory, for evidence and for the Agent to read.

        Paths are reported relative and with forward slashes. An inventory is
        carried in evidence, and a Windows backslash there would make the same
        package describe itself differently on two machines.
        """

        def relative(path: Path) -> str:
            return path.relative_to(self.root).as_posix()

        return {
            "name": self.name,
            "form": "directory" if self.is_directory else "document",
            "root": str(self.root),
            "entry": str(self.entry),
            "files": [relative(p) for p in self.files],
            "directories": [relative(p) for p in self.directories],
        }


@dataclass(frozen=True, slots=True)
class SkillSession:
    """Loaded Skill guidance for one task, before the Agent authors a Workflow."""

    skill_id: str
    package_root: Path
    task: TaskContract
    guidance: str | None
    guidance_document: Path | None
    guidance_package: GuidancePackage | None = None
    warnings: tuple[str, ...] = field(default=())

    @property
    def route(self):
        return self.task.route


#: Files that name the document an Agent should read first inside a directory.
ENTRY_NAMES = ("README.md", "index.md", "SKILL.md", "GUIDANCE.md")


class AINativeSkill:
    """Verify and open the Skill package, then resolve the named guidance.

    Loading verifies the package is complete. If the task names guidance, it is
    resolved and read; if it names nothing, the Agent works from `SKILL.md` alone.

    Guidance resolves in either form, and the order is deliberate:

    1. ``guidance/<name>/`` -- a directory, using its entry document;
    2. ``guidance/<name>.md`` -- a single document.

    A directory is tried first so a name can be promoted from a document to a
    package without changing how a task refers to it.

    The repository root *is* the package root: this file lives at
    ``<root>/src/ainative/session_api/skill.py``, so the root is three parents up
    from ``src/ainative/session_api`` and then one more past ``src``.
    """

    skill_id = "ai-native-game-engine"

    def __init__(self, package_root: Path | None = None) -> None:
        # parents[0]=session_api, [1]=ainative, [2]=src, [3]=repository root.
        self.package_root = package_root or Path(__file__).resolve().parents[3]

    def load(self, task: TaskContract) -> SkillSession:
        """Verify the package and open the guidance this task named.

        @param task: the Agent-authored task contract.
        @returns the loaded session.
        @raises SkillIntegrityError when the package or the named guidance is missing.
        """

        import sys
        from importlib.util import module_from_spec, spec_from_file_location

        gate_path = self.package_root / "integrity_gate.py"
        spec = spec_from_file_location("ainative_skill_integrity_gate", gate_path)
        if spec is None or spec.loader is None:
            raise SkillIntegrityError(f"integrity gate is missing: {gate_path}")
        module = module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        report = module.check_package(self.package_root)
        if not report.ok:
            raise SkillIntegrityError("missing Skill files: " + ", ".join(report.missing))

        package: GuidancePackage | None = None
        warnings: list[str] = []
        if task.guidance:
            package, warnings = self.resolve_guidance(task.guidance)

        return SkillSession(
            skill_id=self.skill_id,
            package_root=self.package_root,
            task=task,
            guidance=task.guidance,
            guidance_document=package.entry if package else None,
            guidance_package=package,
            warnings=tuple(warnings),
        )

    def resolve_guidance(self, name: str) -> tuple[GuidancePackage, list[str]]:
        """Resolve one guidance name to a package, in either on-disk form.

        @param name: the guidance name a task named.
        @returns the package and any warnings about its contents.
        @raises SkillIntegrityError when no form of the name exists.
        """

        warnings: list[str] = []
        base = self.package_root / "guidance" / name

        directory = base
        if directory.is_dir():
            entry = next(
                (directory / candidate for candidate in ENTRY_NAMES
                 if (directory / candidate).is_file()), None)
            if entry is None:
                # A directory with no entry document is still usable: the Agent
                # can read whatever it finds. But it should be told, because a
                # skill without an entry point is usually an accident.
                found = sorted(p for p in directory.rglob("*") if p.is_file())
                if not found:
                    raise SkillIntegrityError(
                        f"guidance directory is empty: {directory}")
                entry = found[0]
                warnings.append(
                    f"guidance '{name}' is a directory with no entry document "
                    f"({'/'.join(ENTRY_NAMES)}); using {entry.name}")
            files = tuple(sorted(p for p in directory.rglob("*") if p.is_file()))
            directories = tuple(sorted(p for p in directory.rglob("*") if p.is_dir()))
            entry.read_text(encoding="utf-8")
            return (GuidancePackage(name=name, root=directory, entry=entry,
                                    files=files, directories=directories), warnings)

        document = self.package_root / "guidance" / f"{name}.md"
        if document.is_file():
            document.read_text(encoding="utf-8")
            return (GuidancePackage(name=name, root=document, entry=document,
                                    files=(document,)), warnings)

        raise SkillIntegrityError(
            f"named guidance does not exist: tried {directory}/ and {document}")

