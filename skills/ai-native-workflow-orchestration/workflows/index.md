# Workflow, Knowledge, and Toolset Inventory

Maintainer-only inventory for the Skill package. It is not runtime dispatch
input and is not the Toolset Registry.

## Route Families

- `host_operation`
- `asset_transfer`
- `artifact_pipeline`

## Workflow guidance

- `host-operation.md`
- `asset-edit.md`
- `asset-roundtrip.md`
- `native-blender-operation.md`
- `provider-artifact-apply.md`

## Dynamic Stage knowledge

```text
knowledge/stage-kinds/
    change.md
    investigation.md
    planning.md

knowledge/objects/
    geometry.md
    skeleton-binding.md
    animation.md
    material-texture.md
    effects-simulation.md
    scene-level.md
    references-metadata.md
    project-runtime-performance.md

knowledge/operations/
    create.md
    configure.md
    import.md
    export.md
    modify.md
    repair.md
    optimize.md
    convert.md
    batch.md
    publish.md
```

The Agent composes execution and acceptance checklists from these layers plus
current state and user requirements.

## Profiles

- `profiles/default.md`
- `profiles/interactive.md`
- `profiles/headless-batch.md`

## Stage Contracts

- `stages/resolve-context.md`
- `stages/read-state.md`
- `stages/resolve-asset.md`
- `stages/create-level-from-template.md`
- `stages/transfer-to-edit-host.md`
- `stages/modify-asset.md`
- `stages/apply-change.md`
- `stages/return-to-target.md`
- `stages/publish-result.md`
- `stages/validate-asset.md`
- `stages/validate-result.md`
- `stages/provider-artifact.md`
- `stages/apply-artifact.md`

## Plan and contract templates

- `templates/workflow-plan-template.md`
- `templates/workflow-plan-template.json`
- `templates/workflow-plan-schema.json`
- `templates/workflow-template.md`
- `templates/stage-template.md`
- `templates/toolset-template.md`

## Toolset documents

- `toolsets/ue5-editor/TOOLSET.md`
- `toolsets/blender-editor/TOOLSET.md`
- `toolsets/transfer-assetsbridge/TOOLSET.md`
- `toolsets/transfer-direct/TOOLSET.md`
- `toolsets/workflow-validation/TOOLSET.md`

## Maintenance rules

1. Add a Workflow when a repeatable macro lifecycle deserves a name.
2. Add Stage-kind knowledge only when execution/acceptance behavior differs.
3. Add object knowledge for genuinely different facts and preservation rules.
4. Add operation knowledge for genuinely different execution and proof rules.
5. Add a Tool when an executable function is stable enough to register.
6. Do not maintain every host/object/operation combination as a recipe.
7. Check exact Tool Calls and acceptance feasibility before change-side effects.
8. Update this inventory and the integrity gate when canonical files change.
9. Published Workflow packages declare a **Shared guidance** link in their
   `WORKFLOW.md` (see `workflows/<id>/WORKFLOW.md`). When a guidance file in
   this directory changes, review every published workflow that links to it
   and update the package if the invariants or route changed.
10. When a published Workflow's route or lifecycle changes, update both its
    `plan.template.yaml` route and its `WORKFLOW.md` Shared guidance line so
    they never diverge.
