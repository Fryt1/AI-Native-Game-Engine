# Workflow Guidance: Artifact Generate and Apply

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
generator MCP Server tool (e.g. ComfyUI)
    generate or retrieve the external Artifact

Blender / UE5 MCP
    apply and optionally publish the Artifact

Blender / UE5 MCP
    read-back calls that prove the declared Artifact and host-side result
```

Generators are reached as host MCP server tools; there is no separate
generator-specific seam. The generator's output is passed as an explicit
Artifact Contract. The host does not guess a file path or a missing apply
operation.

## Agent Workflow rule

The Agent reads the relevant host and generator MCP documentation, selects the
exact calls, confirms them before side effects, and invokes one at a time. The
Python runtime does not generate the generate/apply sequence.

## Failure / recovery

```text
generation failure     → retry or re-plan the generation Stage
contract failure       → repair the Artifact Contract or re-plan
host application fail  → retry the selected apply MCP call
publish failure        → retry the selected publish MCP call
validation failure     → retry or re-plan validation
```

A result may hand off to an asset-edit Workflow through an explicit Artifact or
Transfer Contract.

## Dynamic Stage checklist rule

For each selected Stage, the Agent composes an execution checklist and an
acceptance checklist from the Stage kind, the processing object, the operation
type, the current facts, and the user's requirements, then freezes both in the
Workflow. The Agent supplies that domain competence; the checklist does not
name calls, and the final Workflow stores the exact MCP calls the Agent selected.

A call returning `succeeded` is call-level evidence only. The Stage completes
through evidence-backed `ExecutionItemResult` and `CheckResult` aggregation.
