# Blender Call Surfaces

Blender is reached through its MCP server. This repository holds no Blender
executable path and starts no Blender process.

## What an Agent can select

```text
Blender MCP Server tools
    the operations the running server advertises
```

The server decides which Blender context an operation needs. Whether an operation
requires the current interactive session (Scene, Selection, Active Object, Mode)
or works from a background state is the server's concern, not a Workflow field.

## Before selecting a call

Confirm through the Agent's own MCP client that the Blender MCP server is running
and reachable. A tool listing, or a trivial read, proves it. A documented
interface is not a live server.

See [docs/DEPENDENCIES.md](../../../docs/DEPENDENCIES.md) for the supported
Blender and MCP Add-on versions.
