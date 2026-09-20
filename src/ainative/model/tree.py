"""A Workflow as a tree of nodes.

The two-level model (``Workflow -> Step -> Stage``, flat globally-unique stage
ids, dependencies strictly backwards) cannot express three things a scene needs:

* **containment** -- "a city contains buildings, which contain facades" degrades
  into a naming convention (``building_037_facade``) instead of structure;
* **composite verdicts** -- a parent cannot assert anything about what its
  children produced; it can only check that its own calls returned;
* **per-instance verification** -- 300 buildings become 600 hand-mangled ids, with
  no way to ask whether one building passed except by parsing names.

Here a Workflow *is* a tree. A node is either a **WORKFLOW** (composite, holds
children) or a **STAGE** (leaf, holds calls and its frozen checklists). A phase is
not a separate type: a phase is a WORKFLOW node used for grouping.

Everything else follows from recursion instead of being special-cased:

* identity is a **path**, so sibling subtrees may reuse local names;
* a composite reads a child through ``source_node``, so it can assert something
  about what the child produced;
* fingerprints are **recursive**, so a change in a deep leaf invalidates every
  ancestor whose completion depended on it.

This module is pure data plus derivation. It constructs no Workflow and orders no
node: the Agent authors the tree, and this repository judges it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .checklists import AcceptanceCheck, CheckStatus, StageKind
from .coercion import coerce_enum
from .tools import ToolCall

#: A :class:`CheckStatus` a required item counts as satisfied by.
SATISFIED_STATUSES = frozenset({CheckStatus.PASS})

#: Verdicts that count as **complete**, which is not the same as satisfied. A
#: warning is a degradation the caller must see; it is not unfinished work, so a
#: warned node closes and the task reports ``degraded`` rather than ``blocked``.
COMPLETE_STATUSES = frozenset({CheckStatus.PASS, CheckStatus.WARN})

#: Statuses that do not satisfy a required item and are not a hard failure.
#: A verdict earned on incomplete evidence is not a verdict, so these block.
UNRESOLVED_STATUSES = frozenset({CheckStatus.UNKNOWN, CheckStatus.NEEDS_HUMAN})


class WorkflowStatus(StrEnum):
    """Lifecycle state of one immutable Workflow revision.

    Two different readers use this, and they ask different questions:

    * `session_api/guide.py` asks whether the revision can still be opened, so it
      only separates terminal values from live ones;
    * `acceptance/aggregation.py` asks how far the run got, and its answer reaches
      `TaskResult.workflow_status` on every `finish`.

    That second reader is why `running` and `suspended` are distinct rather than both
    collapsing into "not finished", and why every value here has a producer. A value
    no code writes is a word an author can choose and the engine will never emit --
    `feasible` was one, and was removed.
    """

    DRAFT = "draft"
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALID = "invalid"
    SUPERSEDED = "superseded"


class NodeKind(StrEnum):
    """What a node is: a composite, or a unit of work."""

    WORKFLOW = "workflow"
    STAGE = "stage"


@dataclass(frozen=True, slots=True)
class ExecutionItem:
    """One thing a Stage must handle, so work cannot be silently omitted."""

    item_id: str
    description: str
    required: bool = True
    call_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "description": self.description,
            "required": self.required,
            "call_ids": list(self.call_ids),
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class NodeCheck:
    """One condition that must hold for a node to be complete.

    A check reads from exactly one source, and which source is legal depends on
    the node's kind:

    * ``source_call_id`` -- a STAGE reading one of its own calls;
    * ``source_node``    -- a WORKFLOW reading a **descendant**, by path relative
      to itself. This is the capability a flat model cannot express.

    ``AcceptanceCheck`` already carries both fields plus the operator vocabulary,
    so the tree reuses it rather than defining a parallel type.
    """

    check: AcceptanceCheck

    @property
    def check_id(self) -> str:
        return self.check.check_id

    @property
    def source_call_id(self) -> str | None:
        return self.check.source_call_id

    @property
    def source_node(self) -> str | None:
        """Return the descendant this check reads.

        The schema declares ``source_node`` as a property of a node check, so that
        is where a document puts it. ``AcceptanceCheck`` has no such field, so the
        value is carried in ``metadata`` and read from there.

        ``metadata['source_node']`` is the only place it is read from. An earlier
        version also accepted it nowhere else, and a document written to the schema
        resolved no descendant at all -- the two spellings have to agree, and the
        schema is the one an author reads.
        """

        value = self.check.metadata.get("source_node")
        return str(value) if value else None

    def to_dict(self) -> dict[str, Any]:
        """Return the check in the shape the spec declares for a composite.

        Two deliberate departures from ``AcceptanceCheck.to_dict()``, both of them
        toward the spec rather than away from it:

        * ``call_ids`` is dropped. A composite reads a descendant, so a call list
          on one is meaningless and the spec forbids the field; emitting the stored
          shape produced a document the spec rejects, which no test noticed until
          ``to_dict`` was checked against the schema at all.
        * ``source_node`` is lifted out of ``metadata`` to the top level, which is
          where the spec puts it. The reader accepts both spellings, so a document
          written either way still loads -- but what this model EMITS should be
          what an author would have written.
        """

        payload = self.check.to_dict()
        payload.pop("call_ids", None)

        source = self.source_node
        if source:
            payload["source_node"] = source
            metadata = dict(payload.get("metadata") or {})
            metadata.pop("source_node", None)
            payload["metadata"] = metadata
        return payload


@dataclass(frozen=True, slots=True)
class StageBody:
    """The work a leaf STAGE declares."""

    calls: tuple[ToolCall, ...] = ()
    execution_checklist: tuple[ExecutionItem, ...] = ()
    acceptance_checklist: tuple[NodeCheck, ...] = ()
    #: Which lifecycle this leaf follows. It changes what must be frozen before
    #: the first side effect, so it is part of the definition, not a label: the
    #: three kinds are documented in AGENTS.md and the flat model carried them.
    stage_kind: StageKind = StageKind.CHANGE

    def __post_init__(self) -> None:
        coerce_enum(self, "stage_kind", StageKind)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_kind": self.stage_kind.value,
            "calls": [call.to_dict() for call in self.calls],
            "execution_checklist": [item.to_dict() for item in self.execution_checklist],
            "acceptance_checklist": [check.to_dict() for check in self.acceptance_checklist],
        }


@dataclass(frozen=True, slots=True)
class WorkflowNode:
    """One node of a Workflow tree.

    ``node_id`` is unique among **siblings** only. Uniqueness across the tree is
    supplied by the path, and that is what makes containment work: two subtrees
    may each declare a ``mass`` stage without collision.
    """

    node_id: str
    kind: NodeKind
    purpose: str
    required: bool = True
    #: References to nodes that must complete before this one runs, written
    #: **from this node**: ``..`` is its parent, so ``../mass`` is a sibling and
    #: ``../../site/street-trees`` reaches into another branch. Relative rather
    #: than absolute on purpose -- a reusable subtree does not know where it will
    #: be placed, so a fragment could not name its own siblings by absolute path.
    depends_on: tuple[str, ...] = ()
    stage: StageBody | None = None            # kind == STAGE
    children: tuple[WorkflowNode, ...] = ()  # kind == WORKFLOW
    acceptance_checklist: tuple[NodeCheck, ...] = ()  # kind == WORKFLOW
    recovery: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # The tree arrives as JSON, where ``kind`` is a bare string. Coercing here
        # keeps ``is_leaf`` correct for every caller instead of making each one
        # remember to convert first.
        coerce_enum(self, "kind", NodeKind)

    @property
    def is_leaf(self) -> bool:
        """Return True when this node is a STAGE."""

        return self.kind is NodeKind.STAGE

    @property
    def declared_checks(self) -> tuple[NodeCheck, ...]:
        """Return this node's acceptance checks, wherever its kind keeps them.

        A STAGE owns its checks inside its stage body; a WORKFLOW owns them on the
        node itself. Reading the wrong one returns an **empty tuple**, so a
        consumer that gets the rule wrong does not fail -- it evaluates nothing and
        reports a pass. That is a silent false pass, and it is the reason this
        accessor exists rather than the rule being restated at each call site.
        """

        if self.is_leaf and self.stage is not None:
            return self.stage.acceptance_checklist
        return self.acceptance_checklist

    @property
    def declared_calls(self) -> tuple[ToolCall, ...]:
        """Return the calls this node declares. A composite declares none."""

        return self.stage.calls if self.stage is not None else ()

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "node_id": self.node_id,
            "kind": self.kind.value,
            "purpose": self.purpose,
            "required": self.required,
            "depends_on": list(self.depends_on),
        }
        if self.recovery:
            out["recovery"] = self.recovery
        if self.metadata:
            out["metadata"] = self.metadata
        if self.kind is NodeKind.STAGE and self.stage is not None:
            out["stage"] = self.stage.to_dict()
        if self.kind is NodeKind.WORKFLOW:
            out["children"] = [child.to_dict() for child in self.children]
            if self.acceptance_checklist:
                out["acceptance_checklist"] = [
                    check.to_dict() for check in self.acceptance_checklist
                ]
        return out


@dataclass(frozen=True, slots=True)
class WorkflowTree:
    """One immutable revision of an Agent-authored Workflow tree."""

    workflow_id: str
    root: WorkflowNode
    revision: int = 1
    status: WorkflowStatus = WorkflowStatus.DRAFT
    supersedes_workflow_id: str | None = None
    recovery_pointer: str | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # ``status`` arrives as a bare string from JSON, and ``to_dict`` reaches for
        # ``.value`` on it, so it is coerced where it enters.
        coerce_enum(self, "status", WorkflowStatus)

    @property
    def revision_id(self) -> str:
        base = self.workflow_id or "workflow"
        return f"{base}:r{self.revision}"

    @property
    def node_count(self) -> int:
        return sum(1 for _ in walk(self.root))

    @property
    def leaf_count(self) -> int:
        return sum(1 for _path, node in walk(self.root) if node.is_leaf)

    # -- Derived views the acceptance loop addresses nodes through --
    #
    # A node's identity is its path, not its ``node_id``: ids are unique only
    # among siblings, which is what lets two subtrees each declare a ``mass``.
    # Every accessor below is therefore keyed by path.

    @property
    def stages(self) -> tuple[tuple[str, WorkflowNode], ...]:
        """Return every STAGE node with its path, parents before children."""

        return tuple(leaves(self.root))

    @property
    def nodes(self) -> tuple[tuple[str, WorkflowNode], ...]:
        """Return every node with its path, parents before children."""

        return tuple(walk(self.root))

    @property
    def stage_paths(self) -> tuple[str, ...]:
        return tuple(path for path, _node in leaves(self.root))

    @property
    def composite_paths(self) -> tuple[str, ...]:
        return tuple(path for path, node in walk(self.root) if not node.is_leaf)

    @property
    def calls(self) -> tuple[ToolCall, ...]:
        """Return every declared call, in tree order."""

        return tuple(
            call
            for _path, node in walk(self.root)
            if node.is_leaf and node.stage is not None
            for call in node.stage.calls
        )

    @property
    def required_paths(self) -> frozenset[str]:
        """Return the paths of every required node."""

        return frozenset(path for path, node in walk(self.root) if node.required)

    def node_at(self, path: str) -> WorkflowNode | None:
        """Return the node at an absolute path, or None.

        Accepts a bare ``node_id`` as well, but only when exactly one node in the
        tree carries it: an ambiguous name is reported as missing rather than
        resolved by picking one, because silently judging the wrong subtree is
        worse than refusing.
        """

        found = resolve(self.root, path)
        if found is not None:
            return found
        if "/" in path.strip("/") or not path.strip("/"):
            return None
        matches = [node for _p, node in walk(self.root) if node.node_id == path]
        return matches[0] if len(matches) == 1 else None

    def path_of_call(self, call_id: str) -> str | None:
        """Return the path of the STAGE that declares a call, or None.

        Only when exactly one STAGE declares it. A call id is scoped to the STAGE
        that declares it -- ``execution_checklist`` and ``source_call_id`` both
        resolve inside one STAGE -- so two subtrees may each declare a ``build``,
        and picking one of them would bind a result to the wrong node.
        """

        matches = self.paths_of_call(call_id)
        return matches[0] if len(matches) == 1 else None

    def paths_of_call(self, call_id: str) -> tuple[str, ...]:
        """Return every STAGE path that declares a call, in tree order."""

        return tuple(
            path
            for path, node in walk(self.root)
            if any(call.call_id == call_id for call in node.declared_calls)
        )

    def resolve_dependency(self, declaring_path: str, reference: str) -> str | None:
        """Resolve one ``depends_on`` reference, or None when it names no node.

        The reference is walked **from the declaring node**: ``..`` moves to its
        parent, and any other segment must name a child of where the walk has
        arrived. ``../mass`` is therefore a sibling, and ``../../site/street-trees``
        reaches into another branch -- which is the whole point of the field.

        A bare ``mass`` resolves to the declaring node's own CHILD. That is not an
        error in the arithmetic but it names no dependency, because a node already
        waits for its children; the validator reports it and says what was meant.

        A leading ``/`` returns None: an absolute path is not this syntax, and
        accepting one here would give the field two bases.
        """

        if reference.startswith("/"):
            return None
        segments = [segment for segment in reference.split("/")
                    if segment not in ("", ".")]
        if not segments:
            return None

        current = declaring_path
        for segment in segments:
            if segment == "..":
                if current == ROOT_PATH:
                    return None
                current = parent_path(current)
                continue
            candidate = join_path(current, segment)
            if resolve(self.root, candidate) is None:
                return None
            current = candidate
        return current

    def dependency_paths(self, path: str) -> tuple[str, ...]:
        """Return the resolved dependencies of the node at ``path``.

        References that name no node are dropped: the validator is what reports
        them, and every consumer treats an unresolvable reference as no dependency
        rather than inventing one.
        """

        node = self.node_at(path)
        if node is None:
            return ()
        return tuple(
            resolved
            for resolved in (self.resolve_dependency(path, reference)
                             for reference in node.depends_on)
            if resolved is not None
        )

    def resolve_call_path(self, call_id: str, node_path: str | None = None) -> str:
        """Return the STAGE path a call belongs to.

        ``node_path`` names it outright. Otherwise the call id must be declared by
        exactly one STAGE: a call id is scoped to the STAGE that declares it, so
        two subtrees may each declare a ``build``, and binding a result to the
        wrong one would judge a node the Agent never touched. An ambiguous id is
        refused rather than resolved by picking the first match.

        This is the one place the rule lives, because it decides which node gets
        credit for a host change, and two implementations would eventually differ.

        @raises ValueError: when the call is undeclared, ambiguous, or the named
            node does not declare it.
        """

        if node_path:
            node = self.node_at(node_path)
            if node is None:
                raise ValueError(f"node is not present in the Workflow: {node_path}")
            if not any(call.call_id == call_id for call in node.declared_calls):
                raise ValueError(f"node {node_path} does not declare the call: {call_id}")
            return node_path

        declared = self.paths_of_call(call_id)
        if not declared:
            raise ValueError(f"call is not declared in the Workflow: {call_id}")
        if len(declared) > 1:
            raise ValueError(
                f"call {call_id} is declared by more than one node "
                f"({', '.join(declared)}); name the node with --stage")
        return declared[0]

    def path_of_item(self, item_id: str) -> str | None:
        """Return the path of the STAGE that declares an execution item, or None.

        Unambiguous names only: two subtrees may each declare ``built``, and
        picking one of them would judge a node the Agent did not name.
        """

        return self._unique_path(
            item_id,
            lambda node: [item.item_id for item in node.stage.execution_checklist]
            if node.stage is not None else [],
        )

    def path_of_check(self, check_id: str) -> str | None:
        """Return the path of the node that declares an acceptance check, or None."""

        return self._unique_path(
            check_id, lambda node: [check.check_id for check in node.declared_checks]
        )

    def _unique_path(self, identifier: str, declared: Any) -> str | None:
        matches = [
            path
            for path, node in walk(self.root)
            if identifier in declared(node)
        ]
        return matches[0] if len(matches) == 1 else None

    def fingerprints(self) -> dict[str, str]:
        """Return ``{path: fingerprint}`` for every node."""

        return tree_fingerprints(self.root)

    def to_dict(self) -> dict[str, Any]:
        """Return this revision as a document that satisfies the spec.

        Only fields with a value are emitted, and ``revision_id`` is not emitted at
        all: it is derived from ``workflow_id`` and ``revision``, and the spec
        forbids unknown top-level keys. A round trip through the model therefore
        produces something the spec still accepts -- which is the only way
        ``open`` can hold the spec's shape and this method at the same time.
        """

        out: dict[str, Any] = {
            "workflow_id": self.workflow_id,
            "root": self.root.to_dict(),
            "revision": self.revision,
            "status": self.status.value,
            "warnings": list(self.warnings),
        }
        for name in ("supersedes_workflow_id", "recovery_pointer"):
            value = getattr(self, name)
            if value is not None:
                out[name] = value
        return out


@dataclass(frozen=True, slots=True)
class GateResult:
    """Local precondition / entry gate result."""

    ready: bool
    blocked_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    next_action: str | None = None


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

ROOT_PATH = "/"


def normalise_path(path: str) -> str:
    """Return the canonical form of a node path.

    The engine's canonical form has a leading slash and a trailing slash on every
    segment: ``/a/b/``, and ``/`` for the root. Anything that names a node is
    compared in this form, so callers do not each invent their own.
    """

    segments = [segment for segment in path.strip("/").split("/") if segment]
    if not segments:
        return ROOT_PATH
    return "/" + "/".join(segments) + "/"


def parent_path(path: str) -> str:
    """Return the path of a node's parent. The root has no parent, so it returns
    itself -- callers that must not walk above the root check for that."""

    segments = [segment for segment in path.strip("/").split("/") if segment]
    if len(segments) <= 1:
        return ROOT_PATH
    return "/" + "/".join(segments[:-1]) + "/"


def join_path(path: str, node_id: str) -> str:
    """Return the child path of ``node_id`` under ``path``.

    Every segment is terminated by ``/``, so a leaf and a composite are written
    the same way and a prefix match cannot confuse ``/tower_a/`` with
    ``/tower_ab/``.
    """

    return f"{path}{node_id}/" if path.endswith("/") else f"{path}/{node_id}/"


def walk(node: WorkflowNode, path: str = ROOT_PATH) -> Iterator[tuple[str, WorkflowNode]]:
    """Yield ``(path, node)`` for every node, parents before children."""

    yield path, node
    for child in node.children:
        yield from walk(child, join_path(path, child.node_id))


def resolve(root: WorkflowNode, path: str) -> WorkflowNode | None:
    """Return the node at an absolute path, or None."""

    if path in {"", ROOT_PATH}:
        return root
    segments = [s for s in path.strip("/").split("/") if s]
    current = root
    for segment in segments:
        match = next((c for c in current.children if c.node_id == segment), None)
        if match is None:
            return None
        current = match
    return current


def resolve_relative(node: WorkflowNode, relative: str) -> WorkflowNode | None:
    """Return a **descendant** of ``node`` by a relative path, or None.

    Returns None for the node itself: a composite check reads what its children
    produced, never its own verdict.
    """

    segments = [s for s in relative.strip("/").split("/") if s]
    if not segments:
        return None
    current = node
    for segment in segments:
        match = next((c for c in current.children if c.node_id == segment), None)
        if match is None:
            return None
        current = match
    return None if current is node else current


def paths(root: WorkflowNode) -> list[str]:
    """Return every path, parents before children."""

    return [path for path, _node in walk(root)]


def leaves(root: WorkflowNode) -> list[tuple[str, WorkflowNode]]:
    """Return every STAGE node with its path."""

    return [(path, node) for path, node in walk(root) if node.is_leaf]


def depth(root: WorkflowNode) -> int:
    """Return the tree depth, counting the root as 1."""

    if not root.children:
        return 1
    return 1 + max(depth(child) for child in root.children)


# --------------------------------------------------------------------------- #
# Recursive fingerprint
# --------------------------------------------------------------------------- #


def node_fingerprint(node: WorkflowNode, _cache: dict[int, str] | None = None) -> str:
    """Return a digest of a node's definition **including its whole subtree**.

    Including the subtree is the point: a composite's completion depends on what
    its children produced, so a change anywhere below must invalidate the
    composite's verdict.

    ``node_id`` is excluded, so renaming or moving a subtree keeps its identity
    and an unchanged branch can be carried across revisions whole.

    @param node: the node to digest.
    @param _cache: internal memo keyed by object identity. The digest is
        recursive, so without a memo a comparison at every level re-walks the
        subtree below it, turning one tree-wide comparison into repeated work.
        Callers comparing a whole tree pass one dict for the duration, as
        :func:`plan_reuse` does.
    """

    if _cache is not None:
        cached = _cache.get(id(node))
        if cached is not None:
            return cached

    payload: dict[str, Any] = {
        "kind": node.kind.value,
        "purpose": node.purpose,
        "required": node.required,
        "depends_on": list(node.depends_on),
        "recovery": node.recovery,
    }
    if node.is_leaf and node.stage is not None:
        payload["stage"] = node.stage.to_dict()
    else:
        payload["acceptance_checklist"] = [
            check.to_dict() for check in node.acceptance_checklist
        ]
        payload["children"] = [
            {"node_id": child.node_id, "fingerprint": node_fingerprint(child, _cache)}
            for child in node.children
        ]
    text = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    if _cache is not None:
        _cache[id(node)] = digest
    return digest


def tree_fingerprints(root: WorkflowNode) -> dict[str, str]:
    """Return ``{path: fingerprint}`` for every node."""

    cache: dict[int, str] = {}
    return {path: node_fingerprint(node, cache) for path, node in walk(root)}


# --------------------------------------------------------------------------- #
# Reuse across revisions
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ReusePlan:
    """Which subtrees a revision carries over unchanged, and which must rerun."""

    reusable: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "reusable": list(self.reusable),
            "changed": list(self.changed),
            "added": list(self.added),
            "removed": list(self.removed),
        }


def plan_reuse(previous: WorkflowNode, current: WorkflowNode) -> ReusePlan:
    """Compare two revisions and decide which subtrees are untouched.

    The walk compares **subtrees, not nodes**: a subtree whose fingerprint is
    unchanged is reusable as a whole and the walk does not descend into it. That
    is what keeps reuse cheap on a deep tree -- an untouched branch costs one
    comparison, not one per node.

    One fingerprint memo is shared across both trees, so each node is digested
    once even though the comparison visits it from several ancestors.
    """

    reusable: list[str] = []
    changed: list[str] = []
    added: list[str] = []
    removed: list[str] = []
    cache: dict[int, str] = {}

    def compare(old: WorkflowNode | None, new: WorkflowNode | None, path: str) -> None:
        if old is None and new is not None:
            added.append(path)
            for child in new.children:
                compare(None, child, join_path(path, child.node_id))
            return
        if new is None and old is not None:
            removed.append(path)
            for child in old.children:
                compare(child, None, join_path(path, child.node_id))
            return
        if old is None or new is None:
            return

        if node_fingerprint(old, cache) == node_fingerprint(new, cache):
            reusable.append(path)
            return

        changed.append(path)
        if old.is_leaf or new.is_leaf:
            return

        old_children = {c.node_id: c for c in old.children}
        new_children = {c.node_id: c for c in new.children}
        for node_id in sorted(set(old_children) | set(new_children)):
            compare(old_children.get(node_id), new_children.get(node_id),
                    join_path(path, node_id))

    compare(previous, current, ROOT_PATH)
    return ReusePlan(tuple(reusable), tuple(changed), tuple(added), tuple(removed))
