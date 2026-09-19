# Guidance Template: Node Tree in Machine-Readable Form

A guidance document states a macro lifecycle. Until now it stated it as prose, so
the Agent re-derived the Workflow structure on every run. This template adds a
**machine-readable node tree** so the structure is fixed once and the Agent
supplies only values.

```text
guidance front matter + task values  ->  Workflow JSON
```

**The conversion is performed by the Agent, not by this repository.** This
repository does not generate a Workflow (see `AGENTS.md`, "the Agent decides what
runs next"). What this repository owns is the shape the conversion target must
have, and the deterministic verdict on the result:

```powershell
python -m ainative.session --state s.json --task task.json --workflow workflow.json open
```

`open` validates the Workflow's structure and the entry gate. So the claim "this
template converts correctly" is testable: convert it, hand the result to `open`,
and a template whose output fails `open` is a broken template.

---

## File shape

A guidance document that supports conversion has two parts:

1. **YAML front matter** — the node tree, checklist skeletons, and which values
   the caller must supply. Parsed by the Agent's converter.
2. **Prose** — the invariants, failure rules, and judgement an Agent still needs.
   Not parsed; read by the Agent.

A Workflow **is** a tree: one root node, and every node is either a **STAGE**
leaf (calls plus its two frozen checklists) or a **WORKFLOW** composite
(children, plus checks that read a descendant's verdict). A phase is not a
separate type — a phase is a WORKFLOW node used for grouping. There is no Step.

```markdown
---
guidance_id: <stable id, also the file stem>
route: <the TaskRoute this lifecycle serves>
summary: <one line>

values:
  <value_name>:
    type: <string | number | boolean>
    required: <true | false>
    default: <used when not required>
    description: <what the caller decides>

# The document's single root node. A lifecycle that is a sequence makes it a
# WORKFLOW node whose children are that sequence.
root:
  node_id: <stable id, unique among its siblings>
  kind: workflow
  purpose: <what this lifecycle is>
  required: <true | false>
  depends_on: [<references to nodes that must finish first; empty at the root>]
  children:

    - node_id: <stable id, unique among its siblings>
      kind: stage
      purpose: <local goal>
      required: <true | false>
      depends_on: [<sibling node ids under this same parent>]
      stage_kind: <change | investigation | planning>
      calls:
        - call_id: <stable id, a role name, never a tool name>
          arguments: {<literal> | <"$value_name">}
      execution_checklist:
        - item_id: <stable id>
          description: <what must be handled>
          call_ids: [<call ids in this stage>]
      acceptance_checklist:
        - check_id: <stable id>
          description: <what must be proven>
          operator: <exists|truthy|equals|set_equals|count_equals|within_tolerance|manual|tool_succeeded>
          source_call_id: <call in this stage producing the evidence>
          actual_path: [<output field>]
          expected: <literal> | <"$value_name">
          tolerance: <number> | <"$value_name"> | null

    - node_id: <stable id, unique among its siblings>
      kind: workflow
      purpose: <containment or a phase grouping>
      required: <true | false>
      depends_on: [<sibling node ids under this same parent>]
      children:
        - <nested nodes, either of the two shapes above>
      acceptance_checklist:
        - check_id: <stable id>
          description: <which descendant verdict must hold>
          operator: equals
          source_node: <descendant of this node, relative path, no leading "/">
          expected: <pass | warn | fail | unknown | needs_human>

invariants:
  - <what must remain true across every node>
---

## Prose

The lifecycle in words: when it applies, what it does not cover, how failures are
recovered, and what an Agent must still judge for itself.
```

The front matter keeps a STAGE's fields flat for readability. In the converted
document they live where `templates/workflow.schema.json` puts them: a STAGE's
`stage_kind`, `calls`, `execution_checklist`, and `acceptance_checklist` sit
inside the node's `stage` object, while a WORKFLOW's `children` and
`acceptance_checklist` sit on the node itself. That schema **is** the definition
of the data structure; this template only fixes the lifecycle's part of it.

---

## Conversion rules

The converter applies these, in order. Each one exists because the Workflow
validator rejects the alternative, or because the separation would otherwise be lost.

| Rule | Why it is required |
|---|---|
| `call_id` names a **role**, and the caller binds `{owner, name}` per call id | a guidance document must not name MCP tools; tool names belong to the live server the Agent confirmed |
| A call with no bound target is a **hard error** | `record` refuses a result that does not report the target it ran, so a call left unbound can never collect evidence |
| A call that carries a `target` is a **hard error** | it would put a tool name back into the prompt asset, which the boundary forbids |
| `$name` in `arguments`, `expected`, or `tolerance` is replaced from the supplied values | a template has no numbers |
| A `$name` with no supplied value and no default is a **hard error**, not an empty string | silently emitting a blank would produce a Workflow that opens and then fails its own checks |
| The converted document has exactly one `root` node | a Workflow is a single tree, and the schema requires `root`; every other node is reachable under it |
| `node_id` is unique among its **siblings**; the path is derived by joining ids with `/`, never authored | `node_id` is unique only among siblings, and the path is what identifies a node everywhere else. The schema's `nodeId` pattern forbids `.` and `/` inside an id, so an id can never be confused with a path |
| `call_id`, `item_id`, and `check_id` stay distinct across the converted tree | `record` names a call by `call_id` alone and attributes it to the STAGE that declares it, and `item`/`check` are attributed by a bare id when exactly one node declares it. The validator itself requires uniqueness only inside a STAGE, and the schema forbids `.` and `/` in a `call_id`, so disambiguate with `-` |
| `source_call_id` names a call declared in the **same** STAGE, and every entry of `call_ids` does too | the validator rejects a reference to an undeclared call, and a STAGE check may not read a node |
| `depends_on` holds references walked **from the declaring node** — `../sibling`, `../../branch/node` — never an absolute path, and never the node itself | a reusable subtree does not know where it will be placed, so a sibling can only be named relatively; the validator rejects an absolute reference, one that names nothing, and one written as a bare id (that resolves to the node's own child, which it already waits for). The graph must be acyclic, including cycles closed through the implicit parent-child edge |
| An unreferenced call is a **hard error** | the validator requires every call to support a checklist item |
| A required STAGE with no call, no execution checklist, or no acceptance checklist is a hard error | the validator requires all three on a required leaf |
| A STAGE keeps its acceptance checks inside its stage body; a WORKFLOW keeps them on the node and must not carry a stage body | the validator rejects a STAGE that declares node-level checks and a WORKFLOW that carries a stage body |
| A WORKFLOW check names a `source_node` descendant, uses `equals`, and its `expected` is a **verdict word** | a composite observes exactly one descendant's verdict, and the comparison is applied to that verdict word. `succeeded` is a task status a node never has, so a check written that way can never pass; `tool_succeeded` observes calls a composite does not declare; `count_equals` and `within_tolerance` expect a number or a collection; and a `manual` result is only read for a STAGE, so a composite's `manual` check never resolves. An absolute path would be resolved relatively and mean different nodes at different depths |
| No Step is introduced | there is no Step type. Grouping is a WORKFLOW node, and a phase is just one of those |
| `expected`/`tolerance` that are not supplied stay `null` only for operators that accept it | `within_tolerance` with a null tolerance silently compares against null |

### What the template deliberately does not carry

**No tool names.** A call declares a role (`call-generate-city`) and what it is
for; the caller supplies the `owner`/`name` after confirming the live MCP server.
This keeps one lifecycle usable across hosts and keeps the prompt asset free of
server internals.

**No thresholds.** Every numeric acceptance bound is a `$value` the caller must
supply. In this project two invented thresholds ("3000 distinct colours",
"coplanar ≤ 60") were frozen into a Workflow and passed while the render was still
wrong. A template that pre-filled a number would freeze that mistake permanently.

**No object or host names in the lifecycle.** `guidance_id` names the lifecycle,
not a combination of host and object, because the repository forbids one document
per host/object/operation combination.

---

## Validation of a converted Workflow

Conversion is not "done" when JSON is produced. It is done when the acceptance
loop accepts it:

```powershell
python -m ainative.session --state s.json --task task.json --workflow workflow.json open
```

`open` deserializes the document and runs `validate_tree_structure` plus the entry
gate. The document's shape and format are defined by
`templates/workflow.schema.json`, the spec the author writes against and the one
`reading/schema.py` checks. A template whose output cannot be read, does not match
that spec, or fails structural validation is a broken template.

The rules above are stated so a converter can enforce them without this repository
implementing one. Each rule names the validator behaviour it prevents, because the
failure mode this template exists to stop is a Workflow that opens cleanly and then
fails its own checks.
