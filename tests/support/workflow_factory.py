"""Build the Workflow trees a test needs, without any host or MCP call.

A Workflow **is** a tree, and a node is either a STAGE (leaf: calls and its frozen
checklists) or a WORKFLOW (composite: children and the checks that read them).
There is no flat ``Workflow -> Step -> Stage`` shape; a phase is just a WORKFLOW
node used for grouping.

Every helper here is a stand-in for what the **Agent** authors. Nothing in this
module executes anything: :func:`submit_call_result` is the test stand-in for the
Agent reporting what its own MCP call returned.
"""

from __future__ import annotations

from typing import Any

from ainative.model import (
    AcceptanceCheck,
    CallTarget,
    CheckOperator,
    ExecutionChecklistItem,
    ExecutionResult,
    NodeCheck,
    NodeKind,
    StageBody,
    StageKind,
    TaskContract,
    TaskStatus,
    ToolCall,
    WorkflowNode,
    WorkflowStatus,
    WorkflowTree,
)

#: The synthetic composite the factory hangs a Workflow's top-level groups under.
ROOT_ID = "workflow"


def call(
    owner: str,
    name: str,
    call_id: str,
    arguments: dict[str, Any] | None = None,
    depends_on: tuple[str, ...] = (),
) -> ToolCall:
    """Build one declared call.

    @param owner: the Toolset id for a project Tool, or the MCP server name.
    @param name: the Tool id, or the MCP tool name on that server.
    @param call_id: the id this Workflow refers to the call by.
    @param arguments: the arguments the Agent will pass.
    @param depends_on: calls that must complete first.
    """

    return ToolCall(
        call_id=call_id,
        target=CallTarget(owner=owner, name=name),
        arguments=dict(arguments or {}),
        depends_on=depends_on,
    )


def stage_spec(
    stage_id: str,
    purpose: str,
    operation: str = "",
    calls: tuple[ToolCall, ...] = (),
    *,
    stage_kind: StageKind = StageKind.CHANGE,
    depends_on: tuple[str, ...] = (),
    required: bool = True,
    recovery: str | None = None,
) -> WorkflowNode:
    """Build one STAGE node: a leaf that declares calls and both checklists.

    Its path -- not ``stage_id`` -- is what identifies it, so two subtrees may each
    build a stage called ``mass`` without collision.
    """

    execution_item = ExecutionChecklistItem(
        item_id=f"{stage_id}.executed",
        description=f"Required work for {purpose}",
        required=required,
        call_ids=tuple(call.call_id for call in calls),
        evidence_required=bool(calls),
    )
    source_call_id = calls[-1].call_id if calls else None
    acceptance_check = AcceptanceCheck(
        check_id=f"{stage_id}.completed",
        description=f"Completion evidence for {purpose}",
        required=required,
        call_ids=(source_call_id,) if source_call_id else (),
        source_call_id=source_call_id,
        operator=CheckOperator.TOOL_SUCCEEDED if source_call_id else CheckOperator.MANUAL,
        evidence_required=bool(source_call_id),
    )
    return WorkflowNode(
        node_id=stage_id,
        kind=NodeKind.STAGE,
        purpose=f"{purpose} ({operation})" if operation else purpose,
        required=required,
        depends_on=depends_on,
        recovery=recovery,
        stage=StageBody(
            calls=calls,
            execution_checklist=(execution_item,),
            acceptance_checklist=(NodeCheck(acceptance_check),),
            stage_kind=stage_kind,
        ),
    )


def step(
    step_id: str,
    purpose: str,
    stages: tuple[WorkflowNode, ...],
    depends_on: tuple[str, ...] = (),
    optional: bool = False,
) -> WorkflowNode:
    """Build one WORKFLOW node: a composite used to group and order leaves."""

    return WorkflowNode(
        node_id=step_id,
        kind=NodeKind.WORKFLOW,
        purpose=purpose,
        required=not optional,
        depends_on=depends_on,
        children=tuple(stages),
    )


def workflow_for(
    task: TaskContract,
    steps: tuple[WorkflowNode, ...],
    *,
    revision: int = 1,
    workflow_id: str | None = None,
    status: WorkflowStatus = WorkflowStatus.DRAFT,
) -> WorkflowTree:
    """Wrap top-level groups in a root composite and return the Workflow."""

    return WorkflowTree(
        workflow_id=workflow_id or f"{task.task_id}:workflow",
        root=WorkflowNode(
            node_id=ROOT_ID,
            kind=NodeKind.WORKFLOW,
            purpose="the Workflow",
            children=tuple(steps),
        ),
        revision=revision,
        status=status,
    )


def one_stage_workflow(
    task: TaskContract,
    stage: WorkflowNode,
    *,
    step_id: str = "step-1",
    step_purpose: str = "Execute the Agent-selected Stage",
) -> WorkflowTree:
    return workflow_for(task, (step(step_id, step_purpose, (stage,)),))


def stage_paths(workflow: WorkflowTree) -> tuple[str, ...]:
    """Return every STAGE node's path, in tree order."""

    return workflow.stage_paths


def first_stage_path(workflow: WorkflowTree) -> str:
    """Return the first leaf's path -- the usual subject of a single-stage test."""

    paths = workflow.stage_paths
    if not paths:
        raise AssertionError("this Workflow declares no STAGE node")
    return paths[0]


def first_stage(workflow: WorkflowTree) -> WorkflowNode:
    """Return the first leaf node."""

    return next(node for _path, node in workflow.stages)


def submit_call_result(
    session,
    call: ToolCall,
    status: TaskStatus = TaskStatus.SUCCEEDED,
    **evidence: Any,
) -> ExecutionResult:
    """Submit one declared call's result as the Agent would.

    @param session: the open session.
    @param call: the declared call this result belongs to.
    @param status: what the Agent reported.
    @param evidence: extra evidence fields (``outputs``, ``preserved_relations``, ...).
    @returns the recorded execution result.
    """

    session.check_call_ready(call.call_id)
    result = ExecutionResult(
        call_id=call.call_id,
        status=status,
        target=call.target,
        outputs=dict(evidence.pop("outputs", {})),
        artifacts=tuple(evidence.pop("artifacts", ())),
        warnings=tuple(evidence.pop("warnings", ())),
        errors=tuple(evidence.pop("errors", ())),
        preserved_relations=frozenset(evidence.pop("preserved_relations", ())),
        lost_relations=frozenset(evidence.pop("lost_relations", ())),
    )
    session.record_execution_result(result)
    return result
