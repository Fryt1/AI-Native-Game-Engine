# AI Native Game Engine

An Agent-driven WorkflowPlan runtime for UE5, Blender, MCP servers, transfer backends, validators, and reusable ComfyUI/script-backed Tools.

Agent intent is turned into a `TaskContract` and an Agent-authored `WorkflowPlan` by the Agent itself. The runtime never guesses a Route or Tool; it validates the plan, freezes execution/acceptance checklists per Stage, and lets the Agent execute one exact `ToolCall` or `McpCall` at a time. Every Stage completes only when structured checklist evidence proves it, never from a process exit code alone.

## Table of Contents

- [Background](#background)
- [Install](#install)
- [Runtime dependencies](#runtime-dependencies)
- [Blender MCP dependencies](#blender-mcp-dependencies)
- [ComfyUI MCP dependencies](#comfyui-mcp-dependencies)
- [Hugging Face CLI and MCP dependencies](#hugging-face-cli-and-mcp-dependencies)
- [Usage](#usage)
- [Architecture](#architecture)
- [Security](#security)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
- [License](#license)

## Background

Editor work across Unreal Engine 5 and Blender is normally driven by ad-hoc scripts, brittle menus, and manual round-trips. This project provides a repeatable, evidence-backed runtime so an AI agent can plan host edits, transfer assets, run external tools such as ComfyUI, and prove what happened.

The project keeps three firm boundaries:

- The Agent owns intent: the runtime has no built-in prompt router and no keyword-based Workflow picker.
- The Python runtime owns validation and deterministic acceptance, not plan generation or scheduling.
- MCP Tools are not copied into a project Registry; the Agent MCP Client stays the single owner of MCP execution.

## Install

Requires Python 3.11+ on Windows with Unreal Engine 5 and Blender available when host operations are exercised. Install the editable package from the repository root:

```powershell
python -m pip install -e .[dev]
```

Run from the repository root (the directory containing this README). The project is not published on PyPI and has no third-party runtime dependencies; `dev` extras add pytest and ruff.

## Runtime dependencies

This repository is not a self-contained UE/Blender application. It owns the Python runtime,
Workflow definitions, and Project Tools; the host applications and live MCP Servers are
external dependencies.

The supported baselines are Python 3.11+, Blender MCP 5.1.0+ (see [Blender MCP dependencies](#blender-mcp-dependencies)), and UE5 native MCP 5.8.0+.
Blender 5.2.1 LTS and UE5.8.2 are currently validated. ComfyUI MCP is configured and
live-validated locally with a minimal workflow and output read-back.

See [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) for the full Python, Blender, UE5,
ComfyUI, AssetsBridge, Hugging Face, and MCP dependency contract, including
version baselines, install/verification steps, failure triage, and security
boundaries for each host/MCP integration.

## Blender MCP dependencies

Blender MCP is a Blender Add-on (vendored under `vendor/mcp/blender/`), not an engine-internal
server. The supported baseline is Blender 5.1.0+, with Blender 5.2.1 LTS currently validated,
and it listens on the local TCP socket `localhost:9876` once enabled and started.

See [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) (Blender section) before running a Workflow that contains Blender `McpCall` entries.

## ComfyUI MCP dependencies

ComfyUI MCP is an external stdio MCP Server. The configured official `comfy-mcp` process
uses `comfy-cli` to drive the ComfyUI HTTP API; it is not a Project Tool Registry entry and
it is not a ComfyUI-internal plugin. The project baseline is `comfy-cli >=1.14.0`; the
current local verification uses ComfyUI v0.30.2, `comfy-cli 1.18.0`, and `comfy-mcp 0.10.0`.

The default local target is `http://127.0.0.1:8188`. The MCP process handshake and
`tools/list` have passed locally, but ComfyUI must be running before `server_info`, workflow
execution, or output retrieval can succeed.

See [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) (ComfyUI section) before running a Workflow that contains ComfyUI `McpCall` entries.

## Hugging Face CLI and MCP dependencies

Hugging Face is the model-discovery and model-acquisition side of the ComfyUI pipeline.
Use the Hugging Face MCP Server for Hub search and research, and use the local `hf` CLI to
authenticate and download model files into ComfyUI's model directories. The Hugging Face
MCP is not a Project Tool Registry entry and does not replace ComfyUI MCP.

Typical flow:

```text
Hugging Face MCP → find/check model, license, revision, and files
hf CLI          → authenticate and download the selected model
ComfyUI MCP     → discover, validate, and run the workflow
```

See [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) (Hugging Face section) before using a Workflow that needs Hub resources or local model acquisition.

## Usage

### CLI

The Project Tool CLI executes one exact ToolCall through the Project Tool Registry and prints a structured JSON `ExecutionResult`. It never reads or schedules a WorkflowPlan.

```powershell
python -m ainative.tools --config runtime.json --toolset blender.editor --operation set-location --args '{"location":[1,2,3]}'
```

Detailed runtime configuration and CLI semantics live in [docs/cli.md](docs/cli.md).

### Agent-facing API

The Agent supplies a `TaskContract`, loads Workflow guidance, authors an `ExecutionPlan`, and opens a validation session:

```python
from ainative.agent import WorkflowGuide

task = ...          # Agent-authored TaskContract
plan = ...          # Agent-authored ExecutionPlan
runtime = ...       # RuntimeContext with live project executors/backends

guide = WorkflowGuide()
session = guide.start(task, plan, runtime)
```

The Agent executes each Tool/MCP call itself and submits the raw structured result:

```python
session.record_execution_result(execution_result)
stage_result = session.complete_stage("stage.change")
result = session.finish()
```

`WorkflowSession` never invokes a Tool or MCP Server. It validates the submitted result against the plan, records evidence, evaluates each Stage deterministically, and aggregates the final result.

## Architecture

```text
Agent intent
    → TaskContract
    → Route / Workflow guidance
    → layered Stage knowledge
    → Agent-authored WorkflowPlan
       └── each Stage freezes execution + acceptance checklists
    → plan/checklist/Tool feasibility gate
    → Agent calls one ToolCall or McpCall at a time
    → ExecutionResult + Evidence
    → ExecutionItemResult + CheckResult
    → deterministic StageResult
    → continue / retry / wait / compensate / re-plan
```

Workflow documents lock macro invariants, not a universal Step list. The Agent chooses the concrete Steps, Stages, checklist items, and exact calls for the current task.

### Stage closure

```text
execution checklist   prevents omitted preparation or work
acceptance checklist  prevents Tool success from being mistaken for goal completion
```

Checklist results are:

```text
pass | warn | fail | unknown | needs_human
```

Required failures, unknowns, and human decisions block completion. A Stage with only warnings completes as `degraded`; all required items passing completes as `succeeded`.

### Execution paths

```text
ToolCall
    → Project Tool Registry
    → AssetsBridge / Validation / script-backed / ComfyUI Tools

McpCall
    → Agent MCP Client
    → Blender MCP / UE5 MCP / ComfyUI MCP
```

A call can be marked `execute`, `observe`, `verify`, or `report` for audit. This is per-call metadata, not a permanent Tool role. Reusable Workflow Definitions live under `workflows/`.

### Knowledge structure

The Agent composes Stages from layered knowledge rather than fixed recipes:

```text
skills/ai-native-workflow-orchestration/knowledge/
├── stage-kinds/
├── objects/
└── operations/
```

Tool contracts and workflow templates live with the Skill package and the published Workflows.

### Documentation map

- `AGENTS.md` — repository-wide Agent rules
- `skills/ai-native-workflow-orchestration/SKILL.md` — Skill contract
- `skills/ai-native-workflow-orchestration/knowledge/` — layered Stage knowledge
- `skills/ai-native-workflow-orchestration/templates/` — plan templates and schema
- `skills/ai-native-workflow-orchestration/toolsets/` — Toolset contracts
- `docs/FINAL_ARCHITECTURE.md` — final architecture
- `docs/MAINTENANCE.md` — maintenance and extension rules
- `docs/VALIDATION_REPORT.md` — current verification evidence
- `docs/cli.md` — Project Tool CLI usage
- `docs/DEPENDENCIES.md` — Python、Blender、UE5、ComfyUI、AssetsBridge、MCP 和外部工具依赖总览
- `workflows/` — published reusable Workflow Definitions

## Security

The runtime does not store credentials and requires no API keys. Blender/UE5 command execution is limited to exact project ToolCalls that the Agent selected and the registry resolved. Host paths and `RuntimeContext` come from local configuration you control; do not commit runtime configuration containing machine-specific paths or secrets.

Treat host result files as untrusted: the runtime deletes stale result files before execution, requires request/transfer identity, and rejects malformed or stale JSON with a structured failure. MCP execution remains the responsibility of the configured Agent MCP Client.

## Maintainers

- [Fry](https://github.com/Fryt1) — project maintainer; contact via GitHub issues on [AI-Native-Game-Engine](https://github.com/Fryt1/AI-Native-Game-Engine).

## Contributing

Issues and pull requests are welcome on the GitHub repository. Before changing behavior, read `AGENTS.md` and `docs/MAINTENANCE.md` for the ownership and directory rules. Keep every behavior change paired with tests and update the relevant Skill/Toolset documentation at the same time.

There is no separate `CONTRIBUTING.md` or `CODE_OF_CONDUCT.md` yet; this section is the contribution guide for now.

## License

MIT © [Fry](https://github.com/Fryt1). See [LICENSE](LICENSE).

