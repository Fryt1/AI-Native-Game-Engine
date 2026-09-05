# Stage Contract: Resolve Host Context

## Stage ID

```text
stage.resolve_context
```

## Purpose

Make the host, project, Scene/Level, and target object or asset unambiguous
before a later Tool Call. This Stage is conditional and should be omitted when
the Task Contract already contains sufficient identity.

## Inputs

```text
Task Contract
host/project context
object / asset reference
operation target
```

## Outputs

```text
resolved host context
resolved target reference
context evidence
```

## Tool guidance

When resolution needs host state, the Agent selects a concrete Tool from
`ue5.editor` or `blender.editor`. A no-tool Stage may only record that the
provided context was already unambiguous; it must not hide a host side effect.

## Gate

The host and target of the operation must be identifiable. Do not use a display
name when multiple objects or assets may match.

## Failure / Resume

- ambiguous object or project → request clarification or author a resolution Tool Call
- host Tool unavailable → repair the selected Tool implementation
- context cannot be opened → preserve the host log and re-plan if necessary

## Dynamic checklist composition

```text
stage_kind: investigation
knowledge: references-metadata and project-runtime-performance
```

Execution checklist must resolve host/project/object identity.

Acceptance checklist must prove that context is unique, readable, and evidence-backed. Required results need
structured evidence; unresolved facts remain `unknown` and do not complete the
Stage.
