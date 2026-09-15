# UE5 Call Surface Reference

UE5 is reached through its MCP server. This repository holds no UE5 executable
path and starts no editor process.

## What an Agent can select

```text
UE5 MCP Server tools
    the operations the running server advertises
```

## Before selecting a call

Confirm through the Agent's own MCP client that the UE5 MCP server is running and
reachable, and that the target project is the intended one. A tool listing, or a
trivial read, proves the server is up. A documented interface is not a live
server.

See [docs/DEPENDENCIES.md](../../../docs/DEPENDENCIES.md) for the supported
engine version and the project prerequisites.

## Recorded evidence

Whether a call needs a visible editor session, Slate, or Content Browser context
affects what the acceptance evidence can prove. Record the surface actually used
as part of the Stage evidence rather than assuming one from the tool name.
