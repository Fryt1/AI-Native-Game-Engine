# Example: Provider Artifact Chain

```text
Stage kind: change
Object: material / texture artifact
Operations: create + import / apply + publish
```

An Agent-authored plan may contain:

```text
Stage: generate Artifact
    execution checklist: provider inputs and generation handled
    acceptance checklist: artifact exists, is readable, typed, and has provenance
    Tool: artifact.<provider>.generate

Stage: apply Artifact
    execution checklist: target and replacement policy resolved, apply performed
    acceptance checklist: host state references the artifact correctly
    Tool: blender.editor.<concrete-apply-tool>

Stage: validate host result
    acceptance checklist: required material/texture facts have evidence
    Tool: validation.workflow.<concrete-validator>
```

The chain uses normal Tools, structured CheckResults, and deterministic Stage
aggregation. It does not require a new Route or a second validation Registry.
