# UE5 Python Operational Contract

## Headless surface

```text
UnrealEditor-Cmd.exe
```

Use this surface for commandlet-compatible inspection or batch operations.

## Visible Editor surface

```text
UnrealEditor.exe <project>.uproject -ExecutePythonScript=<script.py>
```

Use the ordinary Editor surface when the operation needs Slate, Content Browser,
or editor-only subsystems. Do not describe `UnrealEditor-Cmd.exe` as a visible
Editor test.

## Current implementation note

The repository currently invokes a configured UE5 executable for one selected
Tool operation and reads its result file. It does not yet use UE5 Python Remote
Execution to attach to an already-open Editor. Adding that surface later must
change only the Tool implementation/execution infrastructure, not the
WorkflowPlan model.

## Environment and request files

The executor passes:

```text
AINATIVE_UE5_OPERATION
AINATIVE_UE5_RESULT_FILE
AINATIVE_UE5_REQUEST_FILE
AINATIVE_UE5_BRIDGE_DIR
AINATIVE_UE5_MANIFEST_FILE (transfer stages only)
```

`AINATIVE_UE5_REQUEST_FILE` contains the JSON object:

```json
{
  "operation": "set_actor_transform",
  "parameters": {
    "actor_path": "/Game/Maps/Test.Test:PersistentLevel.Cube",
    "location": [100, 200, 300]
  }
}
```

A Level template request uses the same envelope:

```json
{
  "operation": "create_level_from_template",
  "parameters": {
    "template": "/Engine/Maps/Templates/Template_Default",
    "target": "/Game/DefaultLightingLevel",
    "expected_default_objects": ["DirectionalLight", "SkyLight"]
  }
}
```

## Result contract

The entry script must persist a structured result before the process exits:

```json
{
  "status": "succeeded | failed",
  "operation": "set_actor_transform",
  "actor": {},
  "location": [0, 0, 0],
  "errors": []
}
```

No result file, a non-zero process, or a failed operation status fails the
selected Tool Call. The Agent decides whether to retry or re-plan.

## Timeout and visible-editor proof

This file documents process-launch behavior used by the UE5 Tool implementation.
It is not the Toolset or Workflow model. A visible-editor acceptance test must
separately prove that `UnrealEditor.exe` created a native window; a successful
commandlet process is not that proof.
