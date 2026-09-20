"""A Skill is loaded, not selected.

The repository *is* the Skill. Loading it means one thing: verify the package is
intact. Naming a lifecycle is the Agent's business, and the skill catalog already
does that job -- a name that does not exist is a name the model never sees, so the
engine does not resolve one, does not hold a second copy of the inventory, and does
not refuse work over a string it cannot check.

What remains here is the integrity gate. A missing prompt asset would leave an Agent
following instructions that are no longer there, and that is a fact only this
process can observe.
"""
from dataclasses import dataclass, field
from pathlib import Path

from ainative.model.task import TaskContract


class SkillIntegrityError(RuntimeError):
    """The Skill package cannot be safely loaded."""


@dataclass(frozen=True, slots=True)
class SkillSession:
    """A verified Skill package, for one task."""

    skill_id: str
    package_root: Path
    task: TaskContract
    warnings: tuple[str, ...] = field(default=())


class AINativeSkill:
    """Verify and open the Skill package.

    The repository root *is* the package root: this file lives at
    ``<root>/src/ainative/session_api/skill.py``, so the root is three parents up from
    ``src/ainative/session_api`` and then one more past ``src``.
    """

    skill_id = "ai-native-game-engine"

    def __init__(self, package_root: Path | None = None) -> None:
        # parents[0]=session_api, [1]=ainative, [2]=src, [3]=repository root.
        self.package_root = package_root or Path(__file__).resolve().parents[3]

    def load(self, task: TaskContract) -> SkillSession:
        """Verify the package.

        @param task: the Agent-authored task contract, carried through for the caller.
        @returns the loaded session.
        @raises SkillIntegrityError when a required file is missing.
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

        return SkillSession(
            skill_id=self.skill_id,
            package_root=self.package_root,
            task=task,
        )
