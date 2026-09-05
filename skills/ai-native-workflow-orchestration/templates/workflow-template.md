# Workflow Guidance Template: <name>

## Purpose

Describe the repeatable macro lifecycle and invariants this Workflow owns.

## Recommended macro flow

```text
<phase A> → <phase B> → <phase C>
```

This is guidance, not a universal executable sequence. State which phases are
required, optional, conditional, or allowed to be combined.

## Steps and Stage contracts

For each possible Step, list:

```text
phase goal
when the Step is needed
Step dependencies
possible Stages
inputs and outputs
validation obligations
failure / recovery rules
```

Do not prescribe one Tool per Stage. The Agent creates the concrete Steps and
Stages for each task. Every required Stage then composes execution and
acceptance checklists from Stage-kind, object, operation, and current-state
knowledge before selecting exact Tool Calls.

## Toolset guidance

List the relevant Toolsets and the invariants that constrain their selection.
Do not create a Tool Call from prose alone; the Agent must query the live
Toolset Registry and store exact Tool IDs in the WorkflowPlan.

## Completion

State what must be true for the Workflow to be complete and what evidence must
be returned.
