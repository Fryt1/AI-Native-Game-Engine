"""The session's own invariants: evidence recording, dependencies, and closure."""

import pytest

from ainative.model import (
    AcceptanceCheck,
    CallTarget,
    CheckOperator,
    CheckResult,
    CheckStatus,
    ExecutionChecklistItem,
    ExecutionItemResult,
    ExecutionResult,
    NodeCheck,
    NodeKind,
    StageBody,
    StageKind,
    TaskContract,
    TaskStatus,
    WorkflowNode,
)
from ainative.session_api import AcceptanceGuide, WorkflowError
from tests.support.workflow_factory import (
    call,
    first_stage,
    first_stage_path,
    one_stage_workflow,
    stage_spec,
    step,
    submit_call_result,
    workflow_for,
)


def host_task(task_id: str = "ue5-actor-stage") -> TaskContract:
    return TaskContract(
        task_id=task_id,
        objective="Move an Actor in a UE5 level",
    )


def actor_plan(task: TaskContract, *, include_read=True, include_set=True):
    """A workflow declaring two UE5 MCP calls the Agent will make itself."""

    calls = []
    previous = None
    if include_read:
        read = call("ue5", "get_actor_transform", "read-1")
        calls.append(read)
        previous = read.call_id
    if include_set:
        calls.append(
            call(
                "ue5",
                "set_actor_transform",
                "set-1",
                {"expected_location": [100, 200, 300]},
                depends_on=(previous,) if previous else (),
            )
        )
    return workflow_for(
        task,
        (step("change", "Read and apply the Actor change", (stage_spec("stage.change", "Read and apply", "actor_transform", tuple(calls)),)),),
    )


def test_a_host_mcp_call_is_accepted_in_the_plan():
    """Host calls are the main work, so they must be declarable."""

    task = host_task()
    workflow = actor_plan(task)
    session = AcceptanceGuide().start(task, workflow)

    assert session.ready
    assert [c.target.name for c in workflow.calls] == ["get_actor_transform", "set_actor_transform"]


def test_opening_a_plan_executes_nothing():
    seen = []
    task = host_task()
    session = AcceptanceGuide().start(task, actor_plan(task))

    assert session.ready
    assert seen == []
    assert session.completed_call_ids == ()


def test_agent_reports_each_mcp_call_and_the_stage_closes():
    task = host_task()
    workflow = actor_plan(task)
    session = AcceptanceGuide().start(task, workflow)
    stage = first_stage(workflow)

    for declared in stage.declared_calls:
        result = submit_call_result(session, declared, TaskStatus.SUCCEEDED, outputs={"actor": "Cube"})
        assert result.status is TaskStatus.SUCCEEDED

    assert session.completed_call_ids == ("read-1", "set-1")
    assert session.complete_node(first_stage_path(workflow)).status is TaskStatus.SUCCEEDED
    assert session.finish().status is TaskStatus.SUCCEEDED


def test_a_call_cannot_be_recorded_before_its_declared_dependency():
    task = host_task("dependency-order")
    workflow = actor_plan(task)
    session = AcceptanceGuide().start(task, workflow)
    set_call = first_stage(workflow).declared_calls[1]

    with pytest.raises(WorkflowError, match="incomplete dependencies"):
        submit_call_result(session, set_call)


def test_a_result_for_a_call_the_plan_never_declared_is_rejected():
    task = host_task("undeclared")
    session = AcceptanceGuide().start(task, actor_plan(task))
    undeclared = call("ue5", "delete_everything", "not-declared")

    with pytest.raises(WorkflowError, match="not declared in the Workflow"):
        session.record_execution_result(
            ExecutionResult(
                call_id=undeclared.call_id,
                status=TaskStatus.SUCCEEDED,
                        target=undeclared.target,
            )
        )



def test_a_result_whose_target_contradicts_the_declaration_is_rejected():
    task = host_task("target-mismatch")
    workflow = actor_plan(task, include_set=False)
    session = AcceptanceGuide().start(task, workflow)
    declared = first_stage(workflow).declared_calls[0]

    mismatch = ExecutionResult(
        call_id=declared.call_id,
        status=TaskStatus.SUCCEEDED,
        target=CallTarget(owner="ue5", name="some_other_tool"),
    )
    with pytest.raises(WorkflowError, match="target mismatch"):
        session.record_execution_result(mismatch)


def test_a_call_id_two_nodes_declare_must_be_bound_by_the_node_path():
    """A call id is scoped to its STAGE, so two subtrees may each declare one.

    Binding a result to the wrong subtree would judge a node the Agent never
    touched, so an ambiguous id is refused rather than resolved by picking one.
    """

    task = host_task("ambiguous-call")
    shared = "get_actor_transform"
    left = stage_spec("stage.left", "Left", "read", (call("ue5", shared, "shared"),))
    right = stage_spec("stage.right", "Right", "read", (call("ue5", shared, "shared"),))
    workflow = workflow_for(task, (step("work", "Two subtrees", (left, right)),))
    session = AcceptanceGuide().start(task, workflow)
    first, second = workflow.stage_paths

    def reported() -> ExecutionResult:
        return ExecutionResult(
            call_id="shared",
            status=TaskStatus.SUCCEEDED,
            target=CallTarget(owner="ue5", name=shared),
        )

    with pytest.raises(WorkflowError, match="declared by more than one node"):
        session.record_execution_result(reported())

    # Named outright, the same call id records once for each declaring node.
    assert session.record_execution_result(reported(), node_path=first).call_id == "shared"
    assert session.record_execution_result(reported(), node_path=second).call_id == "shared"


def test_the_same_call_cannot_be_recorded_twice():
    task = host_task("no-overwrite")
    workflow = actor_plan(task, include_set=False)
    session = AcceptanceGuide().start(task, workflow)
    declared = first_stage(workflow).declared_calls[0]
    submit_call_result(session, declared)

    with pytest.raises(WorkflowError, match="already been recorded"):
        submit_call_result(session, declared)


def call_free_stage(node_id: str, purpose: str) -> WorkflowNode:
    """A STAGE whose work is captured entirely by its own checklists.

    A required STAGE must declare at least one call, so a local checkpoint that
    declares none is an optional node -- while its execution item and its manual
    acceptance check stay required, so the node is still judged on them.
    """

    return WorkflowNode(
        node_id=node_id,
        kind=NodeKind.STAGE,
        purpose=purpose,
        required=False,
        stage=StageBody(
            stage_kind=StageKind.INVESTIGATION,
            calls=(),
            execution_checklist=(
                ExecutionChecklistItem(
                    item_id=f"{node_id}.executed",
                    description=f"Required work for {purpose}",
                    call_ids=(),
                ),
            ),
            acceptance_checklist=(
                NodeCheck(AcceptanceCheck(
                    check_id=f"{node_id}.completed",
                    description=f"Completion evidence for {purpose}",
                    operator=CheckOperator.MANUAL,
                )),
            ),
        ),
    )


def test_a_stage_with_no_calls_closes_once_its_items_are_submitted():
    task = host_task("local-checkpoint")
    stage = call_free_stage("stage.checkpoint", "A local checkpoint")
    workflow = one_stage_workflow(task, stage)
    session = AcceptanceGuide().start(task, workflow)
    path = first_stage_path(workflow)

    session.record_execution_item(
        path,
        ExecutionItemResult(
            item_id=stage.stage.execution_checklist[0].item_id,
            status=CheckStatus.PASS,
            evidence_refs=("note:1",),
        ),
    )
    session.record_check_result(
        path,
        CheckResult(
            check_id=stage.declared_checks[0].check_id,
            status=CheckStatus.PASS,
            evidence_refs=("note:1",),
        ),
    )

    assert session.complete_node(path).status is TaskStatus.SUCCEEDED


def test_a_manual_check_needs_a_recorded_result():
    task = host_task("manual-evidence")
    stage = call_free_stage("stage.manual", "Manual check")
    workflow = one_stage_workflow(task, stage)
    session = AcceptanceGuide().start(task, workflow)
    path = first_stage_path(workflow)

    before = session.complete_node(path)
    assert before.status is TaskStatus.BLOCKED
    assert before.check_results[0].status is CheckStatus.UNKNOWN

    session.record_execution_item(
        path,
        ExecutionItemResult(
            item_id=stage.stage.execution_checklist[0].item_id,
            status=CheckStatus.PASS,
            evidence_refs=("note:1",),
        ),
    )
    session.record_check_result(
        path,
        CheckResult(
            check_id=stage.declared_checks[0].check_id,
            status=CheckStatus.PASS,
            evidence_refs=("note:1",),
        ),
    )
    assert session.complete_node(path).status is TaskStatus.SUCCEEDED


def test_a_deterministic_check_cannot_be_overridden_by_the_agent():
    task = host_task("no-override")
    workflow = actor_plan(task, include_set=False)
    session = AcceptanceGuide().start(task, workflow)
    declared = first_stage(workflow).declared_calls[0]
    node_id = first_stage(workflow).node_id
    path = first_stage_path(workflow)

    with pytest.raises(WorkflowError, match="cannot be overridden"):
        session.record_check_result(
            path,
            CheckResult(check_id=f"{node_id}.completed", status=CheckStatus.PASS),
        )
    assert declared is not None


def test_execution_items_derived_from_calls_cannot_be_overridden():
    task = host_task("no-item-override")
    workflow = actor_plan(task, include_set=False)
    session = AcceptanceGuide().start(task, workflow)
    node_id = first_stage(workflow).node_id
    path = first_stage_path(workflow)

    with pytest.raises(WorkflowError, match="cannot be overridden"):
        session.record_execution_item(
            path,
            ExecutionItemResult(item_id=f"{node_id}.executed", status=CheckStatus.PASS),
        )


def test_a_call_from_a_later_dependent_stage_cannot_run_early():
    task = host_task("stage-order")
    first = stage_spec("stage.first", "First", "read", (call("ue5", "get_actor_transform", "c1"),))
    second = stage_spec(
        "stage.second",
        "Second",
        "write",
        (call("ue5", "set_actor_transform", "c2"),),
        depends_on=("../stage.first",),
    )
    workflow = workflow_for(task, (step("work", "Two stages", (first, second)),))
    session = AcceptanceGuide().start(task, workflow)

    with pytest.raises(WorkflowError, match="incomplete dependencies"):
        submit_call_result(session, second.declared_calls[0])


def test_closing_a_stage_out_of_order_is_blocked_not_silently_allowed():
    task = host_task("close-order")
    first = stage_spec("stage.first", "First", "read", (call("ue5", "get_actor_transform", "c1"),))
    second = stage_spec(
        "stage.second",
        "Second",
        "write",
        (call("ue5", "set_actor_transform", "c2"),),
        depends_on=("../stage.first",),
    )
    workflow = workflow_for(task, (step("work", "Two stages", (first, second)),))
    session = AcceptanceGuide().start(task, workflow)

    result = session.complete_node(workflow.stage_paths[1])

    assert result.status is TaskStatus.BLOCKED
    assert "depends on incomplete nodes" in result.errors[0]


def test_a_cross_branch_dependency_gates_a_call_until_that_node_is_done():
    """The dependency the field exists for: one node in one branch gating one node
    in another. A sibling id could not name it, because the two are not siblings at
    any level -- they meet at the root, three levels up.
    """

    task = host_task("cross-branch")
    ground = stage_spec("ground", "Lay the ground", "lay",
                        (call("ue5", "spawn_ground", "g1"),))
    tower = stage_spec("tower", "Build a tower", "build",
                       (call("ue5", "spawn_tower", "t1"),),
                       # /buildings/tower/ -> .. is /buildings/, .. again is /, then down.
                       depends_on=("../../site/ground",))
    workflow = workflow_for(task, (step("site", "Site", (ground,)),
                                   step("buildings", "Buildings", (tower,))))
    session = AcceptanceGuide().start(task, workflow)

    assert workflow.dependency_paths("/buildings/tower/") == ("/site/ground/",)

    with pytest.raises(WorkflowError, match="incomplete dependencies"):
        submit_call_result(session, tower.declared_calls[0])

    # Settle the other branch, then the same call is allowed. Nothing about the
    # declaration changed -- only the evidence behind it.
    submit_call_result(session, ground.declared_calls[0])
    site_result = session.complete_node("/site/ground/")
    assert site_result.status is TaskStatus.SUCCEEDED, site_result.errors

    submit_call_result(session, tower.declared_calls[0])
    assert session.complete_node("/buildings/tower/").status is TaskStatus.SUCCEEDED


def test_a_composites_dependency_gates_the_leaves_under_it():
    """Ordering is declared once, at the level where it is true.

    A leaf does not repeat its ancestors' references, and must not have to. A blind
    author who could not tell whether a composite's dependency reaches its children
    duplicated the reference onto every leaf instead -- which works, and is noise
    that drifts the moment one copy is edited.
    """

    task = host_task("ancestor-gate")
    ground = stage_spec("ground", "Lay the ground", "lay",
                        (call("ue5", "spawn_ground", "g1"),))
    tower = stage_spec("tower", "Build a tower", "build",
                       (call("ue5", "spawn_tower", "t1"),))
    workflow = workflow_for(task, (
        step("site", "Site", (ground,)),
        step("buildings", "Buildings", (tower,), depends_on=("../site/ground",)),
    ))
    session = AcceptanceGuide().start(task, workflow)

    assert tower.depends_on == (), "the leaf declares no dependency of its own"

    with pytest.raises(WorkflowError, match="incomplete dependencies"):
        submit_call_result(session, tower.declared_calls[0])

    submit_call_result(session, ground.declared_calls[0])
    session.complete_node("/site/ground/")

    submit_call_result(session, tower.declared_calls[0])
    assert session.complete_node("/buildings/tower/").status is TaskStatus.SUCCEEDED
