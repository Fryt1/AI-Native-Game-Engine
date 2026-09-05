# Stage Contract: Resolve Asset

## Stage ID

```text
stage.resolve_asset
```

## Purpose

Give the Agent a unique asset reference and record identity facts before a
transfer or asset edit. This Stage is conditional; it is not automatically
inserted into every plan.

## Inputs

```text
Task Contract
source / edit / target host context
asset identifier or file reference
preservation policy
```

## UE5 inputs currently supported

The UE5 AssetsBridge path accepts an asset path from:

```text
manifest.metadata.ue5_asset_path
manifest.asset_id
manifest.source_asset_path
```

The entrypoint normalizes a package path such as:

```text
/Engine/BasicShapes/Cube
```

to an object path:

```text
/Engine/BasicShapes/Cube.Cube
```

## Outputs

```text
resolved asset reference
asset identity facts
source / edit / target roles
Transfer Manifest seed
```

## Tool guidance

If the asset is not already uniquely identified, the Agent selects a source-host
resolution Tool before any transfer Tool. The resolution Tool may be a UE5
Editor Tool, Blender Tool, or file inspection Tool depending on the task.

A Manifest-level identity check and a host export Tool are separate concerns. A
path string alone is never identity evidence, and Python does not create a
hidden resolve operation from this Stage label.

## Gate

The reference must resolve to a unique host object or file. Do not infer an
asset from a display name when multiple candidates exist.

## Failure / Resume

- asset not found → stop and repair the input reference
- wrong asset class → stop and report the class mismatch
- identity not available → stop before making a preservation promise

## Dynamic checklist composition

```text
stage_kind: investigation
knowledge: references-metadata plus the selected object knowledge
```

Execution checklist must resolve stable identity and source/target roles.

Acceptance checklist must prove that identity is unique and preservation promises are evidence-backed. Required results need
structured evidence; unresolved facts remain `unknown` and do not complete the
Stage.
