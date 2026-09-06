# Stage Contract: Generate or Receive Artifact

## Stage ID

```text
stage.provider_artifact
```

## Purpose

Produce or receive an external Artifact and establish its Artifact Contract for
the next Step.

## Inputs

```text
artifact intent
generator / provider parameters
requested media type / format
output location policy
```

## Call candidates

```text
ordinary project Tool (ToolCall) or direct MCP Server tool (McpCall)
```

Generators such as ComfyUI are reached as ordinary project Tools or as MCP
Server tools; there is no separate generator-specific seam. The Agent selects an
exact published Tool or MCP tool at plan time.

## Outputs

```text
artifact reference
provider id
provenance
parameters
status
```

## Gate

The generation call must return an inspectable result. A prompt or job id alone
is not a usable Artifact.

## Failure / Resume

Generation errors resume at this Stage. Do not report a host mutation failure
when Artifact generation never produced an input.

## Dynamic checklist composition

```text
stage_kind: change
knowledge: create operation plus requested artifact-object knowledge
```

Execution checklist must resolve generator inputs, format, provenance, destination, and failure policy.

Acceptance checklist must prove that artifact exists, is readable, typed, and has provenance/evidence. Required results need
structured evidence; unresolved facts remain `unknown` and do not complete the
Stage.
