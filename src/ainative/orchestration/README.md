# Orchestration Core

Generic WorkflowPlan, Stage, and acceptance mechanics shared by every Agent Workflow and Toolset.

The core does not contain UE5, Blender, AssetsBridge, or provider-specific implementation. It validates structure and executes only the exact selected Tool call; plan generation and scheduling stay with the Agent.

## Modules

```text
orchestration/contracts/
    Task, WorkflowPlan, Stage, checklist, ToolCall, and result contracts

orchestration/planning/
    Route/Workflow context selection, structural plan validation, and exact selected-Tool feasibility

orchestration/acceptance/
    deterministic execution/acceptance checklist evaluator

route_guards.py
    coarse Route preconditions

runtime_context.py
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

The Agent owns the plan and chooses the next call. Python validates and executes only the selected call; it does not generate or schedule the complete plan.

## Maintain

See [docs/MAINTENANCE.md](../../../docs/MAINTENANCE.md) for orchestration invariants and extension rules.

## License

MIT © [Fry](https://github.com/Fryt1). See [LICENSE](../../../LICENSE).
