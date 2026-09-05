# AssetsBridge JSON Operational Contract

## Files

```text
from-unreal.json
from-blender.json
AssetsBridge.json
```

The JSON payload carries asset identity, model path, object identity, transform,
material slots, skeletal or morph facts, textures, and export locations when the
upstream connector supports them.

## Rules

- The bridge directory is an explicit Workflow artifact location.
- JSON is evidence and input to the next connector, not a replacement for the
  target host import result.
- Validate object identity and declared relations after the target operation.
- A malformed or missing bridge file blocks the next Stage and produces a
  resume pointer.
