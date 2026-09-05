# Stage Contract: Publish Result

## Stage ID

```text
stage.publish_result
```

## Purpose

Persist or publish changed host state when the Agent's WorkflowPlan requires a
durable result.

## Inputs

```text
changed host state
output file / project / package reference
publish policy
Agent-selected publish Tool Call
```

## Toolset candidates

```text
blender.editor
    save-mainfile / export operations

ue5.editor
    save_level / target publication operation
```

## Gate

- output location or target package is explicit
- selected host Tool can persist the result
- save / publish authorization is available

## Skip rule

The Agent may omit this Stage for a read-only inspection or deliberately
transient preview. The plan should make that omission clear when publication
would otherwise be expected.

## Outputs

```text
published artifact or package
save evidence
output reference
```

## Failure / Resume

A save or publish error returns a ExecutionResult with a resume pointer. A file that
existed before the Stage is not evidence that the current mutation was
persisted.

## Dynamic checklist composition

```text
stage_kind: change
knowledge: publish knowledge plus the selected object knowledge
```

Execution checklist must resolve destination, version, dependencies, approval, and rollback.

Acceptance checklist must prove that delivered state exists, is persisted, versioned, and usable downstream. Required results need
structured evidence; unresolved facts remain `unknown` and do not complete the
Stage.
