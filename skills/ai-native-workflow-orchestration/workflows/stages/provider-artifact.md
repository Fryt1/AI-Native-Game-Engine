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
provider parameters
requested media type / format
output location policy
```

## Toolset candidates

```text
artifact.<provider_id>
```

## Outputs

```text
artifact reference
provider id
provenance
parameters
status
```

## Gate

The provider must return an inspectable result. A prompt or job id alone is not
a usable Artifact.

## Failure / Resume

Provider errors resume at this Stage. Do not report a host mutation failure when
Artifact generation never produced an input.

## Dynamic checklist composition

```text
stage_kind: change
knowledge: create operation plus requested artifact-object knowledge
```

Execution checklist must resolve provider inputs, format, provenance, destination, and failure policy.

Acceptance checklist must prove that artifact exists, is readable, typed, and has provenance/evidence. Required results need
structured evidence; unresolved facts remain `unknown` and do not complete the
Stage.
