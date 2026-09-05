---
name: ai-native-workflow-orchestration
description: Agent-driven dynamic Stage planning, Tool execution, evidence, and acceptance across hosts and providers.
---

# AI Native Workflow Orchestration Skill

This Skill teaches an Agent to build dynamic but auditable Stages across UE5,
Blender, transfer backends, validators, and artifact providers.

## Ownership rule

The Agent owns the WorkflowPlan and calls one Tool at a time. Every required
Stage owns two frozen lists:

```text
execution checklist
    prevents omitted work

acceptance checklist
    prevents Tool success from being mistaken for goal completion
```

Python validates structure and exact Tool readiness, invokes the selected Tool,
records structured results, and deterministically aggregates checklist outcomes.
It does not create the plan or choose the next Tool.

## Loading and planning order

1. Read this `SKILL.md` and run the integrity gate.
2. Read `workflows/routing.md` and `workflows/workflow-selection.md`.
3. Select the Route and Workflow guidance.
4. Read `knowledge/index.md`.
5. Load the relevant Stage-kind, object, and operation knowledge.
6. For project capabilities, query the Project Tool Registry. For host-native
   capabilities, query the configured Agent MCP Client directly.
7. Author the complete WorkflowPlan using
   `templates/workflow-plan-template.md` and the JSON Schema.
8. For every Stage, freeze its execution and acceptance checklists.
9. Select exact Tool Calls for checklist items and check the complete plan before
   any change-side effect.
10. Start `WorkflowSession` and call one selected Tool at a time.
11. Complete a Stage only after execution items and acceptance checks have
    structured evidence-backed results.
12. Continue, retry, wait for evidence/human input, compensate, or supersede and
    re-plan according to the StageResult.

## Core model

```text
Task Contract
    → Route / Workflow guidance
    → Stage kind + object + operation knowledge
    → Project Tool discovery plus direct MCP discovery
    → Agent-authored WorkflowPlan
       └── Stage
           ├── execution_checklist[]
           ├── acceptance_checklist[]
           └── calls[]
    → plan feasibility
    → Agent calls one ToolCall or McpCall
    → ExecutionResult
    → ExecutionItemResult + CheckResult
    → deterministic StageResult
```

## Stage kinds

```text
change
investigation
planning
```

`change` freezes execution and acceptance before side effects.
`investigation` may expand evidence-gathering items, but its scope, stop
condition, evidence rules, and unknowns remain explicit.
`planning` proves feasibility, risks, dependencies, and acceptance methods.

## Checklist outcomes

Every execution or acceptance item uses:

```text
pass
warn
fail
unknown
needs_human
```

Stage aggregation is deterministic:

```text
required fail          → failed
required unknown       → blocked
required needs_human   → needs_approval
required warn only     → degraded / completed with warnings
all required pass      → succeeded
```

A `pass` or `warn` that requires evidence cannot be accepted without an
evidence reference.

## Execution rules

- The Project Tool Registry contains only project-owned Tools; it does not mirror
  MCP Tools.
- A `ToolCall` uses `toolset_id` + `tool_id`. An `McpCall` uses `server_id` +
  `tool_name`.
- `usage` records `execute`, `observe`, `verify`, or `report` for the current
  call only.
- Blender scripts, UE5 scripts, and ComfyUI graphs are registered as ordinary
  project Tools.
- At execution time, re-resolve only the exact selected ToolCall or validate the
  exact selected McpCall. Do not silently substitute another target.
- Complex comparisons remain ordinary project Tools; simple operators use the
  deterministic evaluator.

## Local and global acceptance

Local acceptance is part of each Stage. A separate validation Stage is allowed
only when it owns cross-Stage or whole-Workflow invariants.

## Recovery

```text
Tool or MCP failure
    → retry the selected call or run an explicit compensating Tool

required unknown
    → gather evidence; otherwise block and report what is missing

needs_human
    → wait for the required decision

wrong plan or checklist
    → supersede the revision and let the Agent author a replacement
```

Never delete an acceptance item because the operation failed. Plan invalidation
does not undo external UE5, Blender, or filesystem state.

## Output contract

```text
ExecutionResult
ExecutionItemResult
CheckResult
ChecklistSummary
StageResult
TaskResult
Evidence
```
