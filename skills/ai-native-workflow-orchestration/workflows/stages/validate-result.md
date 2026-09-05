# Stage Contract: Validate Host Result

## Stage ID

```text
stage.validate_result
```

## Purpose

Read back the host result and verify the facts promised by the Agent's plan.
This Stage is required when the task requests proof or when the Workflow
invariant requires independent validation.

## Inputs

```text
operation result
changed object / asset reference
expected fields or values
published artifact when applicable
Agent-selected read or validation Tool Call
```

## Outputs

```text
observed after-state
comparison result
validation evidence
warnings / errors
```

## Gate

- operation result and target reference are available
- expected validation facts are explicit
- selected read/validation Tool can inspect the target

## Tool guidance

The Agent may use the same host Tool for a read-back when its contract supports
independent observation, or a separate validation Tool when stronger evidence
is required. A successful process exit or an existing file alone is not proof.

## Failure / Resume

Validation failure preserves the operation result and target evidence. Resume at
this Stage or re-plan the owning mutation Stage according to the ExecutionResult.

## Dynamic checklist composition

```text
stage_kind: investigation
knowledge: the owning change Stage object/operation knowledge
```

Execution checklist must read actual post-operation state and required logs.

Acceptance checklist must prove that every local or cross-Stage invariant has evidence-backed CheckResult. Required results need
structured evidence; unresolved facts remain `unknown` and do not complete the
Stage.
