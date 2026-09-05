# Failure Recovery and Resume

Governance is shared execution policy. The Agent-authored WorkflowPlan still
owns which Stage failed and which resume pointer is valid.

## Rules

| Failure | Action |
|---|---|
| Integrity Gate fails | Stop Skill loading and repair the package |
| Workflow cannot be selected | Report missing intent or contract; do not guess |
| Agent plan is structurally invalid | Do not execute; Agent authors a corrected revision |
| Selected Tool is unavailable | Block before side effects; repair or re-plan |
| Selected Backend fails | Preserve evidence and do not silently change Backend |
| Host operation fails | Retry the selected Tool or re-plan its Stage |
| Validation fails | Preserve the report and retry or re-plan validation |
| Conversation is interrupted | Restore the Agent's plan context and resume at the recorded call |

## No silent downgrade

AssetsBridge must not silently become Direct Transfer. A Backend change changes
the output contract and loss semantics, so it requires a new explicit plan
revision.

## Ownership rule

Repair the object that owns the failure:

```text
Workflow contract → Workflow document
Stage contract → Stage document or Agent plan
Tool invocation → Tool implementation or scripts/docs
Asset input → project / Artifact Contract
Transfer relation → Backend or Manifest policy
Validation result → validator or source artifact
```

Plan invalidation does not undo external host state. Use an explicit
compensating Tool or Workflow when undo is required.
