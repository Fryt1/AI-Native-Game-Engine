# Orchestration Core

This package owns the generic mechanics shared by every Agent Workflow and
Toolset. It does not contain UE5, Blender, AssetsBridge, or provider-specific
implementation.

## Modules

```text
D:\work\AI-Native-Game-Engine\src\ainative\orchestration\contracts\
    Task, WorkflowPlan, Stage, checklist, ToolCall, and result contracts

D:\work\AI-Native-Game-Engine\src\ainative\orchestration\planning\
    Route/Workflow context selection, structural plan validation, and exact
    selected-Tool feasibility

D:\work\AI-Native-Game-Engine\src\ainative\orchestration\stages\
    one selected ToolCall or McpCall execution seam

D:\work\AI-Native-Game-Engine\src\ainative\orchestration\acceptance\
    deterministic execution/acceptance checklist evaluator

D:\work\AI-Native-Game-Engine\src\ainative\orchestration\route_guards.py
    coarse Route preconditions only

D:\work\AI-Native-Game-Engine\src\ainative\orchestration\runtime_context.py
    live Project Tool provider context and exact selected-call resolution
```

## Runtime chain

```text
Agent-authored WorkflowPlan
    → exact plan/checklist/Tool/MCP feasibility
    → Agent calls one ToolCall or McpCall
    → ExecutionResult + Evidence
    → ExecutionItemResult / CheckResult
    → StageResult
```

The Agent owns the plan and chooses the next call. Python validates and executes
only the selected call; it does not generate or schedule the complete plan.
