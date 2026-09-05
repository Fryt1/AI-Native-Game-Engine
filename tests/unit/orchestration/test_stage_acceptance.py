from __future__ import annotations

from ainative.agent import WorkflowGuide, WorkflowPlanError
from ainative.orchestration import RuntimeContext
from ainative.orchestration.contracts import (
    AcceptanceCheck,
    CheckOperator,
    CheckStatus,
    ExecutionChecklistItem,
    StageKind,
    StageRequest,
    StepPlan,
    TaskContract,
    TaskResult,
    TaskRoute,
    TaskStatus,
    ToolCallUsage,
    ToolExecutionKind,
)
from ainative.orchestration.planning import PlanIntegrityError, validate_plan_structure
from ainative.registry import toolset_from_operations
from tests.support.plan_factory import call, execute_local_tool_and_submit, plan_for


class FakeUE5:
    host_id = "ue5"

    def __init__(self, *, location=None, degraded=False):
        self.location = list(location or [0, 0, 0])
        self.degraded = degraded
        self.calls = []

    def is_ready(self):
        return True

    def toolsets(self):
        return (
            toolset_from_operations(
                toolset_id="ue5.editor",
                provider_id="ue5",
                execution_kind=ToolExecutionKind.HOST,
                operations=("set_actor_transform", "read_actor_transform"),
            ),
        )

    def execute(self, request):
        self.calls.append(request.operation)
        if request.operation == "set_actor_transform":
            self.location = list(request.parameters["location"])
        return TaskResult(
            status=TaskStatus.DEGRADED if self.degraded else TaskStatus.SUCCEEDED,
            route=TaskRoute.HOST_OPERATION.value,
            details={"location": list(self.location)},
            warnings=("non-blocking warning",) if self.degraded else (),
        )


def _task(task_id: str) -> TaskContract:
    return TaskContract(
        task_id=task_id,
        objective="Move and verify an Actor",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
    )


def test_tool_success_does_not_complete_stage_without_acceptance_evidence():
    task = _task("missing-acceptance-evidence")
    mutate = call(
        "ue5.editor",
        "ue5",
        "set_actor_transform",
        "mutate-1",
        {"location": [1, 2, 3]},
        usage=ToolCallUsage.EXECUTE,
    )
    stage = StageRequest(
        stage_id="stage.change",
        purpose="Move the Actor",
        operation="set_actor_transform",
        calls=(mutate,),
        stage_kind=StageKind.CHANGE,
        execution_checklist=(
            ExecutionChecklistItem("mutation_called", "The mutation Tool was executed", call_ids=(mutate.call_id,)),
        ),
        acceptance_checklist=(
            AcceptanceCheck(
                "location_verified",
                "The final location matches the requested location",
                operator=CheckOperator.MANUAL,
            ),
        ),
    )
    plan = plan_for(task, (StepPlan("change", "Change", (stage,)),))
    session = WorkflowGuide().start(task, plan, RuntimeContext(ue5=FakeUE5()))

    mutate_result = execute_local_tool_and_submit(session, stage, mutate)
    assert mutate_result.status is TaskStatus.SUCCEEDED
    result = session.complete_stage("stage.change")

    assert result.status is TaskStatus.BLOCKED
    assert result.execution_item_results[0].status is CheckStatus.PASS
    assert result.check_results[0].status is CheckStatus.UNKNOWN
    assert "stage.change" not in session.completed_stage_ids


def test_readback_check_deterministically_completes_the_stage():
    task = _task("readback-acceptance")
    mutate = call(
        "ue5.editor",
        "ue5",
        "set_actor_transform",
        "mutate-1",
        {"location": [1, 2, 3]},
        usage=ToolCallUsage.EXECUTE,
    )
    readback = call(
        "ue5.editor",
        "ue5",
        "read_actor_transform",
        "verify-1",
        depends_on=(mutate.call_id,),
        usage=ToolCallUsage.VERIFY,
    )
    stage = StageRequest(
        stage_id="stage.change",
        purpose="Move and verify the Actor",
        operation="actor_transform",
        calls=(mutate, readback),
        stage_kind=StageKind.CHANGE,
        execution_checklist=(
            ExecutionChecklistItem("mutation_called", "The mutation Tool was executed", call_ids=(mutate.call_id,)),
        ),
        acceptance_checklist=(
            AcceptanceCheck(
                "location_matches",
                "Read-back location equals the requested location",
                source_call_id=readback.call_id,
                actual_path=("location",),
                operator=CheckOperator.EQUALS,
                expected=[1, 2, 3],
            ),
        ),
    )
    plan = plan_for(task, (StepPlan("change", "Change", (stage,)),))
    host = FakeUE5()
    session = WorkflowGuide().start(task, plan, RuntimeContext(ue5=host))

    execute_local_tool_and_submit(session, stage, mutate)
    execute_local_tool_and_submit(session, stage, readback)
    result = session.complete_stage("stage.change")

    assert result.status is TaskStatus.SUCCEEDED
    assert result.check_results[0].status is CheckStatus.PASS
    assert result.acceptance_summary.passed == 1
    assert session.finish().status is TaskStatus.SUCCEEDED
    assert host.calls == ["set_actor_transform", "read_actor_transform"]


def test_required_warning_completes_stage_as_degraded():
    task = _task("warn-acceptance")
    observe = call(
        "ue5.editor",
        "ue5",
        "read_actor_transform",
        "observe-1",
        usage=ToolCallUsage.VERIFY,
    )
    stage = StageRequest(
        stage_id="stage.inspect",
        purpose="Inspect the Actor",
        operation="read_actor_transform",
        calls=(observe,),
        stage_kind=StageKind.INVESTIGATION,
        execution_checklist=(
            ExecutionChecklistItem("state_read", "The state was read", call_ids=(observe.call_id,)),
        ),
        acceptance_checklist=(
            AcceptanceCheck(
                "read_completed",
                "The read Tool completed",
                source_call_id=observe.call_id,
                operator=CheckOperator.TOOL_SUCCEEDED,
            ),
        ),
    )
    plan = plan_for(task, (StepPlan("inspect", "Inspect", (stage,)),))
    session = WorkflowGuide().start(task, plan, RuntimeContext(ue5=FakeUE5(degraded=True)))

    execute_local_tool_and_submit(session, stage, observe)
    stage_result = session.complete_stage("stage.inspect")

    assert stage_result.status is TaskStatus.DEGRADED
    assert stage_result.check_results[0].status is CheckStatus.WARN
    assert session.finish().status is TaskStatus.DEGRADED


def test_required_stage_checklists_are_validated_before_execution():
    task = _task("missing-checklists")
    selected = call("ue5.editor", "ue5", "read_actor_transform", "read-1")
    plan = plan_for(
        task,
        (StepPlan("inspect", "Inspect", (StageRequest("stage.inspect", "Inspect", "read", (selected,)),)),),
    )

    try:
        validate_plan_structure(plan)
    except PlanIntegrityError as exc:
        locations = {issue.location for issue in exc.issues}
        assert "stage:stage.inspect.execution_checklist" in locations
        assert "stage:stage.inspect.acceptance_checklist" in locations
    else:
        raise AssertionError("a required Stage without checklists was accepted")


def test_tool_call_usage_is_per_call_metadata_not_a_tool_role():
    selected = call(
        "ue5.editor",
        "ue5",
        "read_actor_transform",
        "verify-1",
        usage=ToolCallUsage.VERIFY,
    )

    assert selected.usage is ToolCallUsage.VERIFY
    assert selected.to_dict()["usage"] == "verify"


def test_agent_cannot_override_a_deterministic_acceptance_check():
    task = _task("no-check-override")
    observe = call(
        "ue5.editor",
        "ue5",
        "read_actor_transform",
        "verify-1",
        usage=ToolCallUsage.VERIFY,
    )
    stage = StageRequest(
        stage_id="stage.verify",
        purpose="Verify the Actor",
        calls=(observe,),
        stage_kind=StageKind.INVESTIGATION,
        execution_checklist=(
            ExecutionChecklistItem("read", "Read the Actor", call_ids=(observe.call_id,)),
        ),
        acceptance_checklist=(
            AcceptanceCheck(
                "location",
                "Location matches",
                source_call_id=observe.call_id,
                operator=CheckOperator.EQUALS,
                actual_path=("location",),
                expected=[0, 0, 0],
            ),
        ),
    )
    session = WorkflowGuide().start(
        task,
        plan_for(task, (StepPlan("verify", "Verify", (stage,)),)),
        RuntimeContext(ue5=FakeUE5()),
    )

    try:
        session.record_check_result(
            "stage.verify",
            __import__("ainative.orchestration.contracts", fromlist=["CheckResult"]).CheckResult(
                "location",
                CheckStatus.PASS,
                evidence_refs=("tool-result:verify-1",),
            ),
        )
    except WorkflowPlanError as exc:
        assert "cannot be overridden" in str(exc)
    else:
        raise AssertionError("a deterministic check was overridden")


def test_agent_cannot_override_tool_backed_execution_evidence():
    task = _task("no-execution-override")
    mutate = call("ue5.editor", "ue5", "set_actor_transform", "mutate-1", {"location": [1, 2, 3]})
    stage = StageRequest(
        stage_id="stage.change",
        purpose="Change the Actor",
        calls=(mutate,),
        execution_checklist=(
            ExecutionChecklistItem("mutation", "Mutation ran", call_ids=(mutate.call_id,)),
        ),
        acceptance_checklist=(
            AcceptanceCheck(
                "mutation_call",
                "Mutation Tool completed",
                source_call_id=mutate.call_id,
                operator=CheckOperator.TOOL_SUCCEEDED,
            ),
        ),
    )
    session = WorkflowGuide().start(
        task,
        plan_for(task, (StepPlan("change", "Change", (stage,)),)),
        RuntimeContext(ue5=FakeUE5()),
    )

    try:
        session.record_execution_item(
            "stage.change",
            __import__("ainative.orchestration.contracts", fromlist=["ExecutionItemResult"]).ExecutionItemResult(
                "mutation",
                CheckStatus.PASS,
                evidence_refs=("invented",),
            ),
        )
    except WorkflowPlanError as exc:
        assert "cannot be overridden" in str(exc)
    else:
        raise AssertionError("Tool-backed execution evidence was overridden")
