# Workflow Template

Copy this file to `guidance/<name>.md` and fill it in. A guidance document states
a repeatable macro lifecycle and its invariants. It is not a script, not a fixed
sequence of calls, and not a Workflow — the Agent writes the Workflow.

## Purpose and scope

State the repeatable lifecycle this document owns: when it applies, and what it
explicitly does not cover.

## Recommended macro flow

```text
<phase A> -> <phase B> -> <phase C>
```

State which phases are required, optional, conditional, or may be combined. This
is guidance, not a universal executable sequence.

## Invariants

List what must remain true across every Stage of this lifecycle: relations that
must survive, orderings that must hold, states that must never occur.

## Per-Stage obligations

For each possible Stage, state:

```text
local goal
when the Stage is needed
its dependencies on other Stages
inputs and outputs
what the execution checklist must resolve
what the acceptance checklist must prove
failure and recovery rules
```

Do not prescribe one call per Stage, and do not write MCP tool names here. The
Agent composes each Stage from the Stage kind, the processing object, the
operation type, the current facts, and the user's requirements, then selects the
exact calls and stores them in the Workflow.

## Completion

State what must be true for this lifecycle to be complete, and what evidence must
be returned. A call returning `succeeded` is never sufficient on its own.

## Failure and recovery

State, for each failure class, whether the Agent retries, compensates, gathers
more evidence, waits for a human decision, or authors a replacement Workflow
revision.

## Declaration rules

- A guidance document carries no dependency declaration. Host and model
  prerequisites live in `docs/DEPENDENCIES.md`.
- Keep each guidance document's lifecycle distinct. Do not create one document
  per host/object/operation combination.
- Register a new file in `guidance/index.md` and in `integrity_gate.py`.
