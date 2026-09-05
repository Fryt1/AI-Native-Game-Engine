# Route Selection Authority

This document selects a coarse Route Family before Workflow selection. A Route
is a safety and constraint guardrail, not a complete tool path and not a
`ppt-master`-style product menu.

## Selection

Select the Route Family that best describes the primary lifecycle:

| Route Family | Select when | Typical Workflow |
|---|---|---|
| `host_operation` | A host object, scene, asset, or project state is changed without requiring a cross-host handoff | `host-operation`, `native-blender-operation` |
| `asset_transfer` | An existing asset crosses hosts or must be round-tripped with relation and loss rules | `asset-edit`, `asset-roundtrip` |
| `artifact_pipeline` | An external Artifact is generated, applied, or published | `provider-artifact-apply` |

The Route narrows which Workflow, Stage, Reference, and Governance documents
are relevant. It does not choose a Backend or Call Surface.

## Route guardrails

### `host_operation`

The primary state is inside one host or project. Typical requirements are:

```text
host / project / object resolution
read current state
apply host operation
save or publish host state when requested
read-back validation
```

No Transfer Manifest is required unless the Workflow explicitly adds a transfer
Step.

### `asset_transfer`

The primary state is an existing asset crossing host boundaries. Typical
requirements are:

```text
source / edit / target roles
Transfer Manifest
preservation and acceptable-loss policy
transfer evidence
import / export / reimport validation
```

AssetsBridge and Direct Transfer are Backend choices inside this Route.

### `artifact_pipeline`

The primary state is an external Artifact and its application or publication.
Typical requirements are:

```text
Artifact Contract
provider provenance
format and quality constraints
application evidence
host-side validation
```

A Provider may be used as one Stage or as a preceding Workflow instance.

## Unknown or mixed intent

If the primary lifecycle is ambiguous, stop at a Blocking Gate and ask for the
missing intent. If a request contains multiple lifecycles, compose a sequence
of Workflow instances and pass an Artifact or Transfer Contract between them.
Do not invent a new Route named after the combination.

## Non-responsibilities

This file does not:

- enumerate every Workflow
- inspect a global Tool table
- create a per-run Tool snapshot
- execute a Stage
- decide AssetsBridge versus Direct Transfer
- replace a Workflow's Step order

The Workflow Selection document handles the next decision.
