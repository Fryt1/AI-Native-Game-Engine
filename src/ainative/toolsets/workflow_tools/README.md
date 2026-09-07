# Workflow Tools

Script-backed runners that publish deterministic workflow implementations as ordinary project Tools.

`workflow_tools` contains runners that publish a script or other deterministic workflow implementation as an ordinary project Tool. The Agent calls the Tool through the Tool Registry; the WorkflowPlan does not contain a separate "workflow artifact" call kind.

Current runner:

```text
PythonScriptWorkflowProvider
    JSON object on stdin
    JSON object on stdout
```

The same Tool contract can later be used for a ComfyUI workflow runner. The ComfyUI graph remains the Tool implementation, not a new WorkflowPlan call kind.

## Maintain

See [src/ainative/toolsets/README.md](../README.md) for Toolset maintenance rules.

## License

MIT © [Fry](https://github.com/Fryt1). See [LICENSE](../../../../LICENSE).
