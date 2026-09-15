# AI Native Game Engine Agent Instructions

This file is the repository-level entry point.

## Required loading order

```text
D:\work\AI-Native\game-engine\AGENTS.md
    → D:\work\AI-Native\game-engine\SKILL.md
    → Skill integrity gate
    → templates/ when authoring a Workflow or a guidance document
    → guidance\ for the matching lifecycle
    → references\ for host/MCP interfaces
    → docs\DEPENDENCIES.md (when a host or MCP call is involved)
    → docs\DEPENDENCIES.md section for the specific host/MCP (Blender/UE5/ComfyUI/HF)
    → exact MCP call feasibility
    → one-call-at-a-time execution
    → python -m ainative.session open (hand the Agent-authored Workflow to Python)
    → python -m ainative.session record / item / check (submit what came back)
    → python -m ainative.session stage (deterministic Stage verdict)
    → python -m ainative.session finish (aggregated TaskResult)
```

The runtime source root is the directory containing this file. Do not infer a
second project root from the current shell directory.

## Repository purpose

This repository gives an Agent the prompt assets and the acceptance machinery to
drive UE5, Blender, and external tools such as ComfyUI through their own MCP
servers.

```text
Agent Intent
    → Task Contract
    → Agent composes each Stage from Stage kind, processing object, operation
      type, current facts, and the user's requirements
    → Agent authors the Workflow (Stages + both frozen checklists + calls)
    → Agent calls one MCP tool at a time
    → ExecutionResult + Evidence
    → Agent submits the Workflow and the results to Python
    → deterministic checklist evaluation
    → StageResult
    → continue / retry / wait / compensate / re-plan
```

The Agent decides what runs next. Python does not schedule, does not generate a
Workflow, and does not choose the following call. What Python does own is the
deterministic verdict: the Agent hands over its own Workflow and its own reported
results, and Python evaluates the Stages against the frozen checklists and
returns the StageResult — it never invents a checklist item, orders a Stage, or
picks a call.

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
- What remains here is what has no host dependency: the transfer file protocol,
  validation, and the acceptance engine.

## Planning rules

- `guidance/` documents supply macro lifecycle guidance and invariants, not one
  universal sequence. They are prompt assets the Agent reads, not a runtime.
- Compose each Stage from Stage kind, processing object, operation type, current
  facts, and user requirements.
- Every required Stage freezes an execution checklist and an acceptance
  checklist before execution.
- A change Stage confirms the calls required for execution and acceptance before
  its first side effect.
- Before selecting a host or MCP call, load docs\DEPENDENCIES.md and confirm the
  required Python, Blender, UE5, add-on/plugin, and Agent prerequisites.
- Before selecting a Blender or UE5 MCP call, confirm the host version, the
  running MCP server, and the Agent client prerequisites.
- During execution, do not silently substitute another MCP server, target, or
  Backend.
- Call success proves only that the call completed. Stage completion comes from
  structured checklist results and evidence.
- Required checklist results use `pass`, `warn`, `fail`, `unknown`, or
  `needs_human`.
- Required `fail`, `unknown`, and `needs_human` results cannot be treated as
  completion.
- Local acceptance belongs to the current Stage. A separate validation Stage is
  allowed for cross-Stage invariants.

## Acceptance boundary (do not blur)

Two acceptance systems exist on purpose, and they answer different questions.
This repository owns the first one and must not absorb the second.

| | This repo: `StageAcceptanceEvaluator` | `AI-Native-Evals`: TestPlan |
| --- | --- | --- |
| Who authors the criteria | The Agent, inside its Workflow | The Task author (a human) |
| When it runs | At a Stage boundary, during the run | After the run, over the workspace |
| Question it answers | Did this Stage meet the Workflow's own frozen criteria? | Was the task actually completed? |
| Status vocabulary | `pass` / `warn` / `fail` / `unknown` / `needs_human` | `passed` / `failed` / `review` / `blocked` / `error` / `skipped` / `observed` |
| May invoke Tools | No, by design | Yes (Judge Agents, host probes) |
| Authority | Gates progress inside one run | The only verdict valid outside the run |

Rules:

- A Stage `pass` proves the Agent did what its own checklist said. It does not
  prove the task is done, because the Agent wrote the checklist. Never present it
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
D:\work\AI-Native\game-engine\
├── AGENTS.md             this file
├── SKILL.md              Skill entry point
├── guidance\             reusable macro-lifecycle guidance
├── references\           host and MCP interface notes
├── templates\            the Workflow template, its field notes, and the guidance template
├── src\ainative\
│   ├── session_api\      Skill loading and the acceptance session
│   ├── cli\              the acceptance-loop CLI and its state file
│   ├── model\            pure data structures
│   ├── reading\          JSON reading and Workflow validation
│   └── acceptance\       deterministic verdict + confirmation gate
├── tests\                unit/integration tests + a sample Task Contract
├── docs\                 cross-cutting architecture and maintenance docs
└── artifacts\            evidence and scratch output
```

### Code ownership

- `D:\work\AI-Native\game-engine\src\ainative\session_api\` owns the Agent-facing
  session API.
- `D:\work\AI-Native\game-engine\src\ainative\cli\` owns the acceptance-loop CLI
  and its durable state.
- `D:\work\AI-Native\game-engine\src\ainative\model\`, `reading\`, and
  `acceptance\` own the data shapes, Workflow validation, and the deterministic
  verdict.
- `D:\work\AI-Native\game-engine\guidance\` and `references\` own what the
  Agent reads. They are prompt assets, not a runtime.
- `D:\work\AI-Native\game-engine\integrity_gate.py` owns the required-file
  list every prompt asset must appear in.

## Call execution

```text
ToolCall(target=owner/name) → Agent MCP Client → named MCP Server/tool
```

There is no execution binding, no Tool registry, and no discovery index. The
call contract carries the target; the Agent's own MCP client resolves and runs
it. Host capabilities — Blender, UE5, ComfyUI — are the Agent's MCP servers'
business, and this repository ships no executable Toolset of its own.

Host dependencies are declared in `docs\DEPENDENCIES.md`. There is no per-package
recipe directory: the Agent reads `guidance\` for the matching lifecycle and
confirms the host prerequisites itself.

## Acceptance loop

One process-level CLI exists: `python -m ainative.session` takes the
Agent-authored Workflow and returns a Stage verdict.

`python -m ainative.session` is how a Workflow and its reported results reach Python.
The Agent authors the Workflow as JSON, executes every call itself, and reports each
result back; Python validates the Workflow structure, stores the evidence in the
`--state` file, and evaluates each Stage against its frozen checklists. Python
still chooses nothing.

```text
open     hand over --task and --workflow
record   submit one executed call result (--result)
item     submit one execution checklist item result (--result)
check    submit one manual acceptance check result (--result)
stage    evaluate and close one Stage (--stage)
finish   aggregate the final TaskResult
status   read the current state without changing it
```

Every command prints one JSON object: exit 0 for a non-blocking result, 1 for a
blocking or failing result, and 2 when the command itself could not run.

A call returning `succeeded` does not complete a Stage. A Stage completes only
when its frozen acceptance checks pass — an empty `preserved_relations` against a
`truthy` check yields check `fail`, then stage `failed`, then exit 1.

## Engineering rules

- Do not reintroduce Capability, CapabilityBinding, or a per-run capability
  snapshot.
- Do not reintroduce a Tool registry, a discovery index, or a search API.
- Do not reintroduce an execution binding, a provider list, or a project Toolset
  runtime.
- Do not reintroduce Python Workflow generation or a whole-Workflow scheduler.
- Do not reintroduce a Blender or UE5 executable path, an editor subprocess
  launch, or a host add-on implementation.
- Do not infer Stage success from call success alone.
- Keep simple checks in the deterministic Stage evaluator.
- Freeze acceptance items before change-side effects. Do not delete an item
  merely because execution failed.
- Preserve ExecutionResults, checklist results, StageResults, and Evidence.
- Do not silently change MCP server, Backend, or loss policy.
- Do not initialize or alter Git history unless explicitly requested.

## Verification commands

```powershell
Set-Location D:\work\AI-Native\game-engine
python -m pytest -q
python integrity_gate.py --json
python -m compileall -q src tests
ruff check src\ainative tests integrity_gate.py
```

### Acceptance-loop example

```powershell
Set-Location D:\work\AI-Native\game-engine
python -m ainative.session --state s.json --task task.json --workflow workflow.json open
python -m ainative.session --state s.json --result executed-call.json record
python -m ainative.session --state s.json --stage stage.validate_asset stage
python -m ainative.session --state s.json finish
python -m ainative.session --state s.json status
```

The Workflow, the task, and every submitted result live in the `--state` file, so
later commands need only `--state` and their own argument.
