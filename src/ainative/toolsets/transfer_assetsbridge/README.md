# AssetsBridge Transfer Toolset

## Toolset ID

```text
transfer.assetsbridge
```

Owns the complete AssetsBridge maintenance unit:

```text
backend.py
connectors.py
protocol.py
external.py
local.py
execution/blender_endpoint.py
```

Coordinates the UE5 connector, Blender connector, JSON exchange protocol, and upstream external Add-on invocation. It is a sibling of `transfer.direct`, not a hidden fallback.

## Protocol facts

- JSON documents are written atomically and carry a `transfer_id`.
- CLI runtimes assign an isolated bridge subdirectory per logical task; direct users may set `metadata.bridge_dir`.
- Results are rejected when they are stale, malformed, or missing the current transfer identity.
