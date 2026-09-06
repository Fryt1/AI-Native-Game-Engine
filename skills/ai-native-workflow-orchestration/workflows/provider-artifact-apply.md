# Workflow Guidance: Artifact Generate and Apply

## Route Family

```text
artifact_pipeline
```

## Purpose

Generate or receive an external Artifact, validate its Artifact Contract, apply
it to Blender or UE5, and publish the host-side result when requested.

## Recommended macro flow

```text
produce or retrieve the Artifact
    ↓
validate the Artifact Contract when required
    ↓
apply it to the selected host
    ↓
publish when requested
    ↓
read back and validate the host result
```

The Agent may omit optional phases or add additional validation Stages. The
Workflow is not a fixed four-Step executor.

## Call roles

```text
generator Tool or MCP Server tool (e.g. ComfyUI)
    generate or retrieve the external Artifact

blender.editor / ue5.editor
    apply and optionally publish the Artifact

validation.workflow
    validate the declared Artifact and host-side result when configured
```

Generators are reached as ordinary project Tools (`ToolCall`) or direct MCP
Server tools (`McpCall`); there is no separate generator-specific seam. The
generator's output is passed as an explicit Artifact Contract. The host does not
guess a file path or a missing apply operation.

## Agent plan rule

The Agent discovers the relevant Toolsets, writes exact Tool Calls / MCP Calls
in the WorkflowPlan, checks all calls before side effects, and invokes one call
at a time. The Python runtime does not generate the generate/apply sequence.

## Failure / recovery

```text
generation failure     → retry or re-plan the generation Stage
contract failure       → repair the Artifact Contract or re-plan
host application fail  → retry the selected apply Tool
publish failure        → retry the selected publish Tool
validation failure     → retry or re-plan validation
```

A result may hand off to an asset-edit Workflow through an explicit Artifact or
Transfer Contract.

## Dynamic Stage checklist rule

For each selected Stage, the Agent loads the relevant `knowledge/stage-kinds`,
`knowledge/objects`, and `knowledge/operations` documents, then freezes an
execution checklist and an acceptance checklist in the WorkflowPlan. Checklist
knowledge does not name Tools; the final plan stores exact Tool Calls from the
live Registry.

A Tool returning `succeeded` is call-level evidence only. The Stage completes
through evidence-backed `ExecutionItemResult` and `CheckResult` aggregation.
