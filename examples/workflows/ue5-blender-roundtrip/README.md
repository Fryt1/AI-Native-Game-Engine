# Example: UE5 → Blender → UE5

## Intent

Modify a UE5 Static Mesh in Blender while preserving declared identity,
material-slot, and Transform relations.

## Agent composition

```text
Stage kind: change
Object: geometry + references/metadata
Operations: export + import + modify
Current requirements: preserve identity, slots, Transform
```

The Agent uses those layers to author Stages such as:

```text
Stage: transfer to Blender
    execution checklist
        source resolved
        selected Backend ready
        export/import performed
    acceptance checklist
        edit-host representation exists
        declared preservation/loss evidence recorded
    Tool Call
        transfer.assetsbridge.transfer_to_edit_host

Stage: modify asset
    execution checklist
        before-state and affected scope known
        mutation performed and saved
    acceptance checklist
        requested Transform changed
        forbidden properties did not change
    Tool Call
        blender.editor.translate-active

Stage: return to UE5
    execution checklist
        modified representation exported and imported
    acceptance checklist
        target asset exists and import has no blocking error
    Tool Call
        transfer.assetsbridge.return_to_target

Stage: cross-host validation
    acceptance checklist
        asset_identity pass
        material_slots pass
        transform pass
    Tool Call
        validation.workflow.validate
```

Each call has per-call usage. The validation Tool remains in the same Registry;
there is no checker Registry. Direct Transfer may replace the transfer Toolset
only in a new plan whose declared loss is acceptable.
