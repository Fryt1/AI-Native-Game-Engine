# Agent WorkflowPlan Template

## Purpose

This template defines the stable structure of one Agent-authored plan. Workflow
content is dynamic, but field names, result contracts, and checklist semantics
are stable.

```text
Workflow guidance
    + Stage-kind knowledge
    + object knowledge
    + operation knowledge
    + current state and user requirements
    → Agent-authored WorkflowPlan
```

The plan can remain in Agent context or be serialized for audit. Python does not
read it as a script or decide the next call.

## Plan shape

```yaml
workflow:
  workflow_id: <selected workflow>
  route: <host_operation | asset_transfer | artifact_pipeline>
  profile: <profile>
  authority_id: <route guardrail>
  plan_id: <task-id>:plan
  revision: 1

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
              call_ids: []
              evidence_required: true

          acceptance_checklist:
            - check_id: <stable check id>
              description: <what must be proven>
              required: true
              call_ids: []
              source_call_id: <Tool Call producing actual evidence>
              actual_path: [<output>, <field>]
              operator: <manual | tool_succeeded | exists | truthy | equals | set_equals | count_equals | within_tolerance>
              expected: <expected value>
              tolerance: null
              evidence_required: true

          calls:
            - kind: tool
              call_id: <unique call id>
              toolset_id: <our exact Toolset>
              tool_id: <our exact Tool>
              arguments: {}
              depends_on: []
              usage: <execute | observe | verify | report>

            - kind: mcp
              call_id: <unique call id>
              server_id: <configured MCP Server>
              tool_name: <exact MCP Tool>
              arguments: {}
              depends_on: []
              usage: <execute | observe | verify | report>

transfer_backend: null
blender_call_surface: null
modification_method: <selected method>
host_app: <ue5 | blender>
host_call_surface: <selected surface>
```

## Stability rules

1. Every required Stage freezes an execution checklist and an acceptance
   checklist before execution.
2. Every Tool Call supports at least one execution or acceptance item.
3. Checklist knowledge never hard-codes a call source. The final plan stores
   exact project Tool references or exact MCP server/tool references.
4. A change Stage checks required project Tools and MCP calls before its first
   side effect.
5. A Tool returning `succeeded` does not automatically satisfy a semantic
   acceptance check.
6. Simple checks use deterministic operators. Complex checks use a normal Tool
   and record its structured output as evidence.
7. A required `unknown` or `needs_human` result cannot be converted to `pass`
   without new evidence or an explicit human decision.
8. A running plan revision is immutable. Changes create a new revision.

## Stage-kind behavior

```text
change
    freeze both checklists and their required Tool Calls before side effects

investigation
    freeze scope and stop conditions; evidence-gathering items may expand as
    new facts arrive, but unknowns remain explicit

planning
    prove goals, constraints, Tool availability, dependencies, risk, and future
    acceptance feasibility
```

## Result chain

```text
ExecutionResult
    → ExecutionItemResult
    → CheckResult
    → deterministic StageResult
    → Agent continues, retries, waits, compensates, or re-plans
```
