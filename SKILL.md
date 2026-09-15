---
name: ai-native-game-engine
description: Agent-driven Stage composition, MCP call execution, evidence, and acceptance across hosts and external tools.
---

# AI Native Game Engine Skill

This Skill teaches an Agent to build dynamic but auditable Stages across UE5,
Blender, and external tools such as ComfyUI.

## Ownership rule

The Agent owns the Workflow and calls one MCP tool at a time. Every required Stage owns
two frozen lists:

```text
execution checklist
    prevents omitted work

acceptance checklist
    prevents call success from being mistaken for goal completion
```

Python validates the Workflow's structure, records the structured results the Agent
submits, and deterministically aggregates checklist outcomes. It does not decide
what runs next.

## Loading order

1. Read this `SKILL.md`.
2. Run the integrity gate: `python integrity_gate.py --json`.
3. Read `guidance/` and pick the document matching the task's lifecycle.
4. Read `references/` for host and MCP interfaces.
5. Load `docs/DEPENDENCIES.md` for the host or MCP server involved and confirm
   its prerequisites before selecting any call.

This package ships no per-object or per-operation knowledge base. The working
order below is the composition rule, and the Agent supplies the domain
competence for the processing object, the operation type, and the current facts.

Host capabilities (Blender, UE5, ComfyUI) are reached through their own MCP
servers by the Agent's MCP client. This package documents what to call; it does
not execute host software.

## Workflow rules

These hold for every Workflow you author.

1. Every required Stage freezes an execution checklist and an acceptance
   checklist before execution.
2. Every call supports at least one execution or acceptance item.
3. Checklist knowledge never hard-codes a call source. The final Workflow stores
   the exact `target` you selected.
4. A change Stage checks its required calls before its first side effect.
5. A call returning `succeeded` does not automatically satisfy a semantic
   acceptance check.
6. Simple checks use deterministic operators. Complex checks use a normal call
   and record its structured output as evidence.
7. A required `unknown` or `needs_human` result cannot be converted to `pass`
   without new evidence or an explicit human decision.
8. A running Workflow revision is immutable. Changes create a new revision.

Start from `templates/workflow-plan-template.json` rather than hand-writing the
JSON. `templates/workflow-plan-template.md` explains each field.

## Working order

1. State the task as a Task Contract: objective, direction, what must be
   preserved, and what loss is acceptable.
2. Break it into Stages, composing each from Stage kind, processing object,
   operation type, current facts, and the user's requirements.
3. For every required Stage, freeze the execution and acceptance checklists
   before any side effect.
4. Select the exact calls that satisfy those checklists.
5. Write the Workflow as JSON and hand it to Python with `open`, then call one at a
   time and record each structured result as evidence against that same state
   file:

   ```powershell
   python -m ainative.session --state s.json --task task.json --workflow workflow.json open
   python -m ainative.session --state s.json --result executed-call.json record
   ```

   `open` validates the Workflow structure and writes `--state`, which carries the
   Workflow and the task for the rest of the loop. Use `record` for a call result,
   `item` for an execution checklist item, and `check` for a manual acceptance
   check. Later commands need only `--state` plus their own argument.
6. Complete a Stage only by asking for the deterministic verdict against its
   frozen checklists, never from a call's own status:

   ```powershell
   python -m ainative.session --state s.json --stage stage.validate_asset stage
   python -m ainative.session --state s.json finish
   python -m ainative.session --state s.json status
   ```

   Exit codes tell you what happened: 0 is a non-blocking result, 1 is blocking
   or failing, and 2 means the command itself could not run. A call returning
   `succeeded` does not complete a Stage — a `truthy` acceptance check on an
   empty `preserved_relations` yields check `fail`, then stage `failed`, then
   exit 1. Python never picks a call, orders a Stage, or adds a checklist item.
7. Continue, retry, wait for evidence or a human decision, compensate, or
   author a replacement Workflow according to the Stage result.

## Core model

```text
Task Contract
    → Stage kind + processing object + operation type + current facts
    → Agent-authored Workflow
       └── Stage
           ├── execution_checklist[]
           ├── acceptance_checklist[]
           └── calls[]
    → Agent calls one MCP tool
    → ExecutionResult
    → ExecutionItemResult + CheckResult
    → deterministic StageResult
```

## Stage kinds

```text
change
investigation
planning
```

`change` freezes execution and acceptance before side effects.
`investigation` may expand evidence-gathering items, but its scope, stop
condition, evidence rules, and unknowns remain explicit.
`planning` proves feasibility, risks, dependencies, and acceptance methods.

## Checklist outcomes

Every execution or acceptance item uses:

```text
pass
warn
fail
unknown
needs_human
```

Stage aggregation is deterministic:

```text
required fail          → failed
required unknown       → blocked
required needs_human   → needs_approval
required warn only     → degraded / completed with warnings
all required pass      → succeeded
```

A `pass` or `warn` that requires evidence cannot be accepted without an
evidence reference.

## Execution rules

- A call names a `target` of owner/name: the MCP server, and the tool on it.
  For an MCP call the owner is the MCP server and the name is the tool on it.
- Confirm a host capability exists and is running before depending on it; a
  documented interface is not a live server.
- At execution time, use the exact call you selected. Do not silently substitute
  another target, server, or backend.
- Simple operators use the deterministic evaluator.
- Every call supports at least one checklist item.

## Local and global acceptance

Local acceptance is part of each Stage. A separate validation Stage is allowed
only when it owns cross-Stage or whole-Workflow invariants.

## Recovery

```text
MCP call failure
    → retry the selected call or run an explicit compensating call

required unknown
    → gather evidence; otherwise block and report what is missing

needs_human
    → wait for the required decision

wrong Workflow or checklist
    → author a replacement Workflow
```

Never delete an acceptance item because the operation failed. Workflow invalidation
does not undo external UE5, Blender, or filesystem state.

## Output contract

```text
ExecutionResult
ExecutionItemResult
CheckResult
ChecklistSummary
StageResult
TaskResult
Evidence
```
