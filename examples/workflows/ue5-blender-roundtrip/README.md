# Example: UE5 → Blender → UE5

Illustrative asset-transfer round-trip example: modify a UE5 Static Mesh in Blender while preserving declared identity, material-slot, and Transform relations.

## Intent

Modify a UE5 Static Mesh in Blender while preserving declared identity, material-slot, and Transform relations.

## Agent composition

```text
Stage kind: change
Object: geometry + references/metadata
Operations: export + import + modify
Current requirements: preserve identity, slots, Transform
```

The Agent uses those layers to author Stages such as transfer to Blender, edit, return to UE5, and validate. This example is illustrative, not a fixed recipe.

## Acceptance note

A returned GLB or a successful process exit is not proof of preservation. Use the validation Tool against source/result snapshots, and read the target host back when the Workflow promises it.

## License

MIT © [Fry](https://github.com/Fryt1). See [LICENSE](../../../LICENSE).
