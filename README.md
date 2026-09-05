# AI Native Game Engine

An Agent-driven WorkflowPlan runtime for UE5, Blender, MCP servers, transfer backends, validators, and reusable ComfyUI/script-backed Tools.

## Architecture

```text
User Intent
    → Task Contract
    → Route / Workflow guidance
    → Stage-kind + object + operation knowledge
    → Agent-authored WorkflowPlan
       └── each Stage freezes execution + acceptance checklists
    → checklist and exact Tool/MCP feasibility gate
    → Agent calls one ToolCall or McpCall at a time
    → ExecutionResult + Evidence
    → ExecutionItemResult + CheckResult
    → deterministic StageResult
    → continue / retry / wait / compensate / re-plan
```

Workflow documents lock macro invariants, not a universal Step list. The Agent
chooses the concrete Steps, dynamic Stages, checklist items, and exact Tool
Calls for the current task.

## Stage closure

```text
execution checklist
    prevents omitted preparation or work

acceptance checklist
    prevents Tool success from being mistaken for goal completion
```

Checklist item results are:

```text
pass | warn | fail | unknown | needs_human
```

Required failures, unknowns, and human decisions block completion. A Stage with
only warnings completes as `degraded`; all required items passing completes as
`succeeded`.

## Intent and Tool ownership

The runtime has no built-in prompt router. The Agent must supply the
`TaskContract`, inspect the selected Workflow guidance and live Tool/MCP
surfaces, then author the exact `WorkflowPlan`. An optional
`IntentInterpreter` may be injected only when it is implemented and owned by
the Agent/LLM integration; the runtime never guesses a Route or Tool.

## Agent-facing API

```python
guide = WorkflowGuide()
skill = guide.load_skill(task)
session = guide.start(task, agent_plan, runtime)

# The Agent executes each Tool/MCP itself, then submits the raw structured result.
session.record_execution_result(execution_result)
stage_result = session.complete_stage("stage.change")
result = session.finish()
```

`WorkflowSession` never invokes a Tool or MCP Server. It validates the submitted
`ExecutionResult` against the plan, records evidence, evaluates each Stage, and
aggregates the final result. For a complex/manual check, the Agent records a
structured `CheckResult` before calling `complete_stage()`.

## Two execution paths

```text
ToolCall
    → Project Tool Registry
    → AssetsBridge / Validation / script-backed / ComfyUI Tools

McpCall
    → Agent MCP Client
    → Blender MCP / UE5 MCP
```

A ToolCall or McpCall can be used to `execute`, `observe`, `verify`, or `report`.
This is per-call audit metadata, not a permanent Tool role. Reusable Workflow
Definitions live under `workflows/` and may combine both paths.

## Project Tool CLI

Every project-owned Tool in the Registry also has a process-level CLI so an
Agent can call it directly without a project MCP wrapper:

```powershell
python -m ainative.tools --config runtime.json --toolset blender.editor --operation set-location --args '{"location":[1,2,3]}'
python -m ainative.tools --config runtime.json --toolset ue5.editor --operation save_level --task task.json
```

The CLI resolves the exact Tool through the Project Tool Registry, executes the
project-owned implementation, and prints a structured `ExecutionResult` as JSON.
It does not read plans or schedule Stages. Blender MCP / UE5 MCP remain
configured directly on the Agent; we do not wrap them.

## Knowledge structure

```text
skills/ai-native-workflow-orchestration/knowledge/
├── stage-kinds/
├── objects/
└── operations/
```

The Agent combines relevant knowledge with current state and user requirements
to produce the Stage checklists. The project does not maintain every
host/object/operation combination as a fixed recipe.

## Documentation map

- `AGENTS.md` — repository-wide Agent rules
- `skills/ai-native-workflow-orchestration/SKILL.md` — Skill contract
- `skills/ai-native-workflow-orchestration/knowledge/` — layered Stage knowledge
- `skills/ai-native-workflow-orchestration/templates/workflow-plan-*` — stable plan format and schema
- `skills/ai-native-workflow-orchestration/toolsets/` — Toolset contracts
- `docs/FINAL_ARCHITECTURE.md` — final architecture (conclusion; history in `artifacts/archive/docs/`)
- `docs/MAINTENANCE.md` — maintenance, extension, and directory rules
- `docs/VALIDATION_REPORT.md` — current verification evidence
- `docs/cli.md` — Project Tool CLI usage
- `workflows/` — published reusable Workflow Definitions

## Development checks

```powershell
python -m pytest -q
python skills\ai-native-workflow-orchestration\scripts\integrity_gate.py --json
python -m compileall -q src scripts skills tests
ruff check src/ainative scripts/e2e scripts/agent scripts/workflows tests
```
