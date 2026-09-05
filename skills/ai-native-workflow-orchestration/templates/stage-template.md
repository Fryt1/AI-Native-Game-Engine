# Stage Contract Template: <name>

## Purpose and scope

State the local goal, affected objects, host scope, and boundaries.

## Stage kind

```text
change | investigation | planning
```

## When to use

State conditions that require, allow, expand, or skip this Stage.

## Inputs and outputs

```text
inputs
outputs
artifacts
evidence
```

## Execution checklist knowledge

List the issues the Agent must resolve so required work is not omitted. Do not
hard-code Tool names in this knowledge document.

## Acceptance checklist knowledge

List the facts that must be proven before the Stage can complete. State
preservation, forbidden-change, tolerance, unknown, and human-decision rules.

## Tool guidance

Describe relevant Toolsets and contracts. The Agent queries the live Registry
and stores exact Tool Calls in the WorkflowPlan. `usage` is per-call metadata,
not a permanent Tool role.

## Aggregation

```text
required fail        → failed
required unknown     → blocked
required needs_human → needs_approval
required warn only   → degraded
all required pass    → succeeded
```

## Failure and recovery

State how to retry, compensate, gather evidence, wait for a decision, or author
a new plan revision. Acceptance items are not deleted because execution failed.
