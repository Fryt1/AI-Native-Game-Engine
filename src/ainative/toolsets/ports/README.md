# Project Toolset Ports

Shared protocols that define the interfaces concrete project Toolsets implement.

These protocols are used by the Project Tool Registry and Toolset packages. They do not contain Workflow policy, MCP protocol handling, or host-specific implementation.

## Layout

```text
host_executor.py     HostExecutor seam + HostOperationRequest
tool.py              ToolsetProvider publishing protocol
transfer_backend.py  AssetTransferBackend cross-host transfer protocol
validation.py        WorkflowValidator post-stage validation protocol
```

MCP connections are owned separately by external Agent MCP configuration. MCP Tools are not registered into the Project Tool Registry.

## Maintain

See [src/ainative/toolsets/README.md](../README.md) for Toolset maintenance rules.

## License

MIT © [Fry](https://github.com/Fryt1). See [LICENSE](../../../../LICENSE).
