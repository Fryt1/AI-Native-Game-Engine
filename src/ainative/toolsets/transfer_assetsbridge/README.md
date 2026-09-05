# AssetsBridge Transfer Toolset

## Toolset ID

```text
transfer.assetsbridge
```

This package owns the complete AssetsBridge maintenance unit:

```text
backend.py
connectors.py
protocol.py
external.py
local.py
execution/blender_endpoint.py
```

It coordinates the UE5 connector, Blender connector, JSON exchange protocol,
and upstream external Add-on invocation. It is a sibling of
`transfer.direct`, not a hidden fallback.
