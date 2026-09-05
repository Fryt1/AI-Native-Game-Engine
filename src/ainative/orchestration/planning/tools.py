from __future__ import annotations

from dataclasses import dataclass

from ainative.orchestration.contracts.plan import ExecutionPlan
from ainative.orchestration.contracts.tools import ToolCall
from ainative.registry import ToolResolutionError, ToolsetRegistry

from .lifecycle import validate_plan_structure


@dataclass(frozen=True, slots=True)
class ToolPlanIssue:
    """One exact project ToolCall that cannot be used."""

    call_id: str
    stage_id: str
    toolset_id: str
    tool_id: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "call_id": self.call_id,
            "stage_id": self.stage_id,
            "toolset_id": self.toolset_id,
            "tool_id": self.tool_id,
            "message": self.message,
        }


class ToolPlanError(RuntimeError):
    """The Agent plan contains a project ToolCall that is not executable."""

    def __init__(self, issues: tuple[ToolPlanIssue, ...]) -> None:
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues))


def check_workflow_tools(plan: ExecutionPlan, registry: ToolsetRegistry) -> tuple[ToolPlanIssue, ...]:
    """Check project ToolCalls without attempting any MCP connection."""

    validate_plan_structure(plan)
    issues: list[ToolPlanIssue] = []
    for stage in plan.workflow.stage_requests:
        for call in stage.calls:
            if not isinstance(call, ToolCall):
                continue
            try:
                registry.resolve_call(call)
            except ToolResolutionError as exc:
                issues.append(
                    ToolPlanIssue(
                        call_id=call.call_id,
                        stage_id=stage.stage_id,
                        toolset_id=call.toolset_id,
                        tool_id=call.tool_id,
                        message=f"{stage.stage_id}/{call.call_id}: {exc}",
                    )
                )
    return tuple(issues)


def check_tool_calls(calls: tuple[ToolCall, ...], registry: ToolsetRegistry) -> tuple[ToolPlanIssue, ...]:
    issues: list[ToolPlanIssue] = []
    for call in calls:
        try:
            registry.resolve_call(call)
        except ToolResolutionError as exc:
            issues.append(
                ToolPlanIssue(
                    call_id=call.call_id,
                    stage_id="",
                    toolset_id=call.toolset_id,
                    tool_id=call.tool_id,
                    message=f"{call.call_id}: {exc}",
                )
            )
    return tuple(issues)
