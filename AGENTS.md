# AI Native Game Engine Agent Instructions

This file is the repository-level entry point.

## Required loading order

Every path below is relative to the repository root — the directory containing
this file. Nothing in this repository names a machine-specific location.

```text
AGENTS.md
    → SKILL.md
    → Skill integrity gate
    → templates/ for the Workflow schema and the result contract when authoring
      a Workflow or a guidance document
    → guidance/ for the matching lifecycle
    → docs/DEPENDENCIES.md (when a host or MCP call is involved)
    → docs/DEPENDENCIES.md section for the specific host/MCP (Blender/UE5/ComfyUI/HF)
    → exact MCP call feasibility
    → one-call-at-a-time execution
    → python -m ainative.session open (hand the Agent-authored Workflow to Python)
    → python -m ainative.session record / item / check (submit what came back)
    → python -m ainative.session stage (deterministic node verdict, named by path)
    → python -m ainative.session supersede (replace the revision when the plan was wrong)
    → python -m ainative.session finish (aggregated TaskResult)
```

There is no host-interface reference to read. What a host's MCP server can do is
decided by the running server, so this repository cannot state it: confirm it
through the Agent's own MCP client before selecting a call.

The runtime source root is the directory containing this file. Do not infer a
second project root from the current shell directory.

## Repository purpose

This repository gives an Agent the prompt assets and the acceptance machinery to
drive UE5, Blender, and external tools such as ComfyUI through their own MCP
servers.

```text
Agent Intent
    → Task Contract
    → Agent composes each node from Stage kind (for a STAGE leaf), processing
      object, operation type, current facts, and the user's requirements
    → Agent authors the Workflow tree: STAGE leaves carry both frozen checklists
      and their calls, WORKFLOW nodes group them and read a descendant's verdict
    → Agent calls one MCP tool at a time
    → ExecutionResult + Evidence
    → Agent submits the Workflow and the results to Python
    → deterministic checklist evaluation, bottom-up over the tree
    → NodeResult per node / StageResult for the node closed / TaskResult
    → continue / retry / wait / compensate / re-plan
```

The Agent decides what runs next. Python does not schedule, does not generate a
Workflow, and does not choose the following call. What Python does own is the
deterministic verdict: the Agent hands over its own Workflow tree and its own
reported results, and Python evaluates each node against its frozen checklists,
bottom-up, and returns the StageResult for the node it was asked to close — it
never invents a checklist item, orders a node, or picks a call.

**A node's identity is its path** (`/step-1/validate-asset/`), not its
`node_id`. A `node_id` is unique only among **siblings**, which is what lets two
subtrees each declare a `mass`; the path is what says which one is meant. Every
argument that names a node — `--stage` on `stage`, `item`, and `check` — takes a
path.

## Host software is reached through MCP

Blender and UE5 are reached through their MCP servers by the Agent's own MCP
client. This repository holds no Blender or UE5 executable path, launches no
editor process, and bundles no host add-on implementation.

```text
Blender  → Blender MCP Server
UE5      → UE5 MCP Server
ComfyUI  → ComfyUI MCP Server
```

Consequences:

- Do not add a host executable path, a `subprocess` launch of an editor, or a
  host-resident plugin to this repository. That code belongs in the host's own
  project.
- An installed add-on is not a running server. Confirm the running
  server through the Agent's own MCP client — a tool listing or a trivial read —
  before selecting a call.
- What remains here is what has no host dependency: plan validation, the
  deterministic acceptance engine, and the prompt assets an Agent reads.

## Planning rules

- `guidance/` documents supply macro lifecycle guidance and invariants, not one
  universal sequence. They are prompt assets the Agent reads, not a runtime.
- Compose each node from Stage kind, processing object, operation type, current
  facts, and user requirements. A STAGE leaf is where the work happens; a
  WORKFLOW node is containment or a phase grouping and is not a separate type.
- Every required STAGE freezes an execution checklist and an acceptance
  checklist before execution, inside its `stage` body.
- `node_id` is unique among **siblings** only. Give siblings distinct ids and let
  the path disambiguate the rest.
- `depends_on` names nodes that must complete first, each written **from the
  declaring node**: `..` is its parent, so `../mass` is a sibling and
  `../../site/ground` reaches into another branch. Relative, not absolute, because
  a reusable subtree does not know where it will be placed and so could not name
  its own siblings otherwise. A bare `mass` resolves to the declaring node's own
  **child** — which it already waits for — and is refused with the spelling that
  was meant. A cycle is refused, including one closed through the implicit
  parent-child edge (a node waiting for its own ancestor).
- ORDER comes only from `depends_on`. The order nodes are written in carries no
  meaning, and two nodes with no dependency between them are unordered: the Agent,
  which executes every call itself, may run them in any order or at the same time.
  Nothing in this repository schedules, and nothing runs anything.
- A composite (WORKFLOW) check reads exactly **one** descendant through
  `source_node` — a relative path under the declaring node, never the node
  itself — and its `expected` is that descendant's **verdict**: `pass`, `warn`,
  `fail`, `unknown`, or `needs_human`. It is not a list of descendants and not a
  task status. Compare it with `equals`: a call-oriented or numeric operator
  applied to a verdict word can never pass. To assert several descendants,
  declare one check each, or nest a composite whose own verdict rolls them up.
- A change STAGE confirms the calls required for execution and acceptance before
  its first side effect.
- Before selecting a host or MCP call, load docs/DEPENDENCIES.md and confirm the
  required Python, Blender, UE5, add-on/plugin, and Agent prerequisites.
- Before selecting a Blender or UE5 MCP call, confirm the host version, the
  running MCP server, and the Agent client prerequisites.
- During execution, do not silently substitute another MCP server, target, or
  Backend.
- Call success proves only that the call completed. A node's completion comes
  from structured checklist results and evidence; a composite's verdict is earned
  on its children's.
- A **node** has a verdict: `pass`, `warn`, `fail`, `unknown`, or `needs_human`.
  A **task** has a status: `succeeded`, `degraded`, `blocked`, `failed`, or
  `needs_approval`. Keep the two vocabularies apart.
- Required `fail`, `unknown`, and `needs_human` results cannot be treated as
  completion.
- An unresolved required node (`unknown` / `needs_human`) makes every ancestor
  unknown, not failed: incomplete evidence is not the same as a failure.
- Local acceptance belongs to the current STAGE. A separate validation node is
  allowed for invariants that cross nodes.

## Acceptance boundary (do not blur)

Two acceptance systems exist on purpose, and they answer different questions.
This repository owns the first one and must not absorb the second.

| | This repo: `StageAcceptanceEvaluator` | `AI-Native-Evals`: TestPlan |
| --- | --- | --- |
| Who authors the criteria | The Agent, inside its Workflow | The Task author (a human) |
| When it runs | At a node boundary, during the run | After the run, over the workspace |
| Question it answers | Did this node meet the Workflow's own frozen criteria? | Was the task actually completed? |
| Status vocabulary | `pass` / `warn` / `fail` / `unknown` / `needs_human` | `passed` / `failed` / `review` / `blocked` / `error` / `skipped` / `observed` |
| May invoke Tools | No, by design | Yes (Judge Agents, host probes) |
| Authority | Gates progress inside one run | The only verdict valid outside the run |

Rules:

- A Stage `pass` proves the Agent's **submitted evidence** satisfied its own
  checklist. It does not prove the work was done. Python never sees the host, so a
  submission whose reported outputs satisfy every check passes whether or not the
  call behind it behaved as reported -- the engine can check shape, references,
  dependency order, repeat runs, and whether required evidence was supplied, and it
  cannot check whether any of it is true. Nor does a pass prove the task is done,
  because the Agent wrote the checklist. Never present it
  as task-level success.
- This repository never imports, depends on, or defers to `AI-Native-Evals`. The
  evaluator stays usable with no eval framework installed.
- `AI-Native-Evals` may consume `StageAcceptance` as a *process signal*. It must
  never adopt a Stage `pass` as its own pass.
- The two share the idea of checking world state, not the authority to judge. The
  primitive operators (`exists`, `equals`, `within_tolerance`, ...) are
  intentionally implemented on both sides for their own layers. When adding a new
  primitive here, check whether the eval side needs the equivalent, and keep the
  vocabularies explicitly mapped rather than assumed equal.

## Stage kinds

A stage kind lives at `stageBody.stage_kind` of a STAGE leaf. It decides what must
be frozen before the first side effect, so it is part of the leaf's definition,
not a label.

```text
change
    freeze execution and acceptance before side effects

investigation
    freeze scope and stop conditions; evidence checks may expand as facts change

planning
    prove goals, constraints, call feasibility, dependencies, risks, and future
    acceptance methods
```

## Directory ownership

This repository **is** the Skill. The guidance below is what an Agent reads;
`src/` is the only executable part.

```text
<repository root>/
├── AGENTS.md             this file
├── SKILL.md              Skill entry point
├── guidance/             reusable macro-lifecycle guidance
├── templates/            the Workflow schema, the result contract, and the
│                         guidance template
├── src/ainative/
│   ├── session_api/      Skill loading, the Workflow opener, the session
│   ├── cli/              the acceptance-loop CLI and its state file
│   ├── model/            pure data structures
│   ├── reading/          JSON reading and Workflow validation
│   └── acceptance/       node verdict, aggregation, confirmation gate
├── tests/                unit/integration tests + a sample Task Contract
├── docs/                 cross-cutting architecture and maintenance docs
└── artifacts/            evidence and scratch output
```

### Code ownership

- `src/ainative/session_api/` owns the Agent-facing session API.
- `src/ainative/cli/` owns the acceptance-loop CLI and its durable state.
- `src/ainative/model/`, `reading/`, and `acceptance/` own the data shapes,
  Workflow validation, and the deterministic verdict.
- `guidance/` owns what the Agent reads about a lifecycle. It is a prompt asset,
  not a runtime.
- `templates/` owns the shapes: the Workflow spec the engine validates, the result
  contract the Agent submits against, and how to write a guidance document.
- `integrity_gate.py` owns the required-file list every prompt asset must appear
  in.

## Call execution

```text
ToolCall(target=owner/name) → Agent MCP Client → named MCP Server/tool
```

There is no execution binding, no Tool registry, and no discovery index. The
call contract carries the target; the Agent's own MCP client resolves and runs
it. Host capabilities — Blender, UE5, ComfyUI — are the Agent's MCP servers'
business, and this repository ships no executable Toolset of its own.

Host dependencies are declared in `docs/DEPENDENCIES.md`. There is no per-package
recipe directory: the Agent reads `guidance/` for the matching lifecycle and
confirms the host prerequisites itself.

## Acceptance loop

One process-level CLI exists: `python -m ainative.session` takes the
Agent-authored Workflow tree and returns a node verdict.

`python -m ainative.session` is how a Workflow and its reported results reach Python.
The Agent authors the Workflow as JSON, executes every call itself, and reports each
result back; Python validates the Workflow structure, stores the evidence in the
`--state` file, and evaluates each node against its frozen checklists, bottom-up, so
a composite's verdict is earned on its children's. Python still chooses nothing.

```text
open       hand over --task and --workflow
record     submit one executed call result (--result)
item       submit one execution checklist item result (--result)
check      submit one manual acceptance check result (--result)
stage      evaluate and close one node, named by path (--stage)
finish     aggregate the final TaskResult
status     read the current state without changing it
supersede  replace the Workflow revision, archiving the old one and its evidence
```

`--stage` takes a node **path** (`/step-1/validate-asset/`), and the path may
address a STAGE leaf or a WORKFLOW composite: closing a composite judges its whole
subtree and reports the roll-up. `item` and `check` also accept `--stage`, to name
the node when a bare item or check id is declared by more than one node — an
ambiguous id is refused rather than resolved by guessing.

Every command prints the same envelope — `command`, `ok`, `verdict`, `exit_code`,
`detail`, `errors` — and exits 0 for a non-blocking result, 1 for a blocking or
failing result, and 2 when the command itself could not run.

`verdict` uses the **task** vocabulary for every command: `succeeded`, `degraded`,
`blocked`, `failed`, `needs_approval`. Task outcomes already speak those words and
a node verdict is mapped onto them; a checklist `pass` reports `succeeded` and a
`warn` reports `degraded`, so a caller reads one field without knowing which
command ran. A node's own verdict stays in the node vocabulary — `pass`, `warn`,
`fail`, `unknown`, `needs_human` — and appears as the result's `status` only after
that mapping.

A call returning `succeeded` does not complete a node. A STAGE completes only
when its frozen acceptance checks pass — an empty `preserved_relations` against a
`truthy` check yields check `fail`, then stage `failed`, then verdict `failed`
and exit 1. A WORKFLOW node completes when every required child completed **and**
its own checks pass; an unresolved required descendant makes every ancestor
`unknown`, which is not the same as `failed`.

A Workflow revision is immutable. A node carries over to a replacement only when
its **path and content fingerprint** are both unchanged — the fingerprint covers
the node's goal, checklists and calls, and deliberately excludes `node_id`, so a
changed subtree is re-run instead of inheriting a verdict that no longer applies.
A node that already ran a call may have changed the host, and re-reporting that
call is refused without `--confirm-side-effects`.

## Engineering rules

- Do not reintroduce Capability, CapabilityBinding, or a per-run capability
  snapshot.
- Do not reintroduce a Tool registry, a discovery index, or a search API.
- Do not reintroduce an execution binding, a provider list, or a project Toolset
  runtime.
- Do not reintroduce Python Workflow generation or a whole-Workflow scheduler.
- Do not reintroduce a Blender or UE5 executable path, an editor subprocess
  launch, or a host add-on implementation.
- Do not reintroduce a flat `Workflow -> Step -> Stage` shape, a `StageRequest`,
  or a globally unique `stage_id`: a node's identity is its path.
- Do not infer Stage success from call success alone.
- Keep simple checks in the deterministic Stage evaluator.
- Freeze acceptance items before change-side effects. Do not delete an item
  merely because execution failed.
- Preserve ExecutionResults, checklist results, StageResults, and Evidence.
- Do not silently change MCP server, Backend, or loss policy.
- Do not initialize or alter Git history unless explicitly requested.

## Verification commands

Run these from the repository root:

```powershell
python -m pytest -q
python integrity_gate.py --json
python -m compileall -q src tests
ruff check src/ainative tests integrity_gate.py
```

### Acceptance-loop example

```powershell
python -m ainative.session --state s.json --task task.json --workflow workflow.json open
python -m ainative.session --state s.json --result executed-call.json record
python -m ainative.session --state s.json --stage /step-1/validate-asset/ stage
python -m ainative.session --state s.json finish
python -m ainative.session --state s.json status
```

The Workflow, the task, and every submitted result live in the `--state` file, so
later commands need only `--state` and their own argument.
