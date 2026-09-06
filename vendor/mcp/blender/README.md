# Blender MCP Add-on (vendored source)

Vendored source of the Blender MCP Add-on, used by the Agent's Blender `McpCall`
execution path.

```text
package/
    Blender 5.1.0+ MCP Add-on source
```

## What is and is not installed by this directory

This directory contains the Add-on source. It is not a Blender installation, and
having the source in the repository does not make Blender MCP available. The
Add-on must be installed and enabled inside the target Blender, and its socket
bridge server must be started before MCP calls succeed.

Default bridge:

```text
localhost:9876
```

See `docs/DEPENDENCIES.md` (Blender section) for install, enable, start, version
requirements, Agent MCP Client configuration, and failure checks.
