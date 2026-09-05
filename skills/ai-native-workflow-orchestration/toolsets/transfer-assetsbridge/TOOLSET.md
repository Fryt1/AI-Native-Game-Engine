# Toolset: AssetsBridge Transfer

## Toolset ID

```text
transfer.assetsbridge
```

## Executor

`AssetsBridgeBackend`, using UE5 and Blender Bridge Connectors.

## Registered Tools

```text
transfer_to_edit_host
return_to_target
export_source
import_for_edit
export_modified
import_target
```

## Preservation boundary

The current validated relations are:

```text
asset_identity
material_slots
transform
```

The Backend must not silently fall back to Direct Transfer.
