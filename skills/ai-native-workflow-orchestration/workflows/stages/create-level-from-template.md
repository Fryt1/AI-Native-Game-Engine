# Stage Contract: Create Level from Template

## Stage ID

```text
stage.create_level_from_template
```

## Purpose

Create a project-owned UE5 Level from an explicit Level template, load the
created Level into the current UE5 Editor process, verify the required default
objects, save the Level, and return machine-readable evidence.

This Stage is a `host_operation` Stage. It does not create a new Route and it
does not use image or window appearance as proof.

## Inputs

```text
UE5 project context
source template Level asset path
project target Level asset path
expected default object classes or names
reuse_existing policy
ue5.editor Tool
```

Defaults for the current UE5.7 fixture are:

```text
template: /Engine/Maps/Templates/Template_Default
target: /Game/DefaultLightingLevel
expected_default_objects: DirectionalLight, SkyLight
```

The target must be a project asset under `/Game`. The Stage never overwrites an
existing target unless `reuse_existing` is explicitly true.

## Outputs

```text
template asset path
target Level asset path
created / reused_existing flag
loaded Level path
actor count and actor summaries
expected default objects
missing default objects
default_objects_valid
saved flag
UE5 result-file evidence
```

A successful Stage requires all declared expected default objects to be observed
through the UE5 Python API and the target Level to be the loaded Editor world.

## Gate

- UE5 executable, project, and Python entry script are ready
- the template asset resolves in `EditorAssetLibrary`
- the target is a project-owned Level path
- the target does not already exist, or `reuse_existing` is true
- `LevelEditorSubsystem.new_level_from_template` or the supported legacy
  `EditorLevelLibrary` method is available
- the target Level can be loaded and saved
- all required default objects are present

## Tool guidance

```text
ue5.editor
    operation: create_level_from_template
```

The Tool is implemented by the UE5 Python Toolset. Its connection or process
entry method is an executor detail and does not change the Stage contract.

## Verification

The operation must validate programmatically:

```text
Template_Default exists
created target Level exists
current loaded Level == target Level
DirectionalLight exists when requested
SkyLight exists when requested
save operation succeeded
```

The follow-up `stage.validate_result` selects:

```text
ue5.editor Tool
    operation: inspect_level
```

This independent read-back verifies the Level after creation rather than
trusting the creation process exit code alone.

## Failure / Resume

- missing template → fail and resume this Stage after repairing the template path
- target already exists without explicit reuse → block the Stage
- template creation or Level load fails → preserve UE5 logs and resume here
- required default object is missing → fail validation and resume here
- save fails → preserve the created Level and resume here
- no result JSON → treat the Stage as failed

## Dynamic checklist composition

```text
stage_kind: change
knowledge: scene-level plus create operation knowledge
```

Execution checklist must resolve template, target, reuse policy, defaults, load and save requirements.

Acceptance checklist must prove that target Level exists, is loaded, has required objects, and is saved. Required results need
structured evidence; unresolved facts remain `unknown` and do not complete the
Stage.
