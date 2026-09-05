# Stage Contract: Modify Asset

## Stage ID

```text
stage.modify_asset
```

## Purpose

Apply the requested asset edit through a compatible Host Tool and
produce an inspectable modified artifact.

## Inputs

````text
edit-host artifact
modification intent
modification parameters
selected Modification Method
```

## Outputs

````text
modified artifact
operation evidence
changed relation facts
```

## Gate

- edit-host context is open and addressable
- mutation parameters are complete and typed
- selected Tool supports the requested operation
- destructive changes have the required confirmation

## Failure / Resume

A host operation error stops the Stage. Preserve the input artifact and process
result, repair the Tool or parameters, and resume at this Stage.

## Tool guidance

For Blender, the Stage may use:

````text
blender.editor Toolset
    CLI + Python or Add-on execution
```

Use the Add-on when current Scene, Selection, Mode, or interactive context is
part of the operation. Use CLI + Python for deterministic background work.

## Dynamic checklist composition

```text
stage_kind: change
knowledge: selected object plus modify knowledge
```

Execution checklist must capture before-state, scope, preservation, rollback, and mutation parameters.

Acceptance checklist must prove that requested properties changed and preservation/forbidden-change checks pass. Required results need
structured evidence; unresolved facts remain `unknown` and do not complete the
Stage.
