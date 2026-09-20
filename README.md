# AI Native Game Engine

Agent-driven Stage composition and evidence-backed acceptance for UE5, Blender, and ComfyUI.

An Agent composes each node from the Stage kind, the processing object, the operation type, and the current facts, decides what to run, and calls real capabilities one at a time — every host software call goes through its own MCP server. The runtime never picks a call for the Agent. A node completes only when structured checklist evidence proves it, never from a process exit code alone.

## Table of Contents

- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [Architecture](#architecture)
- [Security](#security)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
- [License](#license)

## Background

Editor work across Unreal Engine 5 and Blender is normally driven by ad-hoc scripts, brittle menus, and manual round-trips. This project provides a repeatable, evidence-backed runtime so an AI agent can plan host edits, transfer assets, run external tools such as ComfyUI, and prove what happened.

The project keeps three firm boundaries:

- The Agent owns intent and every decision about what runs next.
- The Python runtime owns structural validation and deterministic acceptance, not Workflow generation or scheduling.
- Host editors stay outside this repository: Blender and UE5 are reached through their own MCP servers, so no host executable path, editor subprocess, or host plugin lives here.

## Install

Requires Python 3.11+ on Windows. Blender, UE5, and ComfyUI are required only when their MCP servers are used; none of them is installed or launched by this repository. Install the editable package from the repository root:

```powershell
python -m pip install -e .[dev]
```

The project is not published on PyPI and has no third-party runtime dependencies; `dev` extras add pytest and ruff.

### Install as a skill

The project **is** a skill: `SKILL.md` carries the frontmatter a harness discovers, and everything else in the repository is what that skill needs. An agent finds it only when it sits under a scanned skill root — `~/.agents/skills/`, `~/.dsh/skills/`, or the same path inside a project. Sitting in a checkout is not enough; discovery reads one level deep, `<root>/<name>/SKILL.md`, so a repository anywhere else is invisible.

Two scripts, one per direction:

```powershell
# From a checkout onto this machine
python install_skill.py
#   installed ai-native-game-engine -> <skill root>/ai-native-game-engine

# Confirm the install still matches the checkout
python install_skill.py --check
```

**Do not then install the engine from the copy.** An editable install points at one
source tree, and reinstalling it from a copy aims your working checkout's engine at a
snapshot — after which edits in the checkout stop taking effect. If the engine
already answers `python -m ainative.session --help`, it is installed and needs
nothing. A machine that has only the skill has no repository to install from, and
that is the one case where the copy is the source:

```powershell
pip install -e "<skill root>/ai-native-game-engine"
```

```powershell
# Into one file, to hand to someone else
python pack_skill.py
#   packed ai-native-game-engine at a1b2c3d
#   dist/ai-native-game-engine-a1b2c3d.zip

# Confirm an archive is usable before trusting it
python pack_skill.py --verify dist/ai-native-game-engine-a1b2c3d.zip
#   ai-native-game-engine-a1b2c3d.zip: 63 files, a usable skill
```

`--check` and `--verify` exist because both failures are otherwise invisible. An installed copy drifts silently and then serves stale instructions; an archive missing the engine loads, appears in the catalog, and fails only when an agent runs the command its body names.

The archive unpacks into a skill root directly — its single top-level directory is already the `<name>/` discovery expects:

```powershell
python -c "import zipfile; zipfile.ZipFile('dist/ai-native-game-engine-a1b2c3d.zip').extractall('<skill root>')"
```

Both scripts take their file list from one place, so what is packed is what is installed. `tests/` and build output are excluded: they belong to the source rather than the skill.

### Dependencies

Runtime dependencies are external and version-baselined. See [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) for the full Python, Blender, UE5, ComfyUI, Hugging Face, and MCP dependency contract, including version baselines, install/verification steps, failure triage, and security boundaries for each host/MCP integration.

Supported baselines:

```text
Python          3.11+
Blender MCP     5.1.0+  (5.2.1 LTS validated; add-on listens on localhost:9876)
UE5 MCP         5.8.0+  (5.8.2 validated)
comfy-cli       1.14.0+ (1.18.0 validated; default target http://127.0.0.1:8188)
```

Hugging Face is the model-discovery and model-acquisition side of the ComfyUI pipeline: use the Hugging Face MCP Server for Hub search, and the local `hf` CLI to authenticate and download model files into ComfyUI model directories.

```text
Hugging Face MCP → find/check model, license, revision, and files
hf CLI          → authenticate and download the selected model
ComfyUI MCP     → discover, validate, and run the workflow
```

## Usage

### CLI

One command surface exists: `python -m ainative.session` is where the Agent hands its own Workflow and its own reported results to Python and gets a deterministic node verdict. Python validates the Workflow structure, stores the submitted evidence in the `--state` file, and evaluates each node against its frozen checklists, bottom-up, so a composite's verdict is earned on its children's. It never picks a call, orders a node, or invents a checklist item.

A Workflow is a tree of nodes: a `STAGE` leaf holds the calls and both frozen checklists, a `WORKFLOW` node holds children and checks that read a descendant's verdict. A node's identity is its **path** (`/step-1/validate-asset/`), because `node_id` is unique only among siblings — so `--stage` takes a path, and the path may address a leaf or a composite.

```powershell
python -m ainative.session --state s.json --task task.json --workflow workflow.json open
python -m ainative.session --state s.json --result executed-call.json record
python -m ainative.session --state s.json --stage /step-1/validate-asset/ stage
python -m ainative.session --state s.json finish
python -m ainative.session --state s.json status
```

Commands:

```text
open       validate an Agent-authored Workflow and start a session
record     submit one executed call result as evidence (--result)
item       submit one execution checklist item result (--result)
check      submit one manual acceptance check result (--result)
stage      evaluate one node by path and close it (--stage)
finish     aggregate the final TaskResult
status     show current session state without changing it
supersede  replace the Workflow revision, archiving the old one and its evidence
```

Every command prints the same envelope — `command`, `ok`, `verdict`, `exit_code`, `detail`, `errors` — and exits 0 on a non-blocking result, 1 on a blocking or failing result, and 2 when the command itself could not run. The Workflow, the task, and every submitted result live in the `--state` file, so later commands need only `--state` plus their own argument. The Agent keeps executing every MCP call itself; this CLI only carries the Workflow in and the verdict out. `--stage` takes a node path; `item` and `check` also accept it, to name the node when a bare item or check id is declared by more than one node.

There is no host-editor configuration: Blender and UE5 are reached through their own MCP servers by the Agent. Detailed CLI semantics live in [docs/cli.md](docs/cli.md).

### Agent-facing API

The Agent supplies a `TaskContract`, loads Workflow guidance, authors a `WorkflowTree`, and opens a validation session:

```python
from ainative.session_api import AcceptanceGuide

task = ...          # Agent-authored TaskContract
workflow = ...      # Agent-authored WorkflowTree

guide = AcceptanceGuide()
session = guide.start(task, workflow)
```

The Agent executes each MCP call itself and submits the raw structured result:

```python
session.record_execution_result(execution_result)
node_result = session.complete_node("/step-1/validate-asset/")
result = session.finish()
```

`AcceptanceSession` never invokes an MCP Server. It validates the submitted result against the Workflow, records evidence, evaluates each node deterministically (a `StageResult` carries the `node_path` it closed), and aggregates the final result.

The same loop is available process-level as `python -m ainative.session`, which reads an Agent-authored Workflow from JSON and reports a verdict per node — see the [CLI](#cli) section. Either way, a call returning `succeeded` does not complete a node: an acceptance check reads `ExecutionResult.evidence_view()`, so a check can address first-class evidence (`status`, `target`, `preserved_relations`, `lost_relations`, `artifact_count`, `artifacts`, `warnings`, `errors`) as well as any key in `outputs`. The node completes only when its frozen acceptance checks pass.

### Adding a reusable workflow

See [docs/ADDING_GUIDANCE.md](docs/ADDING_GUIDANCE.md) for the step-by-step guide to adding a reusable lifecycle under `guidance/`. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the architecture walkthrough.

## Architecture

```text
Agent intent
    → TaskContract
    → Agent composes each node from Stage kind, object, operation, current facts
    → Agent decides what to run
       └── a STAGE leaf freezes execution + acceptance checklists
           a WORKFLOW node groups nodes and reads a descendant's verdict
    → structural Workflow validation
    → Agent calls one MCP tool at a time
    → ExecutionResult + Evidence
    → Agent submits the Workflow and the results to Python
       └── ExecutionItemResult + CheckResult
    → deterministic NodeResult per node, bottom-up
    → StageResult for the node closed
    → continue / retry / wait / compensate / re-plan
```

Guidance documents lock macro invariants, not a universal sequence of nodes. The Agent chooses the concrete tree, checklist items, and exact calls for the current task.

### Stage closure

```text
execution checklist   prevents omitted preparation or work
acceptance checklist  prevents Tool success from being mistaken for goal completion
```

Checklist results use the **node** verdict vocabulary:

```text
pass | warn | fail | unknown | needs_human
```

Required failures, unknowns, and human decisions block completion. A STAGE with only warnings completes as `degraded`; all required items passing completes as `succeeded`. A `WORKFLOW` node completes when every required child completed and its own checks pass, and an unresolved required descendant makes every ancestor `unknown` rather than `failed`.

A task, by contrast, has a **status**: `succeeded`, `degraded`, `blocked`, `failed`, or `needs_approval`. The CLI envelope's `verdict` field uses that task vocabulary, with each node verdict mapped onto it.

### Execution paths

```text
Call
    → target: owner/name (MCP server + tool)
    → Agent MCP Client
    → Blender MCP / UE5 MCP / ComfyUI MCP
```

Author a Workflow against `templates/workflow.schema.json`, which defines the data
structure: every node kind, every field, every operator.

A call like `{"call_id": "m1", "target": {"owner": "ue5", "name": "set_actor_transform"}}` is a first-class entry in the Workflow's call graph. There is no execution binding, no provider list, and no per-run provider check: the Workflow is validated structurally, and the Agent's own MCP client resolves and runs every call. This repository owns no transfer Tool — moving an asset between hosts means the Agent calls the source host's MCP export, performs its own file operation, and calls the target host's MCP import. Host dependencies are declared in `docs/DEPENDENCIES.md`.

### Stage composition

The Agent composes every Stage itself from Stage kind, processing object, operation type, current facts, and the user's requirements:

```text
SKILL.md          the composition rule and the execution discipline
guidance/         reusable macro lifecycle guidance
templates/        the Workflow schema and the result contract
```

There is no per-object or per-operation knowledge base and no recipe package in this repository. The Agent supplies the domain competence for the object and the operation; the repository supplies the contract, the guidance, and the deterministic acceptance engine.

### Documentation map

- `AGENTS.md` — repository-wide Agent rules
- `SKILL.md` — the skill's body: when to use it, and the working order
- `guidance/` — reusable macro lifecycle guidance
- `templates/` — the Workflow schema and the result contract
- `docs/ARCHITECTURE.md` — architecture and data flow
- `docs/ADDING_GUIDANCE.md` — step-by-step guide to add a reusable lifecycle
- `docs/MAINTENANCE.md` — maintenance and extension rules
- `docs/VALIDATION_REPORT.md` — current verification evidence
- `docs/cli.md` — `python -m ainative.session` usage
- `docs/DEPENDENCIES.md` — dependency contract overview
- `install_skill.py` — install this project into a skill root, or check it
- `pack_skill.py` — pack the skill into a distributable archive, or verify one

## Security

The runtime does not store credentials and requires no API keys. This repository executes nothing itself; every host and MCP call is performed by the host's own MCP server under the Agent's MCP client. Runtime configuration is local to your machine; do not commit configuration containing machine-specific paths or secrets.

Treat host result files as untrusted: the runtime validates request and transfer identity and rejects malformed or stale JSON with a structured failure. MCP execution remains the responsibility of the configured Agent MCP client.

## Maintainers

- [Fry](https://github.com/Fryt1) — project maintainer; contact via GitHub issues on [AI-Native-Game-Engine](https://github.com/Fryt1/AI-Native-Game-Engine).

## Contributing

Issues and pull requests are welcome on the GitHub repository. Before changing behavior, read `AGENTS.md` and `docs/MAINTENANCE.md` for the ownership and directory rules. Keep every behavior change paired with tests and update the relevant Skill documentation at the same time.

There is no separate `CONTRIBUTING.md` or `CODE_OF_CONDUCT.md` yet; this section is the contribution guide for now.

## License

MIT © [Fry](https://github.com/Fryt1). See [LICENSE](LICENSE).
