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
      a Workflow
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
├── templates/            the Workflow schema and the result contract
├── install_skill.py      install this project into a skill root, or check it
├── pack_skill.py         pack the skill into an archive, or verify one
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
- `templates/` owns the shapes: the Workflow spec the engine validates and the
  result contract the Agent submits against.
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

Host prerequisites are the host's own to document. Nothing here states a version
baseline or an install path for Blender, UE5, or ComfyUI; confirm the running
server through the Agent's own MCP client before selecting a call.

## Acceptance loop

One process-level CLI exists: `python -m ainative.session` takes the
Agent-authored Workflow tree and returns a node verdict. It has eight commands —
`open`, `record`, `item`, `check`, `stage`, `finish`, `status`, `supersede` — and
`docs/cli.md` is the authority on all of them, including the envelope, the exit
codes, and what each one may see. Read it there rather than here.

What belongs here is what you must never get wrong, whichever command you run:

- A call returning `succeeded` does not complete a node. A STAGE completes only
  when its frozen acceptance checks pass. An unresolved required node makes every
  ancestor `unknown`, which is **not** the same as `failed`: incomplete evidence is
  not a failure.
- Closing a node is done by asking for the verdict, never by asserting one.
  `stage` names the node by **path**, so `node_id` never has to be globally unique.
  An ambiguous bare id is refused rather than guessed.
- The task vocabulary and the node vocabulary are different words for different
  things. Never report one as the other.
- A Workflow revision is immutable. A node carries over to a replacement only when
  its **path and content fingerprint** are both unchanged — the fingerprint covers
  the node's goal, checklists and calls, and deliberately excludes `node_id`, so a
  changed subtree is re-run instead of inheriting a verdict that no longer applies.
- A node that already ran a call may have changed the host. Re-reporting that call
  is refused without `--confirm-side-effects`, and passing it should be rare: the
  flag exists for a re-run after a replacement invalidated the node, not for
  retrying one that already succeeded.

The Workflow, the task, and every submitted result live in the `--state` file, so
later commands need only `--state` and their own argument.

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
