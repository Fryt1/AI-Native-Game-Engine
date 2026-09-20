"""The acceptance session: record what the Agent reports, judge it deterministically.

The Agent executes every call itself and submits structured results here. This
class never invokes a Tool or an MCP server. It validates each submitted result
against the Workflow's declaration, records it as evidence, evaluates a node
against its frozen checklists, and aggregates the final Task result.

**Nodes are addressed by path.** A ``node_id`` is unique only among siblings --
that is what lets two subtrees each declare a ``mass`` -- so a bare id cannot
name one node, and this layer never pretends otherwise. ``/buildings/tower_a/mass/``
is a node; ``mass`` alone is an ambiguity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ainative.acceptance import (
    CHECK_STATUS_TO_TASK_STATUS,
    evaluate_tree,
    summarise_checklist,
)
from ainative.acceptance.aggregation import (
    aggregate_task_status,
    next_action_for,
    outstanding_nodes,
)
from ainative.model.checklists import (
    CheckOperator,
    CheckResult,
    CheckStatus,
    ExecutionItemResult,
)
from ainative.model.results import (
    ExecutionResult,
    StageResult,
    TaskResult,
    TaskStatus,
)
from ainative.model.task import TaskContract
from ainative.model.tree import (
    COMPLETE_STATUSES,
    GateResult,
    WorkflowNode,
    WorkflowTree,
    join_path,
)

from .errors import WorkflowError


@dataclass(slots=True)
class AcceptanceSession:
    """Validation/recording session for an Agent-authored Workflow tree."""

    skill: Any
    task: TaskContract
    workflow: WorkflowTree
    gate: GateResult = field(default_factory=lambda: GateResult(True))
    state: dict[str, Any] = field(default_factory=dict)
    _call_paths: dict[str, tuple[str, ...]] = field(default_factory=dict, init=False)
    _call_executions: dict[tuple[str, str], ExecutionResult] = field(
        default_factory=dict, init=False)
    _item_results: dict[tuple[str, str], ExecutionItemResult] = field(
        default_factory=dict, init=False)
    _check_results: dict[tuple[str, str], CheckResult] = field(
        default_factory=dict, init=False)
    _task_results: dict[str, TaskResult] = field(default_factory=dict, init=False)
    _node_results: dict[str, StageResult] = field(default_factory=dict, init=False)
    _skipped: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        for path, node in self.workflow.stages:
            for call in node.declared_calls:
                self._call_paths[call.call_id] = (
                    *self._call_paths.get(call.call_id, ()), path)

    def resolve_call(self, call_id: str, node_path: str | None = None) -> str:
        """Return the node path a call result belongs to.

        Delegates to the Workflow, which is where the rule lives: a call id is
        scoped to the STAGE that declares it, so the same id in two subtrees names
        two different host changes and neither may be bound to the other.
        """

        try:
            return self.workflow.resolve_call_path(call_id, node_path)
        except ValueError as exc:
            raise WorkflowError(str(exc)) from exc

    # -- State the CLI reports --

    @property
    def ready(self) -> bool:
        return self.gate.ready

    @property
    def completed_call_ids(self) -> tuple[str, ...]:
        return tuple(call_id for _path, call_id in self._call_executions)

    @property
    def completed_node_paths(self) -> tuple[str, ...]:
        """Return every node the tree currently judges satisfied.

        Completion is **derived**, not declared. A composite completes when its
        required children completed and its own checks pass, so asking the Agent to
        also close it would be asking it to re-assert what the tree already
        determines. Closing a node still records a verdict at a point in time --
        that is the audit trail -- but it is not what makes the node complete.
        """

        return tuple(sorted(self._satisfied_paths()))

    @property
    def node_results(self) -> tuple[StageResult, ...]:
        return tuple(self._node_results.values())

    @property
    def nodes_with_side_effects(self) -> tuple[str, ...]:
        """Return the node paths that have already touched the outside world.

        Python never sees the host, so it cannot know whether an edit landed. What
        it does know is that the Agent reported a call for that node, which means
        the call ran against a live host and may have changed it.

        This is the fact that matters when a Workflow is replaced: re-running such
        a node could apply the same change twice. The Agent decides what to do;
        Python's job is to name the nodes at risk instead of letting a re-run look
        identical to a first run.
        """

        touched: list[str] = []
        for path, _call_id in self._call_executions:
            if path not in touched:
                touched.append(path)
        return tuple(touched)

    def has_side_effects(self, path: str) -> bool:
        """True once any call declared by this node has been recorded."""

        return path in self.nodes_with_side_effects

    # -- Evidence recording (Agent submits results; Python validates) --

    def record_execution_item(self, path: str, result: ExecutionItemResult) -> ExecutionItemResult:
        body = self._body(path)
        item = next(
            (item for item in body.execution_checklist if item.item_id == result.item_id), None)
        if item is None:
            raise WorkflowError(
                f"Execution checklist item is not declared in {path}: {result.item_id}")
        if item.call_ids:
            raise WorkflowError(
                f"Execution checklist item {result.item_id} is derived from "
                "ExecutionResults and cannot be overridden")
        self._item_results[(path, result.item_id)] = result
        self._invalidate(path)
        return result

    def record_check_result(self, path: str, result: CheckResult) -> CheckResult:
        node = self._node(path)
        check = next(
            (wrapper.check for wrapper in node.declared_checks
             if wrapper.check_id == result.check_id), None)
        if check is None:
            raise WorkflowError(
                f"Acceptance check is not declared in {path}: {result.check_id}")
        if check.operator is not CheckOperator.MANUAL:
            raise WorkflowError(
                f"Acceptance check {result.check_id} uses deterministic operator "
                f"{check.operator.value} and cannot be overridden")
        self._check_results[(path, result.check_id)] = result
        self._invalidate(path)
        return result

    def record_execution_result(
        self,
        result: ExecutionResult,
        node_path: str | None = None,
        *,
        submitted: bool = True,
    ) -> ExecutionResult:
        """Record a raw call result.

        This is the only execution entry point. Python never invokes the call; it
        validates the submitted result against the declaration and dependency
        order, then records it as evidence for the node that declared it.

        @param result: what the Agent reported.
        @param node_path: the node that declared the call. Required only when the
            call id is declared by more than one node.
        @param submitted: True for a result the Agent has just reported, False when
            re-applying an event already in the log. The two are not the same act.
            An event was accepted under the revision it was submitted to, and its
            ordering was checked then; re-applying it after a replacement can find
            a dependency whose evidence was archived, so re-litigating the order
            would leave the state file unreadable -- and a state no command can
            read is worse than one with a stale verdict in it. The target check
            still applies either way, because a target that no longer matches the
            declaration means the event does not belong to this revision at all.

        The result must name the target it ran. A result that omits it cannot be
        checked against the declaration, and "do not silently substitute another
        target" is only a rule if the target is reported.
        """

        path = self.resolve_call(result.call_id, node_path)
        key = (path, result.call_id)
        if key in self._call_executions:
            raise WorkflowError(
                f"Execution result has already been recorded: {result.call_id} at {path}")
        call = next(
            call for call in self._node(path).declared_calls
            if call.call_id == result.call_id)
        if submitted:
            self.check_call_ready(result.call_id, path)
        if result.target is None:
            raise WorkflowError(
                f"Execution result must report the target it ran: {result.call_id} "
                f"declared {call.qualified_name}, got nothing")
        if result.target != call.target:
            raise WorkflowError(
                f"Execution result target mismatch for {result.call_id}: "
                f"declared {call.qualified_name}, got {result.target.owner}/{result.target.name}")
        if not isinstance(result.outputs, dict):
            raise WorkflowError(f"Execution result outputs must be an object: {result.call_id}")
        self._call_executions[key] = result
        self._task_results[result.call_id] = self._task_result_for(result)
        self.state.setdefault("recorded_execution_results", {})[result.call_id] = result.to_dict()
        self._invalidate(path)
        return result

    def _task_result_for(self, result: ExecutionResult) -> TaskResult:
        """Project one call result onto the Workflow's identity, for aggregation."""

        return TaskResult(
            status=result.status,
            workflow_id=self.workflow.workflow_id,
            workflow_revision=self.workflow.revision,
            details=dict(result.outputs),
            artifacts=result.artifacts,
            warnings=result.warnings,
            errors=result.errors,
            resume_pointer=result.resume_pointer,
            preserved_relations=frozenset(result.preserved_relations),
            lost_relations=frozenset(result.lost_relations),
        )

    def check_call_ready(self, call_id: str, node_path: str | None = None) -> None:
        """Fail closed when an Agent tries to run a call before its dependencies."""

        path = self.resolve_call(call_id, node_path)
        call = next(
            call for call in self._node(path).declared_calls if call.call_id == call_id)

        missing: list[str] = []
        failed: list[str] = []

        satisfied = self._satisfied_paths()
        unmet = [p for p in self._required_predecessors(path) if p not in satisfied]
        if unmet:
            missing.append("node:" + ",node:".join(sorted(unmet)))
        for dependency in call.depends_on:
            dependency_result = self._call_executions.get((path, dependency))
            if dependency_result is None:
                missing.append(dependency)
            elif dependency_result.status not in {TaskStatus.SUCCEEDED, TaskStatus.DEGRADED}:
                failed.append(dependency)
        if missing or failed:
            reasons = []
            if missing:
                reasons.append("incomplete dependencies: " + ", ".join(missing))
            if failed:
                reasons.append("failed dependencies: " + ", ".join(failed))
            raise WorkflowError(f"Call {call_id} cannot execute; " + "; ".join(reasons))

    # -- Node evaluation --

    def complete_node(self, path: str) -> StageResult:
        """Evaluate one node against its frozen checklists and close it."""

        if path in self._node_results:
            return self._node_results[path]
        node = self._node(path)

        blocked = self._dependency_block(path)
        if blocked is not None:
            return blocked

        evaluated = self._evaluate().find(path)
        if evaluated is None:
            raise WorkflowError(f"Stage is not present in the Agent-authored Workflow: {path}")

        result = self._report(path, node, evaluated)
        self._node_results[path] = result
        return result

    def _satisfied_paths(self) -> set[str]:
        """Return every node path the tree currently judges done.

        "Done" means ``pass`` **or** ``warn``: a warned node is degraded, which the
        task reports as ``degraded``, not unfinished. Treating a warning as
        outstanding would block a task whose work actually completed.

        An optional node the Agent omitted counts as settled too: it is unknown
        because it did not run, and nothing is waiting on it.
        """

        return {
            reached.path
            for reached in self._evaluate().walk()
            if reached.status in COMPLETE_STATUSES or reached.skipped
        }

    def _report(self, path: str, node: WorkflowNode, evaluated: Any) -> StageResult:
        """Project a node's evaluated verdict onto the reported result shape."""

        calls = tuple(
            self._call_executions[(path, call.call_id)]
            for call in node.declared_calls
            if (path, call.call_id) in self._call_executions
        )
        outputs: dict[str, Any] = {}
        artifacts: list[Any] = []
        warnings: list[str] = []
        errors: list[str] = []
        for execution_result in calls:
            outputs.update(execution_result.outputs)
            artifacts.extend(execution_result.artifacts)
            warnings.extend(execution_result.warnings)
            errors.extend(execution_result.errors)
        # A verdict that is not a pass is not silent: the caller has to be told
        # why, and whether it is a failure or a degradation.
        if evaluated.status in {CheckStatus.FAIL, CheckStatus.UNKNOWN,
                                CheckStatus.NEEDS_HUMAN}:
            errors.append(evaluated.reason)
        elif evaluated.status is CheckStatus.WARN:
            warnings.append(evaluated.reason)

        body = node.stage
        items = body.execution_checklist if body is not None else ()
        checks = tuple(wrapper.check for wrapper in node.declared_checks)
        return StageResult(
            node_path=path,
            status=CHECK_STATUS_TO_TASK_STATUS[evaluated.status],
            execution_results=calls,
            execution_item_results=evaluated.item_results,
            check_results=evaluated.check_results,
            execution_summary=summarise_checklist(items, evaluated.item_results, "item_id"),
            acceptance_summary=summarise_checklist(checks, evaluated.check_results, "check_id"),
            outputs=outputs,
            artifacts=tuple(artifacts),
            warnings=tuple(warnings),
            errors=tuple(errors),
            resume_pointer=(
                None if evaluated.status in COMPLETE_STATUSES
                else (node.recovery or path)
            ),
        )

    def _dependency_block(self, path: str) -> StageResult | None:
        """Return a BLOCKED result when a predecessor is unmet, else None."""

        comp = self._satisfied_paths()
        missing = [p for p in self._required_predecessors(path) if p not in comp]
        if not missing:
            return None
        return StageResult(
            node_path=path,
            status=TaskStatus.BLOCKED,
            errors=[
                f"Stage {path} depends on incomplete nodes: {', '.join(sorted(missing))}"
            ],
            resume_pointer=path,
        )

    def _required_predecessors(self, path: str) -> tuple[str, ...]:
        """Return the paths this node needs settled before it can run.

        Two sources, and both are transitive for a reason. The node's **own**
        ``depends_on`` gates its calls directly. Every **ancestor's** does too:
        a composite cannot complete until its dependencies have, and it cannot
        complete until this node has, so waiting only on the node's own list would
        let a call run inside a subtree whose branch was still blocked.

        Each reference is resolved from the node that declared it, so the same
        declaration means the right path wherever the subtree is placed.
        """

        needed: list[str] = []
        for ancestor_path, _node in self._ancestors_and_self(path):
            for candidate in self.workflow.dependency_paths(ancestor_path):
                if candidate not in needed:
                    needed.append(candidate)
        return tuple(needed)

    def _ancestors_and_self(self, path: str) -> tuple[tuple[str, WorkflowNode], ...]:
        """Return ``(path, node)`` for every ancestor of ``path``, then itself.

        The node itself is included because a dependency gating a node is declared
        on that node, not on its parent. Walking ancestors without it silently
        skips the one declaration that matters.
        """

        out: list[tuple[str, WorkflowNode]] = []
        for candidate in (*self._ancestor_paths(path), path):
            node = self.workflow.node_at(candidate)
            if node is not None:
                out.append((candidate, node))
        return tuple(out)

    @staticmethod
    def _ancestor_paths(path: str) -> tuple[str, ...]:
        """Return ``("/", "/a/", "/a/b/")`` for ``/a/b/c/`` -- root first."""

        segments = [s for s in path.strip("/").split("/") if s]
        out = ["/"]
        current = "/"
        for segment in segments[:-1]:
            current = join_path(current, segment)
            out.append(current)
        return tuple(out)

    def _evaluate(self) -> Any:
        """Evaluate the whole tree from the evidence recorded so far."""

        return evaluate_tree(
            self.workflow,
            self._call_executions,
            frozenset(self._skipped),
            self._item_results,
            self._check_results,
        )

    def _node(self, path: str) -> WorkflowNode:
        node = self.workflow.node_at(path)
        if node is None:
            raise WorkflowError(
                f"Node is not present in the Agent-authored Workflow: {path}")
        return node

    def _body(self, path: str) -> Any:
        node = self._node(path)
        if node.stage is None:
            raise WorkflowError(f"Node {path} is a composite and declares no checklists")
        return node.stage

    def _invalidate(self, path: str) -> None:
        """Drop closed verdicts that new evidence for ``path`` has outdated.

        A change anywhere below a composite changes the composite: its verdict was
        earned on its children's. Dropping only the node itself would leave an
        ancestor reporting a pass that its own evidence no longer supports.
        """

        stale = {path, *self._ancestor_paths(path)}
        for candidate in stale:
            self._node_results.pop(candidate, None)

    # -- Aggregation --

    def finish(self) -> TaskResult:
        """Aggregate recorded results into the final Task result; execute nothing."""

        required = self.workflow.required_paths
        completed = frozenset(self._satisfied_paths())
        status, workflow_status = aggregate_task_status(
            gate_ready=self.gate.ready,
            node_statuses=frozenset(r.status for r in self._node_results.values()),
            required_paths=required,
            completed_paths=completed,
        )
        outstanding = outstanding_nodes(
            required_paths=required, completed_paths=completed)

        artifacts = []
        warnings: list[str] = []
        errors: list[str] = list(self.gate.blocked_reasons)
        preserved_relations: set[str] = set()
        lost_relations: set[str] = set()
        resume_pointer = self.workflow.recovery_pointer
        for node_result in self._node_results.values():
            if node_result.status not in {TaskStatus.SUCCEEDED, TaskStatus.DEGRADED}:
                resume_pointer = node_result.resume_pointer or node_result.node_path
                break
        for task_result in self._task_results.values():
            preserved_relations.update(task_result.preserved_relations)
            lost_relations.update(task_result.lost_relations)
        for node_result in self._node_results.values():
            artifacts.extend(node_result.artifacts)
            warnings.extend(node_result.warnings)
            errors.extend(node_result.errors)
        # A blocked Task must say what it is waiting for, or the Agent has to go
        # looking for the reason it already earned.
        if outstanding and status is TaskStatus.BLOCKED:
            errors.append("required nodes not closed: " + ", ".join(outstanding))
        details = dict(self.state)
        details["agent_execution"] = {
            "completed_calls": list(self.completed_call_ids),
            "completed_nodes": list(self.completed_node_paths),
        }
        details["outstanding_nodes"] = list(outstanding)
        return TaskResult(
            status=status,
            workflow_id=self.workflow.workflow_id,
            workflow_revision=self.workflow.revision,
            workflow_revision_id=self.workflow.revision_id,
            workflow_status=workflow_status.value,
            supersedes_workflow_id=self.workflow.supersedes_workflow_id,
            preserved_relations=frozenset(preserved_relations),
            lost_relations=frozenset(lost_relations),
            nodes_completed=tuple(sorted(completed)),
            node_results=tuple(self._node_results.values()),
            artifacts=tuple(artifacts),
            details=details,
            warnings=tuple(warnings),
            errors=tuple(errors),
            resume_pointer=resume_pointer,
            next_action=next_action_for(status, gate_ready=self.gate.ready),
        )
