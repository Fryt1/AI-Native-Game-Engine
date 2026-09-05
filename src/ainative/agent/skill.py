from dataclasses import dataclass
from pathlib import Path

from ainative.orchestration.contracts.plan import WorkflowSelection
from ainative.orchestration.contracts.task import TaskContract
from ainative.orchestration.planning import select_workflow


class SkillIntegrityError(RuntimeError):
    """The Skill package cannot be safely loaded."""


@dataclass(frozen=True, slots=True)
class SkillSession:
    """Loaded Skill guidance for one task, before the Agent authors a plan."""

    skill_id: str
    package_root: Path
    task: TaskContract
    selection: WorkflowSelection
    selection_document: Path
    workflow_document: Path
    knowledge_index_document: Path
    plan_template_document: Path
    plan_schema_document: Path

    @property
    def knowledge_root(self) -> Path:
        return self.package_root / "knowledge"

    @property
    def route(self):
        return self.selection.route

    @property
    def workflow_id(self) -> str:
        return self.selection.workflow_id

    @property
    def profile(self) -> str:
        return self.selection.profile


class AINativeWorkflowSkill:
    """Entry point for loading Skill and Workflow guidance.

    Loading a Skill selects only a coarse Route/Workflow context. The concrete
    Steps, Stages, and Tool Calls are authored by the Agent after it reads the
    selected documents and discovers the live Toolsets.
    """

    skill_id = "ai-native-workflow-orchestration"

    def __init__(self, package_root: Path | None = None) -> None:
        self.package_root = package_root or Path(__file__).parents[3] / "skills" / self.skill_id

    def load(self, task: TaskContract) -> SkillSession:
        import sys
        from importlib.util import module_from_spec, spec_from_file_location

        gate_path = self.package_root / "scripts" / "integrity_gate.py"
        spec = spec_from_file_location("ainative_skill_integrity_gate", gate_path)
        if spec is None or spec.loader is None:
            raise SkillIntegrityError(f"integrity gate is missing: {gate_path}")
        module = module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        report = module.check_package(self.package_root)
        if not report.ok:
            raise SkillIntegrityError("missing Skill files: " + ", ".join(report.missing))

        selection = select_workflow(task)
        workflow_documents = {
            "host-operation": "host-operation.md",
            "native-blender-operation": "native-blender-operation.md",
            "asset-edit": "asset-edit.md",
            "asset-roundtrip": "asset-roundtrip.md",
            "provider-artifact-apply": "provider-artifact-apply.md",
        }
        selection_document = self.package_root / "workflows" / "workflow-selection.md"
        workflow_name = workflow_documents.get(selection.workflow_id)
        if workflow_name is None:
            raise SkillIntegrityError(f"no Workflow document mapped for selection: {selection.workflow_id}")
        workflow_document = self.package_root / "workflows" / workflow_name
        knowledge_index_document = self.package_root / "knowledge" / "index.md"
        plan_template_document = self.package_root / "templates" / "workflow-plan-template.md"
        plan_schema_document = self.package_root / "templates" / "workflow-plan-schema.json"
        required_documents = (
            selection_document,
            workflow_document,
            knowledge_index_document,
            plan_template_document,
            plan_schema_document,
        )
        if any(not document.is_file() for document in required_documents):
            raise SkillIntegrityError("selected Workflow, knowledge, or plan contract is missing")

        # The Skill host verifies guidance and stable plan contracts. It does not
        # interpret them into a fixed executable plan.
        for document in required_documents:
            document.read_text(encoding="utf-8")
        return SkillSession(
            self.skill_id,
            self.package_root,
            task,
            selection,
            selection_document,
            workflow_document,
            knowledge_index_document,
            plan_template_document,
            plan_schema_document,
        )
