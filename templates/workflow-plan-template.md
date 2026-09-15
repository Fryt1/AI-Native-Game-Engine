# Workflow Plan Template

This template defines the stable structure of one Agent-authored Workflow.
Workflow content is dynamic, but field names, result contracts, and checklist
semantics are stable.

```text
Workflow guidance
    + the guidance document's invariants
    + current state and user requirements
    → Agent-authored Workflow
```

The Workflow can remain in Agent context or be serialized for audit. Python does
not read it as a script or decide the next call.

## Workflow shape

```yaml
workflow_id: <task-id>:workflow
guidance: <guidance document this Workflow follows>
route: <host_operation | asset_transfer | artifact_pipeline>
revision: 1
status: <draft | feasible | running | suspended | completed | failed | invalid | superseded>
supersedes_workflow_id: null
replacement_reason: null

steps:
  - step_id: <phase-id>
    purpose: <phase goal>
    depends_on: []
    optional: false

    stages:
      - stage_id: <local-goal-id>
        stage_kind: <change | investigation | planning>
        purpose: <local goal>
        operation: <human-readable operation label>
        depends_on: []
        required: true
        recovery: <retry, compensate, wait, or re-plan>

        execution_checklist:
          - item_id: <stable item id>
            description: <what must be handled>
            required: true
            evidence_required: true
            call_ids: [<call ids this item covers>]
            metadata: {}

        acceptance_checklist:
          - check_id: <stable check id>
            description: <what must be proven>
            required: true
            operator: <manual | tool_succeeded | exists | truthy | equals | set_equals | count_equals | within_tolerance>
            source_call_id: <call producing the evidence this check reads>
            actual_path: [<output>, <field>]
            expected: <expected value>
            tolerance: null
            evidence_required: true
            call_ids: [<call ids this check covers>]
            metadata: {}

        calls:
          - call_id: <unique call id>
            target:
              owner: <MCP server or project Tool owner>
              name: <tool on that owner>
            arguments: {}
            depends_on: [<earlier call ids>]

recovery_pointer: null
warnings: []
```

## Stability rules

1. Every required Stage freezes an execution checklist and an acceptance
   checklist before execution.
2. Every call supports at least one execution or acceptance item.
3. Checklist knowledge never hard-codes a call source. The final Workflow stores
   the exact `target` the Agent selected.
4. A change Stage checks its required calls before its first side effect.
5. A call returning `succeeded` does not automatically satisfy a semantic
   acceptance check.
6. Simple checks use deterministic operators. Complex checks use a normal call
   and record its structured output as evidence.
7. A required `unknown` or `needs_human` result cannot be converted to `pass`
   without new evidence or an explicit human decision.
8. A running Workflow revision is immutable. Changes create a new revision.

## Stage-kind behavior

```text
change
    freeze both checklists and their required calls before side effects

investigation
    freeze scope and stop conditions; evidence-gathering items may expand as
    new facts arrive, but unknowns remain explicit

planning
    prove goals, constraints, call availability, dependencies, risk, and future
    acceptance feasibility
```

## Result chain

```text
ExecutionResult
    → ExecutionItemResult
    → CheckResult
    → deterministic StageResult
    → Agent continues, retries, waits, compensates, or authors a new revision
```

## Validation

`python -m ainative.session open` validates this structure before anything runs.
It rejects a Workflow with duplicate ids, a `depends_on` naming something not
declared earlier, a required Stage missing either checklist, a call no checklist
item references, and a call without `call_id` or a complete `target`.
