# Toolset: Direct Transfer

## Toolset ID

```text
transfer.direct
```

## Executor

`DirectTransferBackend`, currently backed by explicit file-copy I/O plus Blender
import/export calls in transfer Stages.

## Registered Tools

```text
transfer_to_edit_host
return_to_target
export_source
import_for_edit
export_modified
import_target
```

This Toolset is valid only when its file-level loss is explicitly accepted. It
does not promise host asset identity restoration or reimport semantics.
