"""Validate a Workflow tree's structure and format.

This is detection, not transformation: it reads a tree the Agent authored and
reports every structural problem, naming the authored path. It builds nothing and
orders nothing.

Every rule exists because the alternative produces a tree that opens cleanly and
then lies -- a composite that reports success while a descendant is unresolved, or
a subtree whose local names silently collide with a sibling's.
"""

from __future__ import annotations

from dataclasses import dataclass

from ainative.model.checklists import CheckOperator
from ainative.model.tree import (
    WorkflowNode,
    WorkflowTree,
    join_path,
    parent_path,
    resolve,
    resolve_relative,
    walk,
)


@dataclass(frozen=True, slots=True)
class TreeIssue:
    """One structural problem, located at the path the author wrote."""

    location: str
    rule: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"location": self.location, "rule": self.rule, "message": self.message}


class TreeIntegrityError(RuntimeError):
    """The Agent-authored Workflow tree is structurally invalid."""

    def __init__(self, issues: tuple[TreeIssue, ...]) -> None:
        self.issues = issues
        super().__init__("; ".join(i.message for i in issues))


def validate_tree_structure(tree: WorkflowTree) -> None:
    """Fail closed on a malformed tree, before any side effect.

    @param tree: the Agent-authored tree to check.
    @raises TreeIntegrityError: listing every issue found, not just the first, so
        one pass reports everything an author has to fix.
    """

    issues: list[TreeIssue] = []
    root = tree.root

    for path, node in walk(root):
        _check_siblings(path, node, issues)
        if node.is_leaf:
            _check_stage(path, node, issues)
        else:
            _check_composite(path, node, issues)

    issues.extend(_check_acyclic(root, tree))
    issues.extend(_check_dependencies(root, tree))

    if issues:
        raise TreeIntegrityError(tuple(issues))


def _check_siblings(path: str, node: WorkflowNode, issues: list[TreeIssue]) -> None:
    """Sibling ids are unique."""

    seen: set[str] = set()
    for child in node.children:
        if child.node_id in seen:
            issues.append(TreeIssue(
                join_path(path, child.node_id), "N2",
                f"duplicate sibling node_id '{child.node_id}' under {path}"))
        seen.add(child.node_id)


def _check_dependencies(root: WorkflowNode, tree: WorkflowTree) -> list[TreeIssue]:
    """Return an issue for every ``depends_on`` that does not name a node.

    A reference is walked from the declaring node, so it may cross branches:
    ``../../site/street-trees`` is how a stage under ``/buildings/`` waits for one
    node under ``/site/``. That is the point of the field.

    The one mistake worth naming is a bare sibling id. ``mass`` parses as the
    declaring node's own CHILD -- a node it already waits for -- so it is refused
    with the spelling that was meant, rather than quietly accepted as a dependency
    that does nothing.
    """

    issues: list[TreeIssue] = []
    for path, node in walk(root):
        for reference in node.depends_on:
            if tree.resolve_dependency(path, reference) is not None:
                continue
            if reference.startswith("/"):
                issues.append(TreeIssue(
                    path, "N5",
                    f"depends_on '{reference}' is absolute; a reference is written "
                    "from the declaring node, so a sibling is '../name' and another "
                    "branch is '../../branch/node'"))
            elif "/" not in reference and resolve(
                    root, join_path(parent_path(path), reference)) is not None:
                # The most likely mistake by far: an id in the old sibling
                # spelling. "names no node" would be true and useless, so this
                # case gets the spelling that was meant.
                issues.append(TreeIssue(
                    path, "N5",
                    f"depends_on '{reference}' names a sibling; a reference is walked "
                    f"from this node, so write it '../{reference}'"))
            elif resolve(root, join_path(path, reference)) is not None:
                issues.append(TreeIssue(
                    path, "N5",
                    f"depends_on '{reference}' names this node's own child, which it "
                    f"already waits for; a sibling is written '../{reference}'"))
            else:
                issues.append(TreeIssue(
                    path, "N5",
                    f"depends_on '{reference}', which names no node from {path}"))
    return issues


def _check_stage(path: str, node: WorkflowNode, issues: list[TreeIssue]) -> None:
    """A STAGE holds calls and both checklists, and reads only its own calls."""

    if node.children:
        issues.append(TreeIssue(path, "N1", "a STAGE node must not have children"))
    if node.acceptance_checklist:
        issues.append(TreeIssue(
            path, "N1",
            "a STAGE node declares acceptance checks; a STAGE owns them inside its "
            "stage body, not at node level"))

    body = node.stage
    if body is None:
        issues.append(TreeIssue(path, "N3", "a STAGE node needs a stage body"))
        return

    if node.required:
        if not body.calls:
            issues.append(TreeIssue(path, "N3", "a required STAGE needs at least one call"))
        if not body.execution_checklist:
            issues.append(TreeIssue(
                path, "N3", "a required STAGE must freeze an execution checklist"))
        if not body.acceptance_checklist:
            issues.append(TreeIssue(
                path, "N3", "a required STAGE must freeze an acceptance checklist"))

    call_ids = [call.call_id for call in body.calls]
    if len(call_ids) != len(set(call_ids)):
        issues.append(TreeIssue(path, "N3", "call ids must be unique inside a STAGE"))
    known_calls = set(call_ids)

    item_ids = [item.item_id for item in body.execution_checklist]
    if len(item_ids) != len(set(item_ids)):
        issues.append(TreeIssue(
            path, "N3", "execution item ids must be unique inside a STAGE"))

    for item in body.execution_checklist:
        if not item.item_id or not item.description:
            issues.append(TreeIssue(
                path, "N3", "an execution item needs an item_id and a description"))
        missing = set(item.call_ids) - known_calls
        if missing:
            issues.append(TreeIssue(
                f"{path}{item.item_id}", "V2",
                "execution item names undeclared calls: " + ", ".join(sorted(missing))))

    referenced: set[str] = set()
    for item in body.execution_checklist:
        referenced.update(item.call_ids)

    for check in body.acceptance_checklist:
        identifier = check.check_id
        if not identifier or not check.check.description:
            issues.append(TreeIssue(
                path, "N3", "an acceptance check needs a check_id and a description"))
        if check.source_node:
            issues.append(TreeIssue(
                f"{path}{identifier}", "C1",
                "a STAGE check must not use source_node; only a WORKFLOW reads a child"))
        if check.source_call_id:
            referenced.add(check.source_call_id)
            if check.source_call_id not in known_calls:
                issues.append(TreeIssue(
                    f"{path}{identifier}", "V2",
                    f"reads undeclared call '{check.source_call_id}'"))
        elif not check.source_node and check.check.operator is not CheckOperator.MANUAL:
            # A deterministic check must read something. A ``manual`` check must
            # not: it awaits a human verdict, which is exactly why
            # ``record_check_result`` accepts a submitted result for it. Demanding
            # a source here made every manual check unrepresentable -- and a
            # STAGE check may not use ``source_node`` either, so there was no
            # spelling that satisfied both rules.
            issues.append(TreeIssue(
                f"{path}{identifier}", "V3",
                f"a {check.check.operator.value} check must read from a call"))
        if check.check.operator is CheckOperator.MANUAL and check.source_call_id:
            issues.append(TreeIssue(
                f"{path}{identifier}", "V3",
                "a manual check must not read a call; it awaits a human verdict"))
        if check.check.tolerance is None and check.check.operator.value == "within_tolerance":
            issues.append(TreeIssue(
                f"{path}{identifier}", "V3", "within_tolerance has no tolerance"))
        if (
            check.check.operator not in {CheckOperator.TOOL_SUCCEEDED, CheckOperator.MANUAL}
            and not check.check.actual_path
        ):
            # An empty path reads the whole evidence view, and that view always
            # carries status, target, relations, artifacts, warnings and errors
            # before any of the call's own outputs. A comparison against it is
            # therefore against a fixed-size object plus whatever the call
            # returned -- never what an author means, and impossible to satisfy
            # deliberately. Silently reading the wrong thing is the failure this
            # rule removes.
            issues.append(TreeIssue(
                f"{path}{identifier}", "V5",
                f"a {check.check.operator.value} check must name an actual_path; "
                "an empty one compares against the whole evidence view, not the "
                "call's output"))
        referenced.update(check.check.call_ids)

    for call in body.calls:
        if call.call_id not in referenced:
            issues.append(TreeIssue(
                f"{path}calls", "V1",
                f"call '{call.call_id}' supports no checklist item"))


def _check_composite(path: str, node: WorkflowNode, issues: list[TreeIssue]) -> None:
    """A WORKFLOW holds children and reads only descendants."""

    if node.stage is not None:
        issues.append(TreeIssue(path, "N2", "a WORKFLOW node must not carry a stage body"))
    if not node.children:
        # A composite with nothing under it can never mean anything, required or
        # not: its verdict is earned on its children's, and it has none. The schema
        # requires the ``children`` key but permits an empty list, so this is where
        # an empty one is refused -- with a message that says so, rather than a
        # oneOf report that names the stage branch and complains about the wrong
        # thing. An earlier, narrower version of this rule fired only for a
        # *required* composite, which let an optional empty one through.
        issues.append(TreeIssue(
            path, "N4", "a WORKFLOW node needs at least one child"))

    check_ids = [check.check_id for check in node.acceptance_checklist]
    if len(check_ids) != len(set(check_ids)):
        issues.append(TreeIssue(
            path, "N3", "acceptance check ids must be unique inside a node"))

    for check in node.acceptance_checklist:
        identifier = check.check_id
        operator = check.check.operator
        if not identifier or not check.check.description:
            issues.append(TreeIssue(
                path, "N3", "an acceptance check needs a check_id and a description"))
        if check.source_call_id:
            issues.append(TreeIssue(
                f"{path}{identifier}", "C2",
                "a WORKFLOW check must not use source_call_id; it reads a descendant"))
        if operator not in {CheckOperator.EQUALS, CheckOperator.MANUAL}:
            # A composite observes one descendant's verdict -- a single word. Every
            # other operator applied to a word is an accidental constant:
            # ``tool_succeeded`` and ``exists`` would always pass, ``count_equals``
            # and ``within_tolerance`` always fail, and none of them is a judgement.
            issues.append(TreeIssue(
                f"{path}{identifier}", "C4",
                f"a WORKFLOW check must use equals or manual; '{operator.value}' "
                "applied to a verdict word cannot mean anything"))
        if operator is CheckOperator.MANUAL:
            # A manual composite check awaits a human; it reads no descendant, so
            # demanding one would make it unrepresentable.
            continue
        source = check.source_node
        if not source:
            issues.append(TreeIssue(
                f"{path}{identifier}", "C3",
                "a WORKFLOW check must name a source_node"))
            continue
        if resolve_relative(node, source) is None:
            issues.append(TreeIssue(
                f"{path}{identifier}", "C3",
                f"reads '{source}', which is not a descendant of {path}"))
        if check.check.tolerance is None and operator.value == "within_tolerance":
            issues.append(TreeIssue(
                f"{path}{identifier}", "V3", "within_tolerance has no tolerance"))


def _check_acyclic(root: WorkflowNode, tree: WorkflowTree) -> list[TreeIssue]:
    """Return an issue for every dependency cycle in the tree.

    Two kinds of edge count, and both point the same way -- from a node to
    something it must wait for:

    * a composite waits for **its own children**, which is the completion rule, so
      the edge is implicit in every parent-child pair;
    * a node waits for whatever ``depends_on`` names, which may be anywhere.

    A cycle through either kind is a document that can never start. Checking only
    sibling edges, as an earlier version did, would miss the cycle a cross-branch
    dependency can close.
    """

    edges: dict[str, list[str]] = {}
    for path, node in walk(root):
        targets = list(tree.dependency_paths(path))
        targets.extend(join_path(path, child.node_id) for child in node.children)
        edges[path] = targets

    issues: list[TreeIssue] = []
    finished: set[str] = set()
    visiting: set[str] = set()
    trail: list[str] = []

    def visit(path: str) -> None:
        if path in finished:
            return
        if path in visiting:
            start = trail.index(path) if path in trail else 0
            issues.append(TreeIssue(
                path, "N6",
                "dependency cycle: " + " -> ".join((*trail[start:], path))))
            return
        visiting.add(path)
        trail.append(path)
        for target in edges.get(path, ()):
            if target in edges:
                visit(target)
        trail.pop()
        visiting.discard(path)
        finished.add(path)

    for path in edges:
        visit(path)
    return issues
