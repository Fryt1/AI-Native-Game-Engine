# Transfer Manifest

The Transfer Manifest is the source of truth for cross-host identity and
mapping facts, not a log and not Agent memory.

Minimum fields:

```text
transfer_id
asset_id
source / target / edit app and project
source / target asset path
export file and format
selected Route / Workflow / Profile
selected Backend / Modification Method / Call Surfaces
object / material / skeleton / morph / transform mapping
preserved relations
lost relations
source revision
result status and evidence references
resume pointer
```

The Manifest is created from the Task Contract and then enriched by transfer
Stages. It does not choose the Backend; the Workflow Plan records that choice
and the Manifest records the resulting execution selection.
