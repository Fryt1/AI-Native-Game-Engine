from __future__ import annotations

from dataclasses import dataclass, replace

from ainative.orchestration.contracts.plan import ExecutionPlan, WorkflowPlanStatus
from ainative.orchestration.contracts.tools import McpCall, ToolCall


@dataclass(frozen=True, slots=True)
class PlanIntegrityIssue:
    """One structural problem detected before an Agent-authored plan runs."""

    location: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"location": self.location, "message": self.message}


class PlanIntegrityError(RuntimeError):
    """The Agent-authored Workflow Plan is structurally invalid."""

    def __init__(self, issues: tuple[PlanIntegrityIssue, ...]) -> None:
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues))


def validate_plan_structure(plan: ExecutionPlan) -> None:
    """Fail closed on plan, call, checklist, and dependency structure."""

    issues: list[PlanIntegrityIssue] = []
    steps = plan.workflow.steps
    step_ids = [step.step_id for step in steps]
    if len(step_ids) != len(set(step_ids)):
        issues.append(PlanIntegrityIssue("workflow.steps", "Step IDs must be unique"))

    known_steps: set[str] = set()
    known_stages: set[str] = set()
    known_calls: set[str] = set()
    for step in steps:
        for dependency in step.depends_on:
            if dependency not in known_steps:
                issues.append(
                    PlanIntegrityIssue(
                        f"step:{step.step_id}.depends_on",
                        f"Step {step.step_id} depends on a Step that is not earlier: {dependency}",
                    )
                )
        for stage in step.stages:
            if stage.stage_id in known_stages:
                issues.append(PlanIntegrityIssue(f"stage:{stage.stage_id}", "Stage IDs must be unique"))
            for dependency in stage.depends_on:
                if dependency not in known_stages:
                    issues.append(
                        PlanIntegrityIssue(
                            f"stage:{stage.stage_id}.depends_on",
                            f"Stage {stage.stage_id} depends on a Stage that is not earlier: {dependency}",
                        )
                    )

            if stage.required and not stage.execution_checklist:
                issues.append(
                    PlanIntegrityIssue(
                        f"stage:{stage.stage_id}.execution_checklist",
                        "A required Stage must freeze an execution checklist before execution",
                    )
                )
            if stage.required and not stage.acceptance_checklist:
                issues.append(
                    PlanIntegrityIssue(
                        f"stage:{stage.stage_id}.acceptance_checklist",
                        "A required Stage must freeze an acceptance checklist before execution",
                    )
                )

            execution_ids = [item.item_id for item in stage.execution_checklist]
            if len(execution_ids) != len(set(execution_ids)):
                issues.append(
                    PlanIntegrityIssue(
                        f"stage:{stage.stage_id}.execution_checklist",
                        "Execution checklist item IDs must be unique inside a Stage",
                    )
                )
            acceptance_ids = [check.check_id for check in stage.acceptance_checklist]
            if len(acceptance_ids) != len(set(acceptance_ids)):
                issues.append(
                    PlanIntegrityIssue(
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
                        PlanIntegrityIssue(
                            f"stage:{stage.stage_id}.execution_checklist",
                            "Execution checklist items need item_id and description",
                        )
                    )
                referenced_calls.update(item.call_ids)
                missing = set(item.call_ids) - stage_call_ids
                if missing:
                    issues.append(
                        PlanIntegrityIssue(
                            f"execution-item:{item.item_id}.call_ids",
                            "Execution checklist references calls outside its Stage: " + ", ".join(sorted(missing)),
                        )
                    )
            for check in stage.acceptance_checklist:
                if not check.check_id or not check.description:
                    issues.append(
                        PlanIntegrityIssue(
                            f"stage:{stage.stage_id}.acceptance_checklist",
                            "Acceptance checks need check_id and description",
                        )
                    )
                referenced_calls.update(check.referenced_call_ids)
                missing = set(check.referenced_call_ids) - stage_call_ids
                if missing:
                    issues.append(
                        PlanIntegrityIssue(
                            f"acceptance-check:{check.check_id}.call_ids",
                            "Acceptance check references calls outside its Stage: " + ", ".join(sorted(missing)),
                        )
                    )

            unreferenced = stage_call_ids - referenced_calls
            if unreferenced:
                issues.append(
                    PlanIntegrityIssue(
                        f"stage:{stage.stage_id}.calls",
                        "Every Stage call must support an execution or acceptance checklist item: "
                        + ", ".join(sorted(unreferenced)),
                    )
                )

            for call in stage.calls:
                call_id = getattr(call, "call_id", None)
                if isinstance(call, ToolCall):
                    valid = bool(call_id and call.toolset_id and call.tool_id)
                    message = "ToolCall needs call_id, toolset_id, and tool_id"
                elif isinstance(call, McpCall):
                    valid = bool(call_id and call.server_id and call.tool_name)
                    message = "McpCall needs call_id, server_id, and tool_name"
                else:
                    valid = False
                    message = "Stage calls must be ToolCall or McpCall"
                if not valid:
                    issues.append(PlanIntegrityIssue(f"stage:{stage.stage_id}.calls", message))
                if not call_id:
                    continue
                if call_id in known_calls:
                    issues.append(
                        PlanIntegrityIssue(
                            f"call:{call_id}",
                            "Call IDs must be unique across the complete Workflow Plan",
                        )
                    )
                for dependency in getattr(call, "depends_on", ()):
                    if dependency not in known_calls:
                        issues.append(
                            PlanIntegrityIssue(
                                f"call:{call_id}.depends_on",
                                f"Call {call_id} depends on a call that is not earlier: {dependency}",
                            )
                        )
                known_calls.add(call_id)
            known_stages.add(stage.stage_id)
        known_steps.add(step.step_id)

    if issues:
        raise PlanIntegrityError(tuple(issues))


def with_plan_status(plan: ExecutionPlan, status: WorkflowPlanStatus) -> ExecutionPlan:
    return replace(plan, workflow=replace(plan.workflow, status=status))


def supersede_plan(plan: ExecutionPlan, reason: str) -> ExecutionPlan:
    return replace(
        plan,
        workflow=replace(
            plan.workflow,
            status=WorkflowPlanStatus.SUPERSEDED,
            replan_reason=reason,
        ),
    )


def replan_plan(previous_plan: ExecutionPlan, replacement_plan: ExecutionPlan, reason: str) -> ExecutionPlan:
    previous_workflow = previous_plan.workflow
    replacement_workflow = replacement_plan.workflow
    plan_id = previous_workflow.plan_id or replacement_workflow.plan_id
    workflow = replace(
        replacement_workflow,
        plan_id=plan_id,
        revision=previous_workflow.revision + 1,
        status=WorkflowPlanStatus.DRAFT,
        supersedes_plan_id=previous_workflow.revision_id,
        replan_reason=reason,
    )
    revised = replace(replacement_plan, workflow=workflow)
    validate_plan_structure(revised)
    return revised
