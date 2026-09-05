# UE5 Call Surface Reference

## Surface roles

### Headless command surface

`UnrealEditor-Cmd.exe` is suitable for commandlet-compatible inspection and
batch operations. It is not evidence that the normal visible Editor window was
opened.

### Editor Python surface

The ordinary `UnrealEditor.exe` surface is required when a Tool needs Slate,
Content Browser, or other editor-only subsystems. It is the relevant surface for
an actual visible Editor acceptance test.

## Current implementation status

The current repository invokes one selected UE5 Tool operation through a
configured executable and structured result file. It does not yet attach to an
already-open Editor through UE5 Python Remote Execution. That future transport
change belongs inside the Tool implementation and must not add a Workflow,
Stage, or Route.

## Tool constraints

The Agent-authored plan should record whether the selected Tool needs:

```text
headless execution
normal Editor application
Slate / Content Browser context
project-specific Python support
Actor / Level context
```

Exact executable flags, environment variables, timeouts, and result-file
behavior are maintained in:

```text
scripts/docs/ue5-python.md
```

## AssetsBridge API surface

The current UE5 plugin exposes the Bridge and export/import types used by the
AssetsBridge transfer Tools. Their availability and target-project behavior must
be verified by the selected Tool implementation rather than inferred from the
executable name.
