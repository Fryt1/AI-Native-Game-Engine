"""Evaluate a Workflow tree bottom-up.

Nesting forces one question a flat model never has to answer: **when is a
composite complete?** This module answers it explicitly, because the answer
propagates into reuse, resume and the final verdict.

The rule, in order:

1. a **STAGE** completes when every required execution item is satisfied and every
   required acceptance check passes -- judged by
   :class:`~ainative.acceptance.evaluator.StageAcceptanceEvaluator`, which owns
   what a leaf means;
2. a **WORKFLOW** completes when every required child completed **and** its own
   acceptance checks pass;
3. an optional node the Agent omitted is ``skipped`` -- it does not fail its parent
   and is never reported as ``pass``;
4. an unresolved required check (``unknown`` / ``needs_human``) makes the node
   unknown and blocks **every ancestor**, because a verdict earned on incomplete
   evidence is not a verdict.

Rule 4 is what keeps a tree honest. It is exactly the failure a "did my calls
return" parent would hide.

This module owns recursion and nothing else. It delegates every leaf judgement, so
the operator vocabulary and the evidence rules are defined once, in the evaluator,
rather than restated here for the composite case.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ainative.model.checklists import (
    CheckOperator,
    CheckResult,
    CheckStatus,
    ExecutionItemResult,
)
from ainative.model.results import ExecutionResult
from ainative.model.tree import (
    ROOT_PATH,
    SATISFIED_STATUSES,
    UNRESOLVED_STATUSES,
    NodeKind,
    WorkflowNode,
    WorkflowTree,
    join_path,
)

from .evaluator import StageAcceptanceEvaluator, apply_check, require_check_evidence


@dataclass(frozen=True, slots=True)
class NodeResult:
    """The verdict for one node, with its children's verdicts nested inside."""

    path: str
    node_id: str
    kind: NodeKind
    status: CheckStatus
    required: bool
    item_results: tuple[ExecutionItemResult, ...] = ()
    check_results: tuple[CheckResult, ...] = ()
    children: tuple[NodeResult, ...] = ()
    blocked_by: tuple[str, ...] = ()
    reason: str = ""
    #: True when this node is optional and the Agent omitted it. The status is
    #: ``unknown`` because no evidence exists for work that did not run, and
    #: reporting ``pass`` would be a lie. The flag records *why* it is unknown, so
    #: an omitted optional node is distinguishable from an unresolved required one.
    #: No new status is invented: the vocabulary is fixed at pass / warn / fail /
    #: unknown / needs_human.
    skipped: bool = False

    @property
    def ok(self) -> bool:
        return self.status in SATISFIED_STATUSES

    @property
    def unresolved(self) -> bool:
        """Return True when this node is unknown or awaiting a human."""

        return self.status in UNRESOLVED_STATUSES

    def find(self, path: str) -> NodeResult | None:
        """Return a descendant result by absolute path, or by a relative suffix."""

        if self.path == path:
            return self
        for child in self.children:
            if child.path == path:
                return child
            deeper = child.find(path)
            if deeper is not None:
                return deeper
        stripped = path.strip("/")
        if self.path.rstrip("/").endswith(f"/{stripped}"):
            return self
        return None

    def walk(self) -> list[NodeResult]:
        """Return every result in this subtree, parents before children."""

        out = [self]
        for child in self.children:
            out.extend(child.walk())
        return out

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "path": self.path,
            "node_id": self.node_id,
            "kind": self.kind.value,
            "status": self.status.value,
            "required": self.required,
        }
        if self.skipped:
            out["skipped"] = True
        if self.item_results:
            out["item_results"] = [r.to_dict() for r in self.item_results]
        if self.check_results:
            out["check_results"] = [c.to_dict() for c in self.check_results]
        if self.children:
            out["children"] = [child.to_dict() for child in self.children]
        if self.blocked_by:
            out["blocked_by"] = list(self.blocked_by)
        if self.reason:
            out["reason"] = self.reason
        return out


def evaluate_tree(
    tree: WorkflowTree,
    execution_results: dict[tuple[str, str], ExecutionResult] | None = None,
    skipped_paths: frozenset[str] | None = None,
    item_results: dict[tuple[str, str], ExecutionItemResult] | None = None,
    check_results: dict[tuple[str, str], CheckResult] | None = None,
) -> NodeResult:
    """Evaluate a whole tree bottom-up.

    @param tree: the Agent-authored tree to judge.
    @param execution_results: what the Agent reported, keyed by
        ``(node path, call id)``. A call with no reported result counts as failed,
        never as passed: absence of evidence is not evidence. The path is part of
        the key because a call id is scoped to the STAGE that declares it -- two
        subtrees may each declare a ``build``, which is exactly what lets
        containment work without hand-mangled ids.
    @param skipped_paths: paths of optional nodes the Agent chose to omit.
    @param item_results: execution checklist results the Agent submitted, keyed by
        ``(node path, item id)``. Only items that derive from no call may appear.
    @param check_results: acceptance check results the Agent submitted, keyed by
        ``(node path, check id)``. Only ``manual`` checks may appear.
    @returns the root's verdict with every descendant nested inside it.
    """

    results = execution_results or {}
    omitted = skipped_paths or frozenset()
    explicit_items = item_results or {}
    explicit_checks = check_results or {}
    leaf_evaluator = StageAcceptanceEvaluator()

    def visit(node: WorkflowNode, path: str) -> NodeResult:
        if node.is_leaf:
            return visit_stage(node, path)

        children = tuple(visit(child, join_path(path, child.node_id))
                         for child in node.children)

        # A required child that failed makes the parent fail. A required child that
        # is merely unresolved (unknown / needs_human) makes the parent unknown:
        # the evidence is incomplete, which is not the same as a failure, and
        # collapsing the two would hide "we could not tell" behind "it broke".
        failed = [c.path for c in children
                  if c.required and c.status is CheckStatus.FAIL and c.path not in omitted]
        unresolved = [c.path for c in children
                      if c.required and c.status in UNRESOLVED_STATUSES
                      and c.path not in omitted]
        blocked = failed + unresolved
        checks = evaluate_composite_checks(node, path, children)

        if not node.required and path in omitted:
            status = CheckStatus.UNKNOWN
            reason = "optional node omitted by the Agent"
            skipped = True
        else:
            skipped = False
            if failed:
                status = CheckStatus.FAIL
                reason = f"{len(failed)} required child node(s) failed"
            elif unresolved:
                status = CheckStatus.UNKNOWN
                reason = f"{len(unresolved)} required child node(s) could not be resolved"
            elif any(c.status in UNRESOLVED_STATUSES for c in checks):
                status, reason = CheckStatus.UNKNOWN, "a check could not be resolved"
            elif any(c.status is CheckStatus.FAIL for c in checks):
                status, reason = CheckStatus.FAIL, "a check failed"
            elif any(c.status is CheckStatus.WARN for c in checks):
                status, reason = CheckStatus.WARN, "a check warned"
            else:
                status = CheckStatus.PASS
                reason = "all required children and checks passed"

        return NodeResult(path=path, node_id=node.node_id, kind=node.kind,
                          status=status, required=node.required,
                          check_results=checks, children=children,
                          blocked_by=tuple(blocked), reason=reason, skipped=skipped)

    def visit_stage(node: WorkflowNode, path: str) -> NodeResult:
        """Judge one leaf by handing it to the evaluator that owns leaf meaning."""

        if node.stage is None:
            return NodeResult(path=path, node_id=node.node_id, kind=node.kind,
                              status=CheckStatus.FAIL, required=node.required,
                              reason="a STAGE node has no body")

        acceptance = leaf_evaluator.evaluate(
            node,
            path,
            tuple(results[(path, call.call_id)] for call in node.stage.calls
                  if (path, call.call_id) in results),
            tuple(result for (owner, _item), result in explicit_items.items()
                  if owner == path),
            tuple(result for (owner, _check), result in explicit_checks.items()
                  if owner == path),
        )

        if not node.required and path in omitted:
            status = CheckStatus.UNKNOWN
            reason = "optional stage omitted by the Agent"
            skipped = True
        else:
            skipped = False
            status = acceptance.status
            reason = _stage_reason(status, acceptance)

        return NodeResult(path=path, node_id=node.node_id, kind=node.kind,
                          status=status, required=node.required,
                          item_results=acceptance.item_results,
                          check_results=acceptance.check_results,
                          reason=reason, skipped=skipped)

    def evaluate_composite_checks(node: WorkflowNode,
                                  node_path: str,
                                  child_results: tuple[NodeResult, ...]
                                  ) -> tuple[CheckResult, ...]:
        """Evaluate a composite's checks, each reading one descendant's verdict.

        The observed value is that descendant's verdict word. Nothing else is
        observable, which is why the schema confines ``expected`` to the verdict
        vocabulary: an author who writes ``"succeeded"`` here is comparing against
        a task status that a node never has, and the check can never pass.

        A ``manual`` composite check is the exception: it observes nothing and
        awaits a human, so the Agent's submitted result is what decides it. The
        validator refuses every other operator on a composite, because applying a
        call-oriented or numeric operator to a verdict word yields an accidental
        constant rather than a judgement -- ``tool_succeeded`` and ``exists``
        would always pass, ``count_equals`` and ``within_tolerance`` always fail.
        """

        out: list[CheckResult] = []
        for wrapper in node.declared_checks:
            declared = wrapper.check
            identifier = declared.check_id
            submitted = explicit_checks.get((node_path, identifier))

            if declared.operator is CheckOperator.MANUAL:
                if submitted is None:
                    out.append(CheckResult(
                        check_id=identifier, status=CheckStatus.NEEDS_HUMAN,
                        expected=declared.expected,
                        reason="manual check awaits a human verdict"))
                else:
                    out.append(require_check_evidence(declared, submitted))
                continue

            source = wrapper.source_node
            if not source:
                out.append(CheckResult(
                    check_id=identifier, status=CheckStatus.UNKNOWN,
                    expected=declared.expected,
                    reason="check reads no descendant"))
                continue

            suffix = "/" + source.strip("/") + "/"
            target = next(
                (c for c in child_results
                 if c.path.endswith(suffix) or c.path == source), None)
            if target is None:
                for reached in child_results:
                    target = reached.find(source)
                    if target is not None:
                        break
            if target is None:
                out.append(CheckResult(
                    check_id=identifier, status=CheckStatus.UNKNOWN,
                    expected=declared.expected,
                    reason=f"source_node '{source}' produced no result under "
                           f"{node.node_id}"))
                continue

            out.append(apply_check(declared, target.status.value, identifier))
        return tuple(out)

    return visit(tree.root, ROOT_PATH)


def _stage_reason(status: CheckStatus, acceptance: Any) -> str:
    """Say why a leaf landed where it did, preferring its own error text."""

    if status is CheckStatus.PASS:
        return "every required execution item and check passed"
    if acceptance.errors:
        return " ".join(acceptance.errors)
    if acceptance.warnings:
        return " ".join(acceptance.warnings)
    return {
        CheckStatus.WARN: "a check warned",
        CheckStatus.FAIL: "a required execution item or check failed",
        CheckStatus.UNKNOWN: "a check could not be resolved",
        CheckStatus.NEEDS_HUMAN: "a check needs a human verdict",
    }.get(status, status.value)


def _call_ok(result: ExecutionResult | None) -> bool:
    """Return True only for a call that reported success or a degradation."""

    if result is None:
        return False
    return result.status.value in {"succeeded", "degraded"}


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def summarise_tree(result: NodeResult) -> dict[str, int]:
    """Count node verdicts across the whole tree."""

    counts: dict[str, int] = {}
    for node in result.walk():
        counts[node.status.value] = counts.get(node.status.value, 0) + 1
    return counts


def blocking_paths(result: NodeResult) -> list[str]:
    """Return the paths preventing the root from passing, deepest first.

    An optional node the Agent omitted is not a blocker: it is unknown only
    because it did not run, and the node itself records that with ``skipped``.
    """

    blockers: list[str] = []

    def visit(node: NodeResult) -> bool:
        children_ok = all(visit(child) for child in node.children)
        # A WARN is not a blocker: it is a degradation the caller must see, and the
        # node's own status already records it.
        checks_ok = all(c.status is not CheckStatus.FAIL
                        and c.status not in UNRESOLVED_STATUSES
                        for c in node.check_results)
        blocked = node.status is CheckStatus.FAIL or (
            node.status in UNRESOLVED_STATUSES and not node.skipped)
        okay = children_ok and checks_ok and not blocked
        if not okay and node.required:
            blockers.append(node.path)
        return okay

    visit(result)
    blockers.reverse()
    return blockers
