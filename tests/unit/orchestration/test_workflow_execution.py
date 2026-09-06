import pytest

from ainative.agent import WorkflowGuide, WorkflowPlanError
from ainative.orchestration import RuntimeContext
from ainative.orchestration.contracts import (
    CheckResult,
    CheckStatus,
    ExecutionItemResult,
    StepPlan,
    TaskContract,
    TaskResult,
    TaskRoute,
    TaskStatus,
    ToolExecutionKind,
)
from ainative.registry import toolset_from_operations
from tests.support.plan_factory import (
    call,
    execute_local_tool_and_submit,
    one_stage_plan,
    plan_for,
    stage_plan,
)


class FakeUE5:
    executor_id = "fake-ue5"
    host_id = "ue5"

    def __init__(self, events, operations=("read_actor_transform", "set-actor-transform")):
        self.events = events
        self.location = [0.0, 0.0, 0.0]
        self.operations = operations

    def is_ready(self):
        return True

    def toolsets(self):
        return (
            toolset_from_operations(
                toolset_id="ue5.editor",
                provider_id=self.host_id,
                execution_kind=ToolExecutionKind.HOST,
                operations=self.operations,
            ),
        )

    def execute(self, request):
        self.events.append(request.operation)
        if request.operation == "set-actor-transform":
            self.location = list(request.parameters["expected_location"])
        return TaskResult(
            status=TaskStatus.SUCCEEDED,
            route=TaskRoute.HOST_OPERATION.value,
            details={"location": list(self.location), "actor": "Cube"},
        )


def actor_plan(task: TaskContract, *, include_read=True, include_set=True):
    calls = []
    previous = None
    if include_read:
        read = call("ue5.editor", "ue5", "read_actor_transform", "read-1")
        calls.append(read)
        previous = read.call_id
    if include_set:
        calls.append(
            call(
                "ue5.editor",
                "ue5",
                "set-actor-transform",
                "set-1",
                {"expected_location": [100, 200, 300]},
                depends_on=(previous,) if previous else (),
            )
        )
    return plan_for(
        task,
        (StepPlan("change", "Read and apply the Actor change", (stage_plan("stage.change", "Read and apply", "actor_transform", tuple(calls)),)),),
    )


def execute_agent_plan(guide: WorkflowGuide, task: TaskContract, plan, runtime):
    session = guide.start(task, plan, runtime)
    for stage in plan.workflow.stage_requests:
        for call_item in stage.calls:
            result = execute_local_tool_and_submit(session, stage, call_item)
            if result.status is not TaskStatus.SUCCEEDED:
                break
        session.complete_stage(stage.stage_id)
    return session.finish()


def test_agent_executes_selected_ue5_tools_only_when_agent_calls_them():
    events = []
    task = TaskContract(
        task_id="ue5-actor-stage",
        objective="Move an Actor in a UE5 level",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
    )
    ue5 = FakeUE5(events)
    plan = actor_plan(task)
    session = WorkflowGuide().start(task, plan, RuntimeContext(executors={"ue5": ue5}))

    assert session.ready
    assert events == []
    result = execute_local_tool_and_submit(session, plan.workflow.stage_requests[0], plan.workflow.stage_requests[0].calls[0])
    assert result.status is TaskStatus.SUCCEEDED
    assert events == ["read_actor_transform"]
    result2 = execute_local_tool_and_submit(session, plan.workflow.stage_requests[0], plan.workflow.stage_requests[0].calls[1])
    assert result2.status is TaskStatus.SUCCEEDED
    assert events == ["read_actor_transform", "set-actor-transform"]
    assert session.complete_stage("stage.change").status is TaskStatus.SUCCEEDED
    assert session.finish().status is TaskStatus.SUCCEEDED


def test_agent_plan_blocks_before_side_effect_when_a_later_selected_tool_is_missing():
    events = []
    task = TaskContract(
        task_id="ue5-missing-tool",
        objective="Move an Actor in a UE5 level",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
    )
    ue5 = FakeUE5(events, operations=("read_actor_transform",))
    plan = actor_plan(task)
    session = WorkflowGuide().start(task, plan, RuntimeContext(executors={"ue5": ue5}))

    assert not session.ready
    assert not session.ready
    assert session.finish().status is TaskStatus.BLOCKED
    assert events == []


def test_agent_calls_multiple_tools_in_one_stage_in_plan_order():
    events = []
    task = TaskContract(
        task_id="ue5-multi-tool-stage",
        objective="Read and move an Actor as one local goal",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
    )
    ue5 = FakeUE5(events)
    plan = actor_plan(task)
    session = WorkflowGuide().start(task, plan, RuntimeContext(executors={"ue5": ue5}))

    execute_local_tool_and_submit(session, plan.workflow.stage_requests[0], plan.workflow.stage_requests[0].calls[0])
    execute_local_tool_and_submit(session, plan.workflow.stage_requests[0], plan.workflow.stage_requests[0].calls[1])
    stage = session.complete_stage("stage.change")

    assert stage.status is TaskStatus.SUCCEEDED
    assert events == ["read_actor_transform", "set-actor-transform"]
    assert stage.call_ids == ("read-1", "set-1")


def test_agent_can_create_a_stage_with_no_calls_as_a_local_checkpoint():
    task = TaskContract(
        task_id="checkpoint-stage",
        objective="Record a checkpoint",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
    )
    plan = one_stage_plan(task, stage_plan("stage.checkpoint", "Record the checkpoint", "checkpoint"))
    session = WorkflowGuide().start(task, plan, RuntimeContext(executors={"ue5": FakeUE5([])}))
    session.record_execution_item(
        "stage.checkpoint",
        ExecutionItemResult("stage.checkpoint.executed", CheckStatus.PASS, reason="checkpoint recorded"),
    )
    session.record_check_result(
        "stage.checkpoint",
        CheckResult("stage.checkpoint.completed", CheckStatus.PASS, reason="checkpoint is present"),
    )

    assert session.complete_stage("stage.checkpoint").status is TaskStatus.SUCCEEDED
    assert session.finish().status is TaskStatus.SUCCEEDED


def test_agent_cannot_record_a_call_before_its_dependency():
    events = []
    task = TaskContract(
        task_id="dependency-order",
        objective="Read and move an Actor",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
    )
    plan = actor_plan(task)
    session = WorkflowGuide().start(task, plan, RuntimeContext(executors={"ue5": FakeUE5(events)}))
    stage = plan.workflow.stage_requests[0]

    with pytest.raises(WorkflowPlanError, match="incomplete dependencies"):
        session.check_call_ready(stage.calls[1].call_id)
    assert events == []



def test_agent_cannot_prepare_a_call_from_a_later_dependent_stage():
    events = []
    task = TaskContract(
        task_id="stage-dependency-order",
        objective="Read and move an Actor",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
    )
    first = stage_plan("stage.first", "Read", "read_actor_transform", (call("ue5.editor", "ue5", "read_actor_transform", "read"),))
    later_call = call("ue5.editor", "ue5", "set-actor-transform", "set", {"expected_location": [1, 2, 3]})
    later = stage_plan("stage.later", "Move", "set_actor_transform", (later_call,), depends_on=("stage.first",))
    plan = plan_for(task, (StepPlan("first", "Read", (first,)), StepPlan("later", "Move", (later,), depends_on=("first",))))
    session = WorkflowGuide().start(task, plan, RuntimeContext(executors={"ue5": FakeUE5(events)}))

    with pytest.raises(WorkflowPlanError, match="incomplete dependencies"):
        session.check_call_ready("set")
    assert events == []



def test_agent_cannot_overwrite_a_recorded_execution_attempt():
    events = []
    task = TaskContract(
        task_id="duplicate-result",
        objective="Read an Actor",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
    )
    plan = one_stage_plan(task, stage_plan("stage.read", "Read", "read_actor_transform", (call("ue5.editor", "ue5", "read_actor_transform", "read"),)))
    session = WorkflowGuide().start(task, plan, RuntimeContext(executors={"ue5": FakeUE5(events)}))
    result = execute_local_tool_and_submit(session, plan.workflow.stage_requests[0], plan.workflow.stage_requests[0].calls[0])

    with pytest.raises(WorkflowPlanError, match="already been recorded"):
        session.record_execution_result(result)
