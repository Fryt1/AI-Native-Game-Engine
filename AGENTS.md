# AI Native Game Engine Agent Instructions

This file is the repository-level entry point.

## Required loading order

```text
D:\work\AI-Native-Game-Engine\AGENTS.md
    → D:\work\AI-Native-Game-Engine\skills\ai-native-workflow-orchestration\SKILL.md
    → Skill integrity gate
    → Route / Workflow guidance
    → layered Stage knowledge
    → stable WorkflowPlan template/schema
    → relevant Toolset guides
    → Agent-authored WorkflowPlan
    → docs\DEPENDENCIES.md (when a host or MCP call is involved)
    → docs\DEPENDENCIES.md section for the specific host/MCP (Blender/UE5/ComfyUI/HF)
    → exact Project Tool/MCP call feasibility
    → one-call-at-a-time execution
```

The runtime source root is the directory containing this file. Do not infer a
second project root from the current shell directory.

## Repository purpose

This repository implements Agent-driven dynamic Stages across UE5, Blender,
transfer backends, validators, and external tools such as ComfyUI.

```text
Agent Intent
    → Task Contract
    → Route / Workflow guidance
    → layered Stage knowledge
    → Project Tool discovery plus direct MCP discovery
    → Agent-authored WorkflowPlan
       └── each Stage freezes execution + acceptance checklists
    → plan/checklist/Tool feasibility gate
    → Agent calls one ToolCall or McpCall at a time
    → ExecutionResult + Evidence
    → deterministic checklist evaluation
    → StageResult
    → continue / retry / wait / compensate / re-plan
```

A saved WorkflowPlan is optional audit data. Python does not interpret a plan
file as a script or decide which call comes next.

## Planning rules

- Route and Workflow follow the requested lifecycle, not whichever Tool happens
  to be installed.
- Workflow documents provide macro guidance and invariants, not one universal
  sequence.
- Compose each Stage from Stage kind, processing object, operation type, current
  facts, and user requirements.
- Every required Stage freezes an execution checklist and an acceptance
  checklist before execution.
- A change Stage checks the Project Tools and MCP calls required for execution and
  acceptance before its first side effect.
- For a project capability, query the Project Tool Registry. For MCP, query the configured Agent MCP Client directly. Do not copy MCP Tools into the Project Registry.
- Before selecting a host or MCP call, load docs\DEPENDENCIES.md and confirm the required Python, Blender, UE5, add-on/plugin, and Agent prerequisites.
- Before selecting a Blender `McpCall`, load docs\DEPENDENCIES.md (Blender section) and confirm the Blender version, installed/started MCP Add-on bridge, and Agent client prerequisites; do not assume the vendored Add-on source alone is a live Blender MCP Server.
- Before selecting a UE5 `McpCall`, also load docs\DEPENDENCIES.md (UE5 section) and confirm the engine, target project, Editor process, and Agent client prerequisites; do not assume this repository contains a live UE5 MCP Server.
- The final plan stores exact calls. Every call supports at least one checklist
  item.
- `usage` on a Tool Call (`execute`, `observe`, `verify`, `report`) records this
  call's purpose; it is not a permanent Tool classification.
- During execution, only re-resolve the already selected project ToolCall or
  validate the exact McpCall. Do not search or silently substitute another call,
  MCP Server, Tool, or Backend.
- Tool success proves only that the call completed. Stage completion comes from
  structured checklist results and evidence.
- Required checklist results use `pass`, `warn`, `fail`, `unknown`, or
  `needs_human`.
- Required `fail`, `unknown`, and `needs_human` results cannot be treated as
  completion.
- Local acceptance belongs to the current Stage. A separate validation Stage is
  allowed for cross-Stage invariants.

## Stage kinds

```text
change
    freeze execution and acceptance before side effects

investigation
    freeze scope and stop conditions; evidence checks may expand as facts change

planning
    prove goals, constraints, Tool feasibility, dependencies, risks, and future
    acceptance methods
```

## Directory ownership

```text
D:\work\AI-Native-Game-Engine\
├── docs\                 cross-cutting architecture and maintenance docs
├── skills\               Agent-facing Skill package
├── src\ainative\
│   ├── agent\            Agent facade and execution session
│   ├── orchestration\    plan/stage/checklist mechanics
│   ├── registry\         Project Tool Registry
│   └── toolsets\         concrete project Toolsets
├── scripts\              runners, fixtures, checks, and probes
├── tests\                unit/integration tests mirroring the core units
├── projects\fixtures\   reproducible host fixtures
├── vendor\               external AssetsBridge sources
└── artifacts\            evidence, scratch output, and historical archive
```

### Code ownership

- `D:\work\AI-Native-Game-Engine\src\ainative\agent\` owns the Agent-facing
  session API.
- `D:\work\AI-Native-Game-Engine\src\ainative\orchestration\` owns generic
  plan, Stage, checklist, Route, and acceptance behavior.
- `D:\work\AI-Native-Game-Engine\src\ainative\registry\` owns Toolset
  discovery and exact Tool resolution.
- Each directory under
  `D:\work\AI-Native-Game-Engine\src\ainative\toolsets\` owns one concrete
  Toolset and its implementation details.
- `D:\work\AI-Native-Game-Engine\skills\ai-native-workflow-orchestration\`
  owns Agent guidance, layered knowledge, templates, and Toolset guides.
  Each Toolset guide is maintained at
  `skills\ai-native-workflow-orchestration\toolsets\<unit>\TOOLSET.md`.
- `D:\work\AI-Native-Game-Engine\src\ainative\toolsets\ports\` owns the
  interfaces implemented by concrete Toolset providers.

## Final execution architecture

```text
WorkflowPlan Stage calls[]
    ├── ToolCall → Project Tool Registry → our Tool implementation
    └── McpCall  → Agent MCP Client → named MCP Server/tool
```

Blender/UE5 scripts and ComfyUI graphs may be registered as project Tools; an external ComfyUI
MCP is a direct McpCall. None of these introduces a third WorkflowPlan call type.
Reusable Workflow Definitions live in
`D:\work\AI-Native-Game-Engine\workflows\` and are promoted only after
machine verification and required human review.

## Engineering rules

- Do not reintroduce Capability, CapabilityBinding, a Capability Registry, or a
  per-run Capability Snapshot.
- Do not add a second execution/checker Tool Registry.
- Do not reintroduce Python plan generation or a whole-plan scheduler.
- Do not infer Stage success from Tool success alone.
- Keep complex checkers as normal Tools. Keep simple checks in the deterministic
  Stage evaluator.
- Freeze acceptance items before change-side effects. Do not delete an item
  merely because execution failed.
- Preserve ExecutionResults, checklist results, StageResults, and Evidence.
- Do not silently change Tool, MCP Server, Backend, or loss policy.
- Do not initialize or alter Git history unless explicitly requested.

## Verification commands

```powershell
Set-Location D:\work\AI-Native-Game-Engine
python -m pytest -q
python skills\ai-native-workflow-orchestration\scripts\integrity_gate.py --json
python -m compileall -q src scripts skills tests
ruff check src\ainative scripts\e2e scripts\agent scripts\docs scripts\workflows tests
```
