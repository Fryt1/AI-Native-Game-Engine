# Tool, Checklist, and Registry Contract

## Toolset Registry

The Registry publishes one unified Tool space:

```text
register / unregister owner
list/search/describe Toolsets
list/search/describe Tools
resolve an exact selected Tool Call
check live owner readiness
```

It does not own Workflow order, checklist knowledge, or Stage aggregation.

## Tool and Tool Call

A Tool is executable code with an input/output contract. A Tool Call is the
Agent's exact selection:

```text
call_id
toolset_id
tool_id
provider_id
operation
arguments
depends_on
usage
```

`usage` is one of:

```text
execute
observe
verify
report
```

It records the purpose of this call only. The Tool itself is not permanently
classified as an execution or validation Tool.

## Stage checklists

```text
execution checklist
    what must be handled to avoid omission

acceptance checklist
    what must be proven to complete the Stage
```

Checklist knowledge does not bind Tools. The final WorkflowPlan references
exact Tool Calls selected from the live Registry.

## ExecutionResult

A ExecutionResult records call-level facts:

```text
status
outputs
artifacts
warnings
errors
resume_pointer
```

Tool `succeeded` means the invocation completed without a blocking call-level
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

`manual` means an explicit CheckResult must be recorded. Complex comparisons
remain normal Tools and return structured evidence.

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
