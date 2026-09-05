# Stage Contract: Read Current State

## Stage ID

```text
stage.read_state
```

## Purpose

Read current state before mutation when the task needs current values or a
before/after comparison. This Stage is conditional.

## Inputs

```text
resolved host context
object / asset reference
properties required by the task
Agent-selected read Tool Call
```

## Toolset candidates

```text
blender.editor
    inspect-active or a more specific read Tool

ue5.editor
    read_actor_transform, inspect_level, or a more specific read Tool
```

## Gate

- target object, Scene, Level, or asset is uniquely identified
- requested properties are explicit
- selected read Tool is ready

## Outputs

```text
before-state facts
object / asset identity
read evidence
```

## Tool rule

The Agent selects the read Tool after querying the Toolset Registry. A natural
language Stage label never causes Python to guess an API or insert a read.

## Failure / Resume

A read failure preserves logs and returns a resume pointer for this Stage. If
the object reference is ambiguous, the Agent should repair the plan or request
clarification instead of reading an arbitrary match.

## Dynamic checklist composition

```text
stage_kind: investigation
knowledge: the selected processing-object knowledge
```

Execution checklist must collect the requested before/current-state facts.

Acceptance checklist must prove that required facts are present or explicitly unknown. Required results need
structured evidence; unresolved facts remain `unknown` and do not complete the
Stage.
