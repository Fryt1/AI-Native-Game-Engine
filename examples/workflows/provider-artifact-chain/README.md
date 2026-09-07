# Example: Artifact Generate and Apply Chain

Illustrative provider/artifact checklist closure for an Agent-authored plan that generates, applies, and validates an artifact.

```text
Stage kind: change
Object: material / texture artifact
Operations: create + import / apply + publish
```

An Agent-authored plan may contain:

```text
Stage: generate Artifact
    execution checklist: generator inputs and generation handled
    acceptance checklist: artifact exists, is readable, typed, and has provenance
    Call: ordinary project Tool or MCP Server tool (e.g. ComfyUI)

Stage: apply Artifact
    execution checklist: target and replacement policy resolved, apply performed
    acceptance checklist: host state references the artifact correctly
    Tool: blender.editor.<concrete-apply-tool>

Stage: validate host result
    acceptance checklist: required material/texture facts have evidence
    Tool: validation.workflow.<concrete-validator>
```

The chain uses normal Tools, structured CheckResults, and deterministic Stage
aggregation. Generation is an ordinary ToolCall or McpCall; it does not require
a generator-specific seam or a second Registry.

## License

MIT © [Fry](https://github.com/Fryt1). See [LICENSE](../../../LICENSE).
