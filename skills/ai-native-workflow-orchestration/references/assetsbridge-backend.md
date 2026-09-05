# AssetsBridge Backend

The current public AssetsBridge pair uses a shared bridge directory and two JSON
files:

```text
UE5 → Blender
    from-unreal.json

Blender → UE5
    from-blender.json
```

The UE5 plugin and Blender add-on are both required for a full round-trip. The
shared directory carries the JSON object metadata and exported glTF / GLB file.
The object metadata includes `objectId`, `model`, `internalPath`,
`exportLocation`, `stringType`, `worldData`, material slots / changesets, and
optional texture data.

```text
AssetsBridge Backend
    ├── UE5 Bridge Connector
    └── Blender Bridge Connector
```

Use it when the Task Contract requires UE5 identity or relationship-preserving
round-trip. It can reduce repeated path, slot, Transform, Skeleton, Morph, PBR,
and Reimport configuration, but each preserved relation still needs validation.

This is a Transfer Backend, not a Profile and not the Blender Executor.
