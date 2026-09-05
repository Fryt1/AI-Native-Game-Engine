# Toolset: Blender Editor

## Toolset ID

```text
blender.editor
```

## Executor

The Blender executor may use CLI + Python for deterministic file operations or
the AI Native Add-on for current Scene, Selection, Active Object, and Mode.

## Registered Tools

```text
inspect-active
configure-scene-unreal
create-cube
import-glb
export-glb
translate-active
set-location
set-scale
rename-active
save-mainfile
import-bridge-json
export-bridge-json
apply-artifact
modify
run-script
```

The external AssetsBridge Add-on is not this Toolset. It is a Connector used by
`transfer.assetsbridge`.
