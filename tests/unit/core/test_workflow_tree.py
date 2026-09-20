"""The Workflow tree must do what a flat model cannot, and refuse what it must.

Three capabilities justify nesting, so each gets a test that would be impossible or
dishonest under flat globally-unique ids:

* **containment** -- sibling subtrees reuse the same local names without collision;
* **composite reads child** -- a parent's acceptance check reads a descendant's
  verdict, so a composite can assert something about what its children produced;
* **recursive invalidation** -- changing a deep leaf changes every ancestor's
  fingerprint, so a verdict earned by the old subtree cannot be reused.

The suite also proves the tree refuses to report success while a descendant is
unresolved, which is the failure a "did my calls return" parent would hide.
"""

from __future__ import annotations

import pytest

from ainative.acceptance.tree_evaluator import (
    blocking_paths,
    evaluate_tree,
    summarise_tree,
)
from ainative.model.checklists import (
    AcceptanceCheck,
    CheckOperator,
    CheckStatus,
    ExecutionChecklistItem,
)
from ainative.model.results import ExecutionResult, TaskStatus
from ainative.model.tools import CallTarget, ToolCall
from ainative.model.tree import (
    NodeCheck,
    NodeKind,
    StageBody,
    WorkflowNode,
    WorkflowTree,
    depth,
    node_fingerprint,
    paths,
    plan_reuse,
    tree_fingerprints,
    walk,
)
from ainative.reading.tree_validate import TreeIntegrityError, validate_tree_structure

# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #

TARGET = CallTarget(owner="blender", name="execute_blender_code")


def node_check(check_id: str, operator: CheckOperator = CheckOperator.TRUTHY,
               field: str = "ok", expected=None, tolerance=None,
               source_node: str | None = None, call_id: str | None = None) -> NodeCheck:
    """One acceptance check reading a call, or a descendant when source_node is set.

    ``source_call_id`` must name the call exactly as the stage declares it, so the
    caller passes it rather than the helper guessing from the check id.
    """

    metadata = {"source_node": source_node} if source_node else {}
    return NodeCheck(AcceptanceCheck(
        check_id=check_id,
        description=f"{check_id} must hold",
        operator=operator,
        source_call_id=None if source_node else call_id,
        actual_path=(field,),
        expected=expected,
        tolerance=tolerance,
        metadata=metadata,
    ))


def leaf(node_id: str, *, depends_on: tuple[str, ...] = (),
         operator: CheckOperator = CheckOperator.TRUTHY, field: str = "ok",
         expected=None, tolerance=None, required: bool = True) -> WorkflowNode:
    """A STAGE with one call, one execution item, and one acceptance check."""

    call_id = f"call.{node_id}"
    return WorkflowNode(
        node_id=node_id,
        kind=NodeKind.STAGE,
        purpose=f"{node_id} purpose",
        required=required,
        depends_on=depends_on,
        stage=StageBody(
            calls=(ToolCall(call_id=call_id, target=TARGET,
                            arguments={"purpose": node_id}),),
            execution_checklist=(ExecutionChecklistItem(
                item_id=f"{node_id}.done", description="work handled",
                call_ids=(call_id,)),),
            acceptance_checklist=(
                node_check(f"{node_id}.ok", operator=operator, field=field,
                           expected=expected, tolerance=tolerance, call_id=call_id),
            ),
        ),
    )


def building(alias: str, *, openings_field: str = "openings") -> WorkflowNode:
    """One building subtree: mass then facade, with a composite verdict.

    The composite check id is deliberately alias-free. An id embedding the alias
    would make two otherwise identical subtrees fingerprint differently, which
    would break the reuse the tree exists to provide.
    """

    return WorkflowNode(
        node_id=alias,
        kind=NodeKind.WORKFLOW,
        purpose="a building",
        children=(
            leaf("mass", operator=CheckOperator.WITHIN_TOLERANCE, field="min_z",
                 expected=0.0, tolerance=0.02),
            leaf("facade", depends_on=("../mass",),
                 operator=CheckOperator.WITHIN_TOLERANCE, field=openings_field,
                 expected=40, tolerance=10),
        ),
        acceptance_checklist=(
            node_check("building.built", operator=CheckOperator.EQUALS,
                       expected="pass", source_node="facade"),
        ),
    )


def city(*, openings_field: str = "openings") -> WorkflowNode:
    """Two buildings that reuse identical local names, plus sidewalks."""

    return WorkflowNode(
        node_id="city",
        kind=NodeKind.WORKFLOW,
        purpose="the whole city",
        children=(
            building("tower_a", openings_field=openings_field),
            building("tower_b", openings_field=openings_field),
            leaf("sidewalks", field="continuous"),
        ),
        acceptance_checklist=(
            node_check("city.all_buildings", operator=CheckOperator.EQUALS,
                       expected="pass", source_node="tower_a"),
        ),
    )


def tree(root: WorkflowNode | None = None) -> WorkflowTree:
    return WorkflowTree(workflow_id="procedural-city", root=root or city(),
                )

def results_for(root: WorkflowNode) -> dict[tuple[str, str], ExecutionResult]:
    """Reported results where every call succeeds and every value passes.

    A call id is scoped to the STAGE that declares it, so the results are keyed by
    ``(node path, call id)``.
    """

    out: dict[tuple[str, str], ExecutionResult] = {}
    for path, node in walk(root):
        if node.is_leaf and node.stage is not None:
            for call in node.stage.calls:
                out[(path, call.call_id)] = ExecutionResult(
                    call_id=call.call_id, status=TaskStatus.SUCCEEDED, target=TARGET,
                    outputs={"ok": True, "min_z": 0.0, "openings": 42,
                             "continuous": True})
    return out


# --------------------------------------------------------------------------- #
# The three capabilities
# --------------------------------------------------------------------------- #


def test_sibling_subtrees_reuse_local_names_without_collision():
    """Containment: two subtrees both declare ``mass`` and ``facade``."""

    all_paths = paths(city())
    assert len(all_paths) == len(set(all_paths)), "paths must be unique"

    facades = [p for p in all_paths if p.endswith("/facade/")]
    assert facades == ["/tower_a/facade/", "/tower_b/facade/"], facades

    validate_tree_structure(tree())


def test_a_composite_check_reads_a_descendant_verdict():
    """A parent asserts something about what its children produced."""

    root = city()
    result = evaluate_tree(tree(root), results_for(root))

    assert result.status is CheckStatus.PASS
    tower_a = next(c for c in result.children if c.node_id == "tower_a")
    assert tower_a.status is CheckStatus.PASS

    city_check = next(c for c in result.check_results
                      if c.check_id == "city.all_buildings")
    assert city_check.status is CheckStatus.PASS
    _, value = city_check.actual, city_check.actual
    assert value == CheckStatus.PASS.value


def test_a_deep_leaf_change_invalidates_every_ancestor():
    """Recursive fingerprints: a facade change must invalidate its parents."""

    before = tree_fingerprints(city())
    after = tree_fingerprints(city(openings_field="recessed_openings"))

    changed = {p for p in before if before[p] != after.get(p)}
    assert "/tower_a/facade/" in changed
    assert "/tower_a/" in changed, "the composite above the changed leaf must change"
    assert "/" in changed, "the root must change"
    assert "/sidewalks/" not in changed, "an untouched branch must not change"


def test_reuse_stops_at_an_unchanged_subtree():
    """An unchanged branch is reused whole; the walk does not descend into it."""

    plan = plan_reuse(city(), city(openings_field="recessed_openings"))

    assert "/sidewalks/" in plan.reusable
    assert "/tower_a/" in plan.changed
    assert "/tower_a/facade/" in plan.changed
    # tower_b's facade has the same field rename, so it changes too.
    assert "/tower_b/" in plan.changed


# --------------------------------------------------------------------------- #
# Completion rules
# --------------------------------------------------------------------------- #


def test_missing_evidence_blocks_the_parent_and_the_root():
    """E1/E2: absence of evidence is never success."""

    root = city()
    results = {key: value for key, value in results_for(root).items()
               if not key[1].startswith("call.facade")}
    result = evaluate_tree(tree(root), results)

    assert result.status is not CheckStatus.PASS
    blockers = blocking_paths(result)
    assert len(blockers) >= 2, blockers


def test_a_failing_measured_value_propagates_up_the_tree():
    """E3: a failing grandchild fails its parent and the root."""

    root = city()
    results = results_for(root)
    for key in [k for k in results if k[1].startswith("call.facade")]:
        results[key] = ExecutionResult(
            call_id=key[1], status=TaskStatus.SUCCEEDED, target=TARGET,
            outputs={"ok": True, "openings": 3})
    result = evaluate_tree(tree(root), results)

    assert result.status is CheckStatus.FAIL
    assert blocking_paths(result)


def test_an_omitted_optional_node_does_not_fail_its_parent():
    """E4: an optional node may be omitted; it is never reported as ``pass``.

    The status is ``unknown`` rather than a new ``skipped`` value, because the
    engine's vocabulary is fixed at pass / warn / fail / unknown / needs_human. The
    ``skipped`` flag records why, so an omitted optional node is distinguishable
    from an unresolved required one.
    """

    root = WorkflowNode(
        node_id="city", kind=NodeKind.WORKFLOW, purpose="the city",
        children=(leaf("required_part", field="ok"),
                  leaf("optional_part", field="ok", required=False)),
    )
    result = evaluate_tree(tree(root), results_for(root),
                           skipped_paths=frozenset({"/optional_part/"}))

    omitted = next(c for c in result.children if c.node_id == "optional_part")
    assert omitted.status is CheckStatus.UNKNOWN, "no evidence exists for work not run"
    assert omitted.skipped is True
    assert omitted.status is not CheckStatus.PASS
    assert result.status is CheckStatus.PASS, "an omitted optional node is not a blocker"
    assert "/optional_part/" not in blocking_paths(result)


def test_an_unresolved_required_child_makes_the_parent_unknown_not_failed():
    """E2 versus E3: 'we could not tell' is not 'it broke'."""

    root = WorkflowNode(
        node_id="city", kind=NodeKind.WORKFLOW, purpose="the city",
        children=(leaf("a", field="ok"), leaf("b", field="ok")),
    )
    results = results_for(root)
    # Drop b's evidence: its check becomes unknown, not failed.
    results = {key: value for key, value in results.items() if key[1] != "call.b"}
    result = evaluate_tree(tree(root), results)

    assert result.status is CheckStatus.UNKNOWN, result.status
    assert result.status is not CheckStatus.FAIL


def test_a_human_check_makes_the_node_unknown_not_passed():
    """E2: a ``manual`` check cannot be silently treated as satisfied."""

    root = WorkflowNode(
        node_id="city", kind=NodeKind.WORKFLOW, purpose="the city",
        children=(WorkflowNode(
            node_id="part", kind=NodeKind.WORKFLOW, purpose="part",
            children=(leaf("work"),),
            acceptance_checklist=(
                NodeCheck(AcceptanceCheck(
                    check_id="part.looks_right",
                    description="a human must judge this",
                    operator=CheckOperator.MANUAL,
                    metadata={"source_node": "work"},
                )),
            ),
        ),),
    )
    result = evaluate_tree(tree(root), results_for(root))
    assert result.status is CheckStatus.UNKNOWN


# --------------------------------------------------------------------------- #
# Structural rejection
# --------------------------------------------------------------------------- #


def bad_tree(root: WorkflowNode) -> WorkflowTree:
    return WorkflowTree(workflow_id="bad", root=root)


#: One entry per structural rule: ``(label, tree, fragment of the message)``.
#: ``test_every_rule_the_validator_can_emit_has_a_test_case`` reads this list, so a
#: new rule without a case here fails the suite.
MALFORMED_TREES: list[tuple[str, WorkflowNode, str]] = [
    (
        "a stage with children",
        WorkflowNode(node_id="bad", kind=NodeKind.STAGE, purpose="bad",
                     children=(leaf("child"),),
                     stage=StageBody(
                         calls=(ToolCall("c", TARGET),),
                         execution_checklist=(ExecutionChecklistItem(
                             "i", "d", call_ids=("c",)),),
                         acceptance_checklist=(
                             NodeCheck(AcceptanceCheck("k", "d",
                                                       operator=CheckOperator.TRUTHY,
                                                       source_call_id="c")),),)),
        "must not have children",
    ),
    (
        "a call supporting no checklist item",
        WorkflowNode(node_id="bad", kind=NodeKind.STAGE, purpose="bad",
                     stage=StageBody(
                         calls=(ToolCall("c1", TARGET), ToolCall("c2", TARGET)),
                         execution_checklist=(ExecutionChecklistItem(
                             "i", "d", call_ids=("c1",)),),
                         acceptance_checklist=(
                             NodeCheck(AcceptanceCheck("k", "d",
                                                       operator=CheckOperator.TRUTHY,
                                                       source_call_id="c1")),),)),
        "supports no checklist item",
    ),
    (
        "a composite reading a missing descendant",
        WorkflowNode(node_id="bad", kind=NodeKind.WORKFLOW, purpose="bad",
                     children=(leaf("only"),),
                     acceptance_checklist=(node_check(
                         "k", operator=CheckOperator.EQUALS, expected="pass",
                         source_node="ghost"),)),
        "not a descendant",
    ),
    (
        "a composite check using a non-verdict operator",
        WorkflowNode(node_id="bad", kind=NodeKind.WORKFLOW, purpose="bad",
                     children=(leaf("only"),),
                     acceptance_checklist=(node_check("k", source_node="only"),)),
        "must use equals or manual",
    ),
    (
        "a sibling dependency cycle",
        WorkflowNode(node_id="bad", kind=NodeKind.WORKFLOW, purpose="bad",
                     children=(leaf("a", depends_on=("../b",)),
                               leaf("b", depends_on=("../a",)))),
        "dependency cycle",
    ),
    (
        "a dependency naming no node",
        WorkflowNode(node_id="bad", kind=NodeKind.WORKFLOW, purpose="bad",
                     children=(leaf("a", depends_on=("../../elsewhere",)),)),
        "names no node",
    ),
    (
        # A bare id parses as the declaring node's own CHILD -- something it already
        # waits for -- so it is not a dependency at all. The message gives the
        # spelling that was meant, because that is the whole mistake.
        "a dependency written as a bare sibling id",
        WorkflowNode(node_id="bad", kind=NodeKind.WORKFLOW, purpose="bad",
                     children=(leaf("mass"), leaf("facade", depends_on=("mass",)))),
        "write it '../mass'",
    ),
    (
        "an absolute dependency",
        WorkflowNode(node_id="bad", kind=NodeKind.WORKFLOW, purpose="bad",
                     children=(leaf("a", depends_on=("/bad/a/",)),)),
        "is absolute",
    ),
    (
        "a stage check using source_node",
        WorkflowNode(node_id="bad", kind=NodeKind.WORKFLOW, purpose="bad",
                     children=(WorkflowNode(
                         node_id="s", kind=NodeKind.STAGE, purpose="s",
                         stage=StageBody(
                             calls=(ToolCall("c", TARGET),),
                             execution_checklist=(ExecutionChecklistItem(
                                 "i", "d", call_ids=("c",)),),
                             acceptance_checklist=(
                                 node_check("k", source_node="other"),),)),)),
        "must not use source_node",
    ),
    (
        "a composite check using source_call_id",
        WorkflowNode(node_id="bad", kind=NodeKind.WORKFLOW, purpose="bad",
                     children=(leaf("only"),),
                     acceptance_checklist=(NodeCheck(AcceptanceCheck(
                         "k", "d", operator=CheckOperator.EQUALS, expected="pass",
                         source_call_id="call.only")),)),
        "must not use source_call_id",
    ),
    (
        "within_tolerance with no tolerance",
        WorkflowNode(node_id="bad", kind=NodeKind.WORKFLOW, purpose="bad",
                     children=(leaf("x", operator=CheckOperator.WITHIN_TOLERANCE,
                                    field="n", expected=1),)),
        "no tolerance",
    ),
    (
        "two siblings sharing a node_id",
        WorkflowNode(node_id="bad", kind=NodeKind.WORKFLOW, purpose="bad",
                     children=(leaf("same"), leaf("same"))),
        "duplicate sibling node_id",
    ),
    (
        "a workflow node carrying a stage body",
        WorkflowNode(node_id="bad", kind=NodeKind.WORKFLOW, purpose="bad",
                     children=(leaf("only"),),
                     stage=StageBody(calls=(ToolCall("c", TARGET),))),
        "must not carry a stage body",
    ),
    (
        "a workflow with no children",
        WorkflowNode(node_id="bad", kind=NodeKind.WORKFLOW, purpose="bad"),
        "needs at least one child",
    ),
    (
        # An OPTIONAL empty composite is just as meaningless as a required one, and
        # an earlier version of the rule let it through by checking `required`
        # first. Its verdict is earned on its children's, and it has none.
        "an optional workflow with no children",
        WorkflowNode(node_id="bad", kind=NodeKind.WORKFLOW, purpose="bad",
                     required=False),
        "needs at least one child",
    ),
    (
        "a required stage with no execution checklist",
        WorkflowNode(node_id="bad", kind=NodeKind.STAGE, purpose="bad",
                     stage=StageBody(
                         calls=(ToolCall("c", TARGET),),
                         acceptance_checklist=(
                             NodeCheck(AcceptanceCheck(
                                 "k", "d", operator=CheckOperator.TRUTHY,
                                 source_call_id="c")),))),
        "must freeze an execution checklist",
    ),
    (
        "a required stage with no acceptance checklist",
        WorkflowNode(node_id="bad", kind=NodeKind.STAGE, purpose="bad",
                     stage=StageBody(
                         calls=(ToolCall("c", TARGET),),
                         execution_checklist=(ExecutionChecklistItem(
                             "i", "d", call_ids=("c",)),))),
        "must freeze an acceptance checklist",
    ),
    (
        "an execution item referencing an undeclared call",
        WorkflowNode(node_id="bad", kind=NodeKind.STAGE, purpose="bad",
                     stage=StageBody(
                         calls=(ToolCall("c", TARGET),),
                         execution_checklist=(ExecutionChecklistItem(
                             "i", "d", call_ids=("c", "ghost")),),
                         acceptance_checklist=(
                             NodeCheck(AcceptanceCheck(
                                 "k", "d", operator=CheckOperator.TRUTHY,
                                 source_call_id="c")),))),
        "undeclared calls",
    ),
    (
        "a check reading an undeclared call",
        WorkflowNode(node_id="bad", kind=NodeKind.STAGE, purpose="bad",
                     stage=StageBody(
                         calls=(ToolCall("c", TARGET),),
                         execution_checklist=(ExecutionChecklistItem(
                             "i", "d", call_ids=("c",)),),
                         acceptance_checklist=(
                             NodeCheck(AcceptanceCheck(
                                 "k", "d", operator=CheckOperator.TRUTHY,
                                 source_call_id="ghost")),))),
        "undeclared call",
    ),
]


@pytest.mark.parametrize(("label", "root", "fragment"), MALFORMED_TREES,
                         ids=[case[0] for case in MALFORMED_TREES])
def test_the_validator_rejects_malformed_trees(label, root, fragment):
    """Every structural rule fires, and the message names the cause."""

    del label
    with pytest.raises(TreeIntegrityError) as caught:
        validate_tree_structure(bad_tree(root))
    assert fragment in str(caught.value), str(caught.value)


def _rules_emitted_by(source: str) -> set[str]:
    """Return every rule id a validator source can report."""

    import re

    emitted: set[str] = set()
    for match in re.finditer(r"TreeIssue\(", source):
        hit = re.search(r"[\"']([A-Z]\d+)[\"']", source[match.end():match.end() + 400])
        if hit:
            emitted.add(hit.group(1))
    return emitted


def _rules_triggered_by(cases) -> set[str]:
    """Return every rule id the given malformed cases actually report."""

    triggered: set[str] = set()
    for _label, root, _fragment in cases:
        try:
            validate_tree_structure(bad_tree(root))
        except TreeIntegrityError as exc:
            triggered.update(issue.rule for issue in exc.issues)
    return triggered


def _uncovered(source: str, cases) -> list[str]:
    """Return rules the validator can emit that no case triggers."""

    return sorted(_rules_emitted_by(source) - _rules_triggered_by(cases))


def _validator_source() -> str:
    from pathlib import Path

    return Path("src/ainative/reading/tree_validate.py").read_text(encoding="utf-8")


def test_every_rule_the_validator_can_emit_has_a_test_case():
    """Coverage of the rule table is enforced here, not asserted in prose.

    The spec lists the rules. This reads the rule ids the validator can actually
    report and the ids the cases above actually trigger, and fails when a rule
    exists that no case exercises. A documented rule with no case is a claim
    nobody checks.
    """

    emitted = _rules_emitted_by(_validator_source())
    assert emitted, "no rules were discovered; the discovery pattern is wrong"
    assert not _uncovered(_validator_source(), MALFORMED_TREES), (
        "the validator can emit rules that no case triggers: "
        f"{_uncovered(_validator_source(), MALFORMED_TREES)}")


def test_the_coverage_check_actually_detects_an_uncovered_rule():
    """Prove the check bites, on a synthetic source rather than the real one.

    Injecting into the real validator was tried and does not work: appending an
    extra issue just before the raise adds it to *every* failing case, so it
    always looks covered. Feeding a synthetic source to the same helpers proves
    the comparison without depending on the injection point.
    """

    synthetic = _validator_source() + '\n    issues.append(TreeIssue("/", "Z9", "x"))\n'

    assert "Z9" in _rules_emitted_by(synthetic)
    assert "Z9" in _uncovered(synthetic, MALFORMED_TREES), (
        "the coverage comparison failed to notice an untested rule")
    assert "Z9" not in _uncovered(_validator_source(), MALFORMED_TREES)


def test_the_validator_accepts_a_correct_tree():
    """Positive control, so the suite cannot pass by rejecting everything."""

    validate_tree_structure(tree())


def test_a_correct_tree_evaluates_to_pass():
    """Positive control for the evaluator."""

    root = city()
    result = evaluate_tree(tree(root), results_for(root))

    assert result.status is CheckStatus.PASS
    counts = summarise_tree(result)
    assert counts.get("pass", 0) == len(paths(root))
    assert depth(root) == 3


def test_the_tree_serialises_and_round_trips_its_kind():
    """A tree arrives as JSON, where ``kind`` is a bare string."""

    document = tree().to_dict()
    assert document["root"]["kind"] == "workflow"

    rebuilt = WorkflowNode(
        node_id=document["root"]["node_id"], kind=document["root"]["kind"],
        purpose=document["root"]["purpose"])
    assert rebuilt.kind is NodeKind.WORKFLOW
    assert rebuilt.is_leaf is False


def test_fingerprints_are_memoised_across_a_whole_tree_comparison():
    """A deep tree must not be re-digested once per ancestor.

    Without a shared memo, comparing two revisions re-walks the subtree beneath
    every node it descends through, so the cost grows with nodes x depth. The tree
    here is deep enough and *changed* at a deep leaf, which forces the comparison
    to descend -- an unchanged tree exits at the root and would prove nothing.

    The assertion counts fingerprint calls rather than wall time, because a timing
    assertion on a fast machine is flaky.
    """

    import ainative.model.tree as tree_module

    def build(retuned: bool) -> WorkflowNode:
        """root -> 3 groups -> 3 subgroups -> 4 leaves, one leaf retunable.

        ``retuned`` changes exactly one deep leaf's tolerance, so the comparison
        must descend to that leaf and back up through its ancestors.
        """

        def leaf_node(name: str, tol: float) -> WorkflowNode:
            call_id = f"call.{name}"
            return WorkflowNode(
                node_id=name, kind=NodeKind.STAGE, purpose=name,
                stage=StageBody(
                    calls=(ToolCall(call_id, TARGET),),
                    execution_checklist=(ExecutionChecklistItem(
                        f"{name}.done", "d", call_ids=(call_id,)),),
                    acceptance_checklist=(node_check(
                        f"{name}.ok", operator=CheckOperator.WITHIN_TOLERANCE,
                        field="n", expected=1, tolerance=tol, call_id=call_id),),
                ),
            )

        return WorkflowNode(
            node_id="root", kind=NodeKind.WORKFLOW, purpose="root",
            children=tuple(
                WorkflowNode(
                    node_id=f"group{i}", kind=NodeKind.WORKFLOW, purpose="group",
                    children=tuple(
                        WorkflowNode(
                            node_id=f"sub{i}_{k}", kind=NodeKind.WORKFLOW,
                            purpose="sub",
                            children=tuple(
                                leaf_node(f"work{i}_{k}_{j}",
                                          2.0 if retuned and (i, k, j) == (0, 0, 0)
                                          else 1.0)
                                for j in range(4)),
                        )
                        for k in range(3)
                    ),
                )
                for i in range(3)
            ),
        )

    before = build(retuned=False)
    after = build(retuned=True)

    calls = {"n": 0}
    original = tree_module.node_fingerprint

    def counting(node, _cache=None):
        calls["n"] += 1
        return original(node, _cache)

    tree_module.node_fingerprint = counting
    try:
        plan = plan_reuse(before, after)
    finally:
        tree_module.node_fingerprint = original

    node_total = len(paths(before))
    assert plan.changed, "the comparison must actually descend for this test to mean anything"
    # Two trees, each node digested about once: allow 3x for the comparison's own
    # top-level calls. Without the memo this is ~5x on this shape and grows with
    # depth.
    assert calls["n"] <= node_total * 3, (
        f"{calls['n']} fingerprint calls for {node_total} nodes over two trees "
        f"indicates the memo is not shared")


def test_a_renamed_node_keeps_its_fingerprint_when_content_is_unchanged():
    """``node_id`` is excluded from the fingerprint, so a rename is not a change.

    The subtree is built twice with different aliases. Everything the fingerprint
    covers is identical; only ``node_id`` differs. Note that a check id embedding
    the alias *is* part of the content, so this builder deliberately does not do
    that -- a rename that rewrites check ids is a real change, not a rename.
    """

    def subtree(alias: str) -> WorkflowNode:
        return WorkflowNode(
            node_id=alias, kind=NodeKind.WORKFLOW, purpose="a building",
            children=(leaf("mass"),),
            acceptance_checklist=(node_check("built", source_node="mass"),),
        )

    assert node_fingerprint(subtree("tower_a")) == node_fingerprint(subtree("tower_b"))
    assert node_fingerprint(subtree("tower_a")) != node_fingerprint(
        WorkflowNode(node_id="tower_a", kind=NodeKind.WORKFLOW, purpose="a building",
                     children=(leaf("mass"),))), "dropping a check is a real change"


# --------------------------------------------------------------------------- #
# Cross-branch dependencies
# --------------------------------------------------------------------------- #
#
# A reference is walked FROM the declaring node, so a stage buried in one branch
# can wait for a single node in another. That is what a sibling id could not say,
# and it is why the field stopped taking one.


def cross_branch_tree(reverse: bool = False) -> WorkflowTree:
    """Two branches, with the buildings one waiting on the site one.

    ``/buildings/tower/`` is three levels down, so reaching ``/site/ground/`` is
    ``../../site/ground``. ``reverse`` points the second edge back the other way,
    which closes a cycle across the two branches.
    """

    ground = leaf("ground", depends_on=("../../buildings/tower",) if reverse else ())
    tower = leaf("tower", depends_on=("../../site/ground",))
    return WorkflowTree(
        workflow_id="probe",
        root=WorkflowNode(
            node_id="city", kind=NodeKind.WORKFLOW, purpose="the city",
            children=(
                WorkflowNode(node_id="site", kind=NodeKind.WORKFLOW, purpose="the site",
                             children=(ground,)),
                WorkflowNode(node_id="buildings", kind=NodeKind.WORKFLOW,
                             purpose="the buildings", children=(tower,)),
            ),
        ),
    )


def test_a_dependency_may_point_into_another_branch():
    """The capability the field exists for: one node gating on one other node."""

    tree = cross_branch_tree()

    validate_tree_structure(tree)
    assert tree.dependency_paths("/buildings/tower/") == ("/site/ground/",)


def test_a_reference_that_climbs_above_the_root_names_nothing():
    """'..' at the root has nowhere to go, so it resolves to no node rather than
    clamping to the root -- which would silently turn it into a real dependency."""

    tree = cross_branch_tree()
    assert tree.resolve_dependency("/", "../../anything") is None
    assert tree.resolve_dependency("/site/ground/", "../../../site/ground") is None


def test_a_cycle_closing_across_branches_is_rejected():
    """Two branches waiting on each other can never start, and the old check --
    which only walked sibling edges -- could not see it."""

    with pytest.raises(TreeIntegrityError) as caught:
        validate_tree_structure(cross_branch_tree(reverse=True))

    assert "dependency cycle" in str(caught.value), str(caught.value)


def test_written_order_carries_no_meaning():
    """Only ``depends_on`` orders anything.

    A node written FIRST may depend on one written after it, and the validator
    accepts it: ``late`` here is declared before ``early`` and runs after it. An
    author who assumed written order was an ordering would get a document that runs
    in an order they did not intend, and nothing would say so -- which is why the
    spec states the rule outright rather than leaving it to be inferred.
    """

    late = leaf("late", depends_on=("../early",))
    early = leaf("early")
    tree = WorkflowTree(
        workflow_id="probe",
        root=WorkflowNode(node_id="city", kind=NodeKind.WORKFLOW, purpose="the city",
                          children=(late, early)),
    )

    validate_tree_structure(tree)

    assert tree.dependency_paths("/late/") == ("/early/",)
    assert tree.dependency_paths("/early/") == (), "no dependency, no ordering"


def test_a_node_cannot_wait_for_its_own_ancestor():
    """The parent-child edge is the completion rule, not a declaration.

    A composite completes only once its children have, so a node waiting for an
    ancestor is waiting for itself. Nothing in ``depends_on`` says so -- the loop
    closes through the implicit edge, which is why the cycle check has to include
    it. ``..`` is the shortest way to write this mistake.
    """

    tree = WorkflowTree(
        workflow_id="probe",
        root=WorkflowNode(
            node_id="city", kind=NodeKind.WORKFLOW, purpose="the city",
            children=(
                WorkflowNode(node_id="buildings", kind=NodeKind.WORKFLOW,
                             purpose="the buildings",
                             children=(leaf("tower", depends_on=("..",)),)),
            ),
        ),
    )

    with pytest.raises(TreeIntegrityError) as caught:
        validate_tree_structure(tree)

    assert "dependency cycle" in str(caught.value), str(caught.value)
