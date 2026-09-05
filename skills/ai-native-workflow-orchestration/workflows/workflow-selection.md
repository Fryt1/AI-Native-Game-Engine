# Workflow Selection and Dynamic Stage Composition

This document explains how the Agent turns a Task Contract into a stable-format,
dynamic WorkflowPlan. It does not define a Python plan builder.

## Planning chain

```text
Task Contract
    → Route guardrail
    → Workflow guidance
    → Stage-kind / object / operation knowledge
    → Project Tool discovery plus direct MCP discovery
    → Agent-authored WorkflowPlan
    → checklist + Project Tool/MCP feasibility gate
    → Agent-controlled calls
```

## 1. Select Route and Workflow guidance

Select `host_operation`, `asset_transfer`, or `artifact_pipeline`, then read the
matching Workflow guidance. Workflow guidance supplies macro invariants,
dependencies, preservation, evidence, and recovery expectations. It is not a
fixed Step list.

## 2. Compose each dynamic Stage from layered knowledge

For every local goal, load:

```text
Stage kind
    change | investigation | planning

processing object
    geometry | skeleton/binding | animation | material/texture | effects |
    scene/level | references/metadata | project/runtime/performance

operation type
    create | configure | import | export | modify | repair | optimize | convert | batch | publish

current state and user requirements
    actual target, preservation, loss, tolerance, authorization, and evidence
```

These layers produce the Stage execution and acceptance checklists. They do not
name Tools.

## 3. Freeze the Stage checklists

Every required Stage records:

```text
stage_kind
purpose and scope
execution_checklist[]
acceptance_checklist[]
recovery
```

The execution checklist answers what must be handled. The acceptance checklist
answers what must be proven before the Stage can complete.

For a change Stage, both lists are frozen before the first side effect. They may
change only when the user goal changes, environment facts change, or the goal is
proven infeasible. The new plan revision records the reason.

Investigation Stages may expand evidence-gathering items as facts change, but
scope, stop conditions, evidence rules, and unknown handling stay explicit.

## 4. Select exact Project ToolCalls or direct McpCalls

For a project-owned capability:

```text
select relevant Project Toolset
    → describe Toolset
    → list/search project Tools
    → inspect Tool schema and limits
    → select exact ToolCall
```

For a host-native MCP capability:

```text
select configured MCP Server
    → list/inspect its remote Tools through Agent MCP Client
    → select exact McpCall(server_id + tool_name)
```

The final plan stores either:

```text
ToolCall:
    kind: tool
    call_id
    toolset_id
    tool_id
    arguments
    depends_on
    usage

McpCall:
    kind: mcp
    call_id
    server_id
    tool_name
    arguments
    depends_on
    usage
```

`usage` is `execute`, `observe`, `verify`, or `report` for this call only. It is
not a permanent Tool classification. Every call must support an execution or
acceptance item. Complex checkers remain normal project Tools in the same
Registry.

## 5. Check the complete plan before side effects

The gate checks:

```text
plan and checklist structure
Step / Stage / call dependencies
unique checklist and call IDs
all checklist call references exist
all selected project Tools resolve
all selected MCP Server/tool pairs resolve
change Stages have a feasible acceptance path
```

If a later required acceptance call is missing, block before the first change
call. The gate never creates, reorders, or substitutes calls.

## 6. Execute one Tool at a time

```text
WorkflowGuide.start(task, plan, runtime)
    → Agent executes the exact call and submits record_execution_result()
    → ExecutionResult
    → Agent reads the next plan item
```

Execution re-resolves only the selected project ToolCall, or validates the exact
McpCall against the Agent MCP Client. A failed dependency prevents the next dependent
call from running.

## 7. Evaluate the Stage

Execution checklist items can be derived from their referenced ExecutionResults or
recorded explicitly for non-Tool facts. Acceptance checks are evaluated by:

```text
simple deterministic operator
    exists | truthy | equals | set_equals | count_equals | within_tolerance

or complex normal Tool
    structured ExecutionResult → explicit CheckResult
```

The only checklist statuses are:

```text
pass | warn | fail | unknown | needs_human
```

A Tool returning `succeeded` does not satisfy a semantic check unless the
acceptance definition explicitly checks Tool completion rather than domain
state.

## 8. Complete, recover, or re-plan

```text
all required pass       → succeeded
required warn only      → degraded
required fail           → failed
required unknown        → blocked
required needs_human    → needs_approval
```

Local acceptance stays inside the Stage. A final validation Stage may own
cross-Stage invariants. A wrong plan or checklist is superseded; external state
requires an explicit compensating Tool to undo.
