---
name: ai-native-game-engine
description: Use when an agent must drive Blender, UE5, or ComfyUI through MCP and prove what happened — composing a Workflow tree of stages, running one call at a time, and submitting structured evidence for a deterministic verdict per node. Use when acceptance must be checked rather than asserted, when a host operation must stay auditable, when a multi-stage job needs a gate so a failed step cannot be reported as done, or when deciding whether a host call is feasible before committing to a plan.
---

# AI Native Game Engine Skill

This Skill teaches an Agent to build dynamic but auditable Stages across UE5,
Blender, and external tools such as ComfyUI.

## Ownership rule

The Agent owns the Workflow and calls one MCP tool at a time. A Workflow is a
**tree**, and every node in it is one of two things:

```text
STAGE      a leaf: the calls it declares plus two frozen lists

    execution checklist
        prevents omitted work

    acceptance checklist
        prevents call success from being mistaken for goal completion

WORKFLOW   a composite: children, plus checks that read a descendant's verdict
```

A phase is not a separate type — it is a WORKFLOW node used for grouping, and a
node's identity is its **path** (`/step-1/validate-asset/`), because `node_id` is
unique only among siblings.

Python validates the Workflow's structure, records the structured results the Agent
submits, and deterministically aggregates checklist outcomes bottom-up, so a
composite's verdict is earned on its children's. It does not decide what runs next.

## Loading order

1. Read this `SKILL.md`.
2. Make the engine runnable: `python -m pip install -e .` from this skill's base
   directory. The engine ships inside this skill, so there is nothing to fetch --
   but it is a Python package, and the commands below need it importable. Confirm
   with `python -m ainative.session --help`.
3. Run the integrity gate: `python integrity_gate.py --json`.
4. Read `templates/` — `workflow.schema.json` is the Workflow's shape, and
   `result-contract.md` is the shape of what you submit against it.
5. Read `guidance/` and pick the document matching the task's lifecycle.
6. Load `docs/DEPENDENCIES.md` for the host or MCP server involved and confirm
   its prerequisites before selecting any call. There is no interface reference to
   read: what a host's MCP server can do is decided by the running server, so
   confirm it through your own MCP client.

Every path above is relative to this skill's base directory, which the loader
reports as `Base directory for this skill: <path>`. Resolve them there; do not
infer the location from the working directory.

This package ships no per-object or per-operation knowledge base. The working
order below is the composition rule, and the Agent supplies the domain
competence for the processing object, the operation type, and the current facts.

Host capabilities (Blender, UE5, ComfyUI) are reached through their own MCP
servers by the Agent's MCP client. This package documents what to call; it does
not execute host software.

## Workflow rules

These hold for every Workflow you author.

1. Every required STAGE freezes an execution checklist and an acceptance
   checklist before execution. Both live inside its `stage` body; a STAGE does
   not declare checks at node level.
2. Every call supports at least one execution or acceptance item.
3. Checklist knowledge never hard-codes a call source. The final Workflow stores
   the exact `target` you selected.
4. A change STAGE checks its required calls before its first side effect.
5. A call returning `succeeded` does not automatically satisfy a semantic
   acceptance check.
6. Simple checks use deterministic operators. Complex checks use a normal call
   and record its structured output as evidence.
7. A required `unknown` or `needs_human` result cannot be converted to `pass`
   without new evidence or an explicit human decision.
8. A running Workflow revision is immutable. Changes create a new revision.
9. A `node_id` is unique among **siblings** only. Name siblings distinctly and
   address a node by its path. `depends_on` names nodes that must complete first,
   written **from the declaring node**: `..` is its parent, so `../mass` is a
   sibling and `../../site/ground` reaches into another branch. A bare `mass`
   would be the declaring node's own child — something it already waits for — and
   is refused with the spelling that was meant. A cycle is refused, including one
   closed through the implicit parent-child edge.
10. A WORKFLOW node's check reads exactly **one** descendant through
    `source_node` — a path relative to the declaring node, never the node itself
    — and its `expected` is that descendant's **verdict**: `pass`, `warn`,
    `fail`, `unknown`, or `needs_human`. It is not a list of descendants and not
    a task status such as `succeeded`. Compare it with `equals`: the check is
    applied to a verdict word, so a call-oriented or numeric operator can never
    pass. To assert several descendants, declare one check each, or nest a
    composite whose verdict rolls them up.

To replace a revision, use `supersede` rather than reopening:

```powershell
python -m ainative.session --state s.json --workflow new.json --reason "why" supersede
```

A node carries over only when its **path and content fingerprint** are both
unchanged — the goal, the checklists, and the calls. An unchanged `node_id` is not
enough: the fingerprint is what the engine compares, and it excludes `node_id`
precisely so that a renamed node is a different node at a different path. If you
changed what a node must prove, its earlier verdict says nothing about the new one,
and it must run again.

Python cannot see the host and cannot undo anything, but it does know which nodes
have already run a call against a live host. `supersede` reports those as
`side_effects_at_risk`, and re-reporting such a call is refused until you pass
`--confirm-side-effects`. Take that seriously: re-running a call the host already
saw can apply the same change twice. If a node must be undone, that is an
explicit compensating call you author, not something this repository can do.

Author the Workflow against `templates/workflow.schema.json`. That file **is** the
definition of the data structure: it states every node kind, every field, and every
operator. There is no separate fill-in template, because a template and a schema
describing one shape drift apart, and the schema is the one a document can be
checked against.

`open` enforces that schema before it accepts a document, and then enforces the
semantics the schema cannot express (sibling uniqueness, dependency cycles, which
side a check may read). A rejection names the layer: a spec failure reports a JSON
pointer, a semantic failure reports a rule number such as `C4` or `V3`. Fix the
document; do not ask for the check to be relaxed.

## Working order

1. State the task as a Task Contract: objective, direction, what must be
   preserved, and what loss is acceptable.
2. Break it into a tree of nodes, composing each from Stage kind, processing
   object, operation type, current facts, and the user's requirements. STAGE
   leaves hold the work; WORKFLOW nodes hold containment or a phase grouping and
   the checks that read what their descendants proved.
3. For every required STAGE, freeze the execution and acceptance checklists
   before any side effect, inside its `stage` body. Give every WORKFLOW node the
   checks that read a descendant's verdict where the roll-up matters.
4. Select the exact calls that satisfy those checklists.
5. Write the Workflow as JSON and hand it to Python with `open`, then execute one
   call at a time and record each structured result as evidence against that same
   state file. Later commands need only `--state` plus their own argument.
   `docs/cli.md` is the authority on the commands themselves — the envelope, the
   exit codes, and what each one may see — and `templates/result-contract.md` is
   the authority on what you submit. Read them there rather than here:

   ```powershell
   python -m ainative.session --state s.json --task task.json --workflow workflow.json open
   python -m ainative.session --state s.json --result executed-call.json record
   python -m ainative.session --state s.json --stage /step-1/validate-asset/ stage
   python -m ainative.session --state s.json finish
   ```

   An `item` result covers an execution checklist item and a `check` result covers a
   manual acceptance check. `open` validates the Workflow structure and writes
   `--state`, which carries the Workflow and the task for the rest of the loop.

6. Complete a node only by asking for the deterministic verdict against its frozen
   checklists, never from a call's own status. `stage` names the node by **path**,
   and the path may address a STAGE leaf or a WORKFLOW composite — closing a
   composite judges its whole subtree and reports the roll-up. `item` and `check`
   also accept `--stage`, to name the node when a bare item or check id is declared
   by more than one node; an ambiguous id is refused rather than resolved by
   guessing, because judging the wrong subtree silently is worse than asking.

   A call returning `succeeded` does not complete a node. A WORKFLOW node completes
   when every required child completed and its own checks pass; an unresolved
   required descendant makes every ancestor `unknown`, which is not the same as
   `failed`.

7. Continue, retry, wait for evidence or a human decision, compensate, or
   author a replacement Workflow according to the node result.

## Core model

```text
Task Contract
    → Stage kind + processing object + operation type + current facts
    → Agent-authored Workflow tree
       └── WorkflowTree
           └── root: WorkflowNode (kind = workflow)
               ├── WorkflowNode (kind = workflow)      a phase or containment
               │   ├── acceptance_checklist[]          reads source_node
               │   └── children[]
               │       └── WorkflowNode (kind = stage) a leaf
               │           └── stage: StageBody
               │               ├── stage_kind          change | investigation | planning
               │               ├── execution_checklist[]
               │               ├── acceptance_checklist[]
               │               └── calls[]
               └── ...
    → Agent calls one MCP tool
    → ExecutionResult
    → ExecutionItemResult + CheckResult
    → deterministic NodeResult per node, bottom-up
    → StageResult for the node closed
```

The root of a Workflow document is a single node; a Workflow **is** the tree, and
its path is `/`.

## Stage kinds

A stage kind is a property of a STAGE leaf, stored at `stageBody.stage_kind`. It
decides what must be frozen before the first side effect, so it belongs to the
leaf's definition rather than labelling it.

```text
change
investigation
planning
```

`change` freezes execution and acceptance before side effects.
`investigation` may expand evidence-gathering items, but its scope, stop
condition, evidence rules, and unknowns remain explicit.
`planning` proves feasibility, risks, dependencies, and acceptance methods.
A WORKFLOW node has no stage kind: it declares no calls and no stage body.

## Checklist outcomes

Two vocabularies exist and they are never interchangeable. A **node** verdict uses:

```text
pass
warn
fail
unknown
needs_human
```

A **task** status — what the envelope's `verdict` field carries, whichever command
ran — uses `succeeded`, `degraded`, `blocked`, `failed`, `needs_approval`.

A STAGE aggregates deterministically, mapping the first onto the second:

```text
required fail          → failed
required unknown       → blocked
required needs_human   → needs_approval
required warn only     → degraded / completed with warnings
all required pass      → succeeded
```

A WORKFLOW node aggregates from its children, then from its own checks:

```text
a required child failed            → fail
a required child unknown/needs_human → unknown   (and the same for an
                                     unresolved check of its own)
a check failed                     → fail
a check warned                     → warn
otherwise                          → pass
```

An unresolved required node makes every ancestor unknown, not failed: incomplete
evidence is not the same as a broken one. An optional node the Agent omitted is
`skipped`, which does not fail its parent and is never reported as `pass`.

A `pass` or `warn` that requires evidence cannot be accepted without an
evidence reference.

## Execution rules

- A call names a `target` of owner/name: the MCP server, and the tool on it.
  For an MCP call the owner is the MCP server and the name is the tool on it.
- Confirm a host capability exists and is running before depending on it; a
  documented interface is not a live server.
- At execution time, use the exact call you selected. Do not silently substitute
  another target, server, or backend.
- Simple operators use the deterministic evaluator.
- Every call supports at least one checklist item.

## Local and global acceptance

Local acceptance is part of each STAGE. A separate validation node is allowed
only when it owns invariants that cross nodes. A WORKFLOW node's own check reads
one descendant's verdict through `source_node`, so a composite never asserts
anything about itself and never re-reads a call.

## Recovery

```text
MCP call failure
    → retry the selected call or run an explicit compensating call

required unknown
    → gather evidence; otherwise block and report what is missing

needs_human
    → wait for the required decision

wrong Workflow or checklist
    → author a replacement Workflow
```

Never delete an acceptance item because the operation failed. Workflow invalidation
does not undo external UE5, Blender, or filesystem state.

## Output contract

```text
ExecutionResult
ExecutionItemResult
CheckResult
ChecklistSummary
NodeResult
StageResult
TaskResult
Evidence
```
