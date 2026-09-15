# Call, Checklist, and Result Contract

## No registry, no binding

There is no Toolset Registry, no execution binding, and no provider list. A Workflow
declares its calls directly, and the Agent's own MCP client resolves and runs
them. This repository validates the Workflow's structure and evaluates evidence; it
executes nothing.

## Call and Call Target

A call names *what the Agent will invoke*. Both kinds are first-class, because
both are real work:

```text
project_tool    a Tool implemented in this repository
mcp             a tool on a host's own MCP server, invoked by the Agent's client
```

A call is the Agent's exact selection:

```text
call_id
kind            project_tool | mcp
target
    owner       project_tool: Toolset id   |  mcp: MCP server name
    name        project_tool: Tool id      |  mcp: tool name on that server
arguments
depends_on
```

`kind` defaults to `mcp`. One shape covers both kinds because the Agent, not this
repository, resolves the target. An MCP call such as

```json
{"call_id": "m1", "kind": "mcp", "target": {"owner": "ue5", "name": "set_actor_transform"}}
```

is a normal entry in the Workflow's call graph: it participates in dependency
ordering and can carry a `tool_succeeded` acceptance check.

## Stage checklists

```text
execution checklist
    what must be handled to avoid omission

acceptance checklist
    what must be proven to complete the Stage
```

Checklist composition does not bind Tools. The final WorkflowPlan references the
exact calls the Agent selected.

## ExecutionResult

An ExecutionResult records call-level facts:

```text
call_id
status
kind
target
outputs
artifacts
warnings
errors
resume_pointer
preserved_relations
lost_relations
```

A submitted result must match its declared call: the `call_id` must be declared in
the Workflow, and the `kind` and `target` must agree with that declaration.

Call `succeeded` means the invocation completed without a blocking call-level
error. It does not automatically mean a semantic acceptance item passed.

## ExecutionItemResult and CheckResult

Both use:

```text
pass
warn
fail
unknown
needs_human
```

A pass/warn with `evidence_required: true` needs at least one evidence reference.
Simple deterministic checks support:

```text
tool_succeeded
exists
truthy
equals
set_equals
count_equals
within_tolerance
```

`manual` means an explicit CheckResult must be recorded. Reserve it for genuine
human judgment; a fact an MCP read-back can answer should be checked
deterministically against that call's evidence.

## StageResult

StageResult contains:

```text
ExecutionResult[]
ExecutionItemResult[]
CheckResult[]
execution_summary
acceptance_summary
status
artifacts / warnings / errors / resume_pointer
```

Its status is deterministically aggregated. The Agent decides what to do next,
but cannot override a required `fail`, `unknown`, or `needs_human` without new
evidence or an explicit human decision.
