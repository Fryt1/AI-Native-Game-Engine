from __future__ import annotations

from dataclasses import dataclass, replace

from ainative.model.workflow import Workflow, WorkflowStatus


@dataclass(frozen=True, slots=True)
class WorkflowIntegrityIssue:
    """One structural problem detected before an Agent-authored Workflow runs."""

    location: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"location": self.location, "message": self.message}


class WorkflowIntegrityError(RuntimeError):
    """The Agent-authored Workflow is structurally invalid."""

    def __init__(self, issues: tuple[WorkflowIntegrityIssue, ...]) -> None:
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues))


def validate_workflow_structure(workflow: Workflow) -> None:
    """Fail closed on workflow, call, checklist, and dependency structure."""

    issues: list[WorkflowIntegrityIssue] = []
    steps = workflow.steps
    step_ids = [step.step_id for step in steps]
    if len(step_ids) != len(set(step_ids)):
        issues.append(WorkflowIntegrityIssue("workflow.steps", "Step IDs must be unique"))

    known_steps: set[str] = set()
    known_stages: set[str] = set()
    known_calls: set[str] = set()
    for step in steps:
        for dependency in step.depends_on:
            if dependency not in known_steps:
                issues.append(
                    WorkflowIntegrityIssue(
                        f"step:{step.step_id}.depends_on",
                        f"Step {step.step_id} depends on a Step that is not earlier: {dependency}",
                    )
                )
        for stage in step.stages:
            if stage.stage_id in known_stages:
                issues.append(WorkflowIntegrityIssue(f"stage:{stage.stage_id}", "Stage IDs must be unique"))
            for dependency in stage.depends_on:
                if dependency not in known_stages:
                    issues.append(
                        WorkflowIntegrityIssue(
                            f"stage:{stage.stage_id}.depends_on",
                            f"Stage {stage.stage_id} depends on a Stage that is not earlier: {dependency}",
                        )
                    )

            if stage.required and not stage.execution_checklist:
                issues.append(
                    WorkflowIntegrityIssue(
                        f"stage:{stage.stage_id}.execution_checklist",
                        "A required Stage must freeze an execution checklist before execution",
                    )
                )
            if stage.required and not stage.acceptance_checklist:
                issues.append(
                    WorkflowIntegrityIssue(
                        f"stage:{stage.stage_id}.acceptance_checklist",
                        "A required Stage must freeze an acceptance checklist before execution",
                    )
                )

            execution_ids = [item.item_id for item in stage.execution_checklist]
            if len(execution_ids) != len(set(execution_ids)):
                issues.append(
                    WorkflowIntegrityIssue(
                        f"stage:{stage.stage_id}.execution_checklist",
                        "Execution checklist item IDs must be unique inside a Stage",
                    )
                )
            acceptance_ids = [check.check_id for check in stage.acceptance_checklist]
            if len(acceptance_ids) != len(set(acceptance_ids)):
                issues.append(
                    WorkflowIntegrityIssue(
                        f"stage:{stage.stage_id}.acceptance_checklist",
                        "Acceptance check IDs must be unique inside a Stage",
                    )
                )

            stage_call_ids = {
                call_id
                for call in stage.calls
                if (call_id := getattr(call, "call_id", None))
            }
            referenced_calls: set[str] = set()
            for item in stage.execution_checklist:
                if not item.item_id or not item.description:
                    issues.append(
                        WorkflowIntegrityIssue(
                            f"stage:{stage.stage_id}.execution_checklist",
                            "Execution checklist items need item_id and description",
                        )
                    )
                referenced_calls.update(item.call_ids)
                missing = set(item.call_ids) - stage_call_ids
                if missing:
                    issues.append(
                        WorkflowIntegrityIssue(
                            f"execution-item:{item.item_id}.call_ids",
                            "Execution checklist references calls outside its Stage: " + ", ".join(sorted(missing)),
                        )
                    )
            for check in stage.acceptance_checklist:
                if not check.check_id or not check.description:
                    issues.append(
                        WorkflowIntegrityIssue(
                            f"stage:{stage.stage_id}.acceptance_checklist",
                            "Acceptance checks need check_id and description",
                        )
                    )
                referenced_calls.update(check.referenced_call_ids)
                missing = set(check.referenced_call_ids) - stage_call_ids
                if missing:
                    issues.append(
                        WorkflowIntegrityIssue(
                            f"acceptance-check:{check.check_id}.call_ids",
                            "Acceptance check references calls outside its Stage: " + ", ".join(sorted(missing)),
                        )
                    )

            unreferenced = stage_call_ids - referenced_calls
            if unreferenced:
                issues.append(
                    WorkflowIntegrityIssue(
                        f"stage:{stage.stage_id}.calls",
                        "Every Stage call must support an execution or acceptance checklist item: "
                        + ", ".join(sorted(unreferenced)),
                    )
                )

            for call in stage.calls:
                call_id = getattr(call, "call_id", None)
                target = getattr(call, "target", None)
                valid = bool(call_id and target and target.owner and target.name)
                if not valid:
                    issues.append(
                        WorkflowIntegrityIssue(
                            f"stage:{stage.stage_id}.calls",
                            "ToolCall needs call_id and a target with an owner and a name",
                        )
                    )
                if not call_id:
                    continue
                if call_id in known_calls:
                    issues.append(
                        WorkflowIntegrityIssue(
                            f"call:{call_id}",
                            "Call IDs must be unique across the complete Workflow",
                        )
                    )
                for dependency in getattr(call, "depends_on", ()):
                    if dependency not in known_calls:
                        issues.append(
                            WorkflowIntegrityIssue(
                                f"call:{call_id}.depends_on",
                                f"Call {call_id} depends on a call that is not earlier: {dependency}",
                            )
                        )
                known_calls.add(call_id)
            known_stages.add(stage.stage_id)
        known_steps.add(step.step_id)

    if issues:
        raise WorkflowIntegrityError(tuple(issues))


def with_workflow_status(workflow: Workflow, status: WorkflowStatus) -> Workflow:
    return replace(workflow, status=status)


def supersede_workflow(workflow: Workflow, reason: str) -> Workflow:
    return replace(workflow, status=WorkflowStatus.SUPERSEDED, replacement_reason=reason)


def replan_workflow(previous_plan: Workflow, replacement_plan: Workflow, reason: str) -> Workflow:
    workflow_id = previous_plan.workflow_id or replacement_plan.workflow_id
    revised = replace(
        replacement_plan,
        workflow_id=workflow_id,
        revision=previous_plan.revision + 1,
        status=WorkflowStatus.DRAFT,
        supersedes_workflow_id=previous_plan.revision_id,
        replacement_reason=reason,
    )
    validate_workflow_structure(revised)
    return revised
