# Failure Recovery and Resume

Governance is shared execution policy. The Agent-authored WorkflowPlan still
owns which Stage failed and which resume pointer is valid.

## Rules

| Failure | Action |
|---|---|
| Integrity Gate fails | Stop Skill loading and repair the package |
| Workflow cannot be selected | Report missing intent or contract; do not guess |
| Agent Workflow is structurally invalid | Do not execute; Agent authors a corrected revision |
| Selected MCP call is unavailable | Block before side effects; repair or re-plan |
| Selected MCP call fails | Preserve evidence and do not silently substitute another call |
| Host operation fails | Retry the selected call or re-plan its Stage |
| Validation fails | Preserve the report and retry or re-plan validation |
| Conversation is interrupted | Restore the Agent's plan context and resume at the recorded call |

## No silent substitution

A Stage runs the exact MCP call its plan selected. When that call fails, is
unavailable, or turns out not to preserve what the Stage promised, the Agent
preserves the evidence and escalates — it does not quietly swap in a different
MCP server or tool name, or a different file operation, and report the Stage as
if the original call had succeeded. What the Stage claims to preserve is part of
the Workflow's output contract: an Agent that finds the achievable result
unacceptable must re-plan or renegotiate the preservation promise, not widen what
the Stage claims. Any change to the selected call or preservation claim requires
a new explicit Workflow revision.

## Ownership rule

Repair the object that owns the failure:

```text
Workflow contract → Workflow document
Stage contract → Stage document or Agent plan
MCP call → the host's MCP server, or the Agent's call selection
Asset input → project / Artifact Contract
Transfer relation → Agent's export/import MCP call selection
Validation result → the read-back call's evidence or the source artifact
```

Workflow invalidation does not undo external host state. Use an explicit compensating
call or Workflow when undo is required.
