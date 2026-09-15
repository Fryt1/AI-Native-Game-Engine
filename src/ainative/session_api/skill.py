"""A Skill is loaded, not selected.

The repository *is* the Skill. Loading it means: verify the package is intact and
resolve the guidance document the task named. The framework does not pick
guidance for the Agent, and there is no whitelist — the Agent may name any
guidance document that exists.
"""
from dataclasses import dataclass
from pathlib import Path

from ainative.model.task import TaskContract


class SkillIntegrityError(RuntimeError):
    """The Skill package cannot be safely loaded."""


@dataclass(frozen=True, slots=True)
class SkillSession:
    """Loaded Skill guidance for one task, before the Agent authors a Workflow."""

    skill_id: str
    package_root: Path
    task: TaskContract
    guidance: str | None
    guidance_document: Path | None

    @property
    def route(self):
        return self.task.route


class AINativeSkill:
    """Verify and open the Skill package, then resolve the named guidance.

    Loading verifies the package is complete. If the task names a guidance
    document, it is resolved and read; if it names nothing, the Agent works from
    `SKILL.md` alone.

    The repository root *is* the package root: this file lives at
    ``<root>/src/ainative/agent/skill.py``, so the root is three parents up from
    ``src/ainative/agent`` and then one more past ``src``.
    """

    skill_id = "ai-native-game-engine"

    def __init__(self, package_root: Path | None = None) -> None:
        # parents[0]=agent, [1]=ainative, [2]=src, [3]=repository root.
        self.package_root = package_root or Path(__file__).resolve().parents[3]

    def load(self, task: TaskContract) -> SkillSession:
        """Verify the package and open the guidance this task named.

        @param task: the Agent-authored task contract.
        @returns the loaded session.
        @throws SkillIntegrityError when the package or the named guidance is missing.
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

        guidance_document: Path | None = None
        if task.guidance:
            candidate = self.package_root / "guidance" / f"{task.guidance}.md"
            if not candidate.is_file():
                raise SkillIntegrityError(f"named guidance does not exist: {candidate}")
            candidate.read_text(encoding="utf-8")
            guidance_document = candidate

        return SkillSession(
            skill_id=self.skill_id,
            package_root=self.package_root,
            task=task,
            guidance=task.guidance,
            guidance_document=guidance_document,
        )
