from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ainative.orchestration.contracts.results import TaskResult, TaskStatus
from ainative.orchestration.contracts.task import TaskRoute
from ainative.orchestration.contracts.tools import (
    ToolDefinition,
    ToolExecutionKind,
    ToolsetDefinition,
)
from ainative.registry import tool_id_for
from ainative.toolsets.ports.host_executor import HostOperationRequest


@dataclass(frozen=True, slots=True)
class PythonScriptWorkflowSpec:
    """One registered Tool implemented by a JSON-in/JSON-out Python script."""

    operation: str
    script: str | Path
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object"})
    output_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object"})


class PythonScriptWorkflowProvider:
    """Expose reusable Python workflows as ordinary project Tools.

    The script is never a WorkflowPlan call kind. The Registry publishes it as
    a normal Tool; the implementation metadata tells maintainers that the Tool
    is backed by a script.

    Script contract:
      - receive one JSON object on stdin;
      - write one JSON object on stdout;
      - optionally provide ``status``, ``details``, ``warnings``, and ``errors``.
    """

    def __init__(
        self,
        *,
        provider_id: str,
        toolset_id: str,
        host_id: str,
        specs: tuple[PythonScriptWorkflowSpec, ...],
        python_executable: str | Path | None = None,
        timeout: int = 300,
    ) -> None:
        self.provider_id = provider_id
        self.executor_id = provider_id
        self.host_id = host_id
        self.toolset_id = toolset_id
        self.specs = specs
        self.python_executable = str(python_executable or sys.executable)
        self.timeout = timeout
        self._by_operation = {spec.operation: spec for spec in specs}

    def is_ready(self) -> bool:
        return bool(self.specs) and all(Path(spec.script).is_file() for spec in self.specs)

    def toolsets(self) -> tuple[ToolsetDefinition, ...]:
        tools = tuple(
            ToolDefinition(
                tool_id=tool_id_for(self.toolset_id, spec.operation),
                operation=spec.operation,
                execution_kind=ToolExecutionKind.HOST,
                description=spec.description,
                input_schema=dict(spec.input_schema),
                output_schema=dict(spec.output_schema),
                metadata={
                    "implementation": "python_script",
                    "entrypoint": str(Path(spec.script)),
                },
            )
            for spec in self.specs
        )
        return (
            ToolsetDefinition(
                toolset_id=self.toolset_id,
                provider_id=self.provider_id,
                title=f"{self.host_id} Workflow Tools",
                description="Reusable host workflows exposed as project-owned Tools.",
                tools=tools,
                metadata={"provider": "python_script"},
            ),
        )

    def execute(self, request: HostOperationRequest) -> TaskResult:
        spec = self._by_operation.get(request.operation)
        if spec is None:
            return self._result(TaskStatus.BLOCKED, request, errors=(f"Unknown workflow Tool: {request.operation}",))
        payload = json.dumps(request.parameters, ensure_ascii=False, default=str)
        try:
            completed = subprocess.run(
                [self.python_executable, str(spec.script)],
                input=payload,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return self._result(TaskStatus.FAILED, request, errors=(f"workflow script failed to start: {exc}",))
        if completed.returncode != 0:
            return self._result(
                TaskStatus.FAILED,
                request,
                errors=(completed.stderr.strip() or f"workflow script exited with {completed.returncode}",),
            )
        try:
            result = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            return self._result(TaskStatus.FAILED, request, errors=(f"workflow script returned invalid JSON: {exc}",))
        try:
            status = TaskStatus(str(result.get("status", "succeeded")))
        except ValueError:
            status = TaskStatus.FAILED
        return self._result(
            status,
            request,
            details=dict(result.get("details", result.get("outputs", {}))),
            warnings=tuple(result.get("warnings", ())),
            errors=tuple(result.get("errors", ())),
        )

    @staticmethod
    def _result(
        status: TaskStatus,
        request: HostOperationRequest,
        *,
        details: dict[str, Any] | None = None,
        warnings: tuple[str, ...] = (),
        errors: tuple[str, ...] = (),
    ) -> TaskResult:
        return TaskResult(
            status=status,
            route=TaskRoute.HOST_OPERATION.value,
            call_surface=request.call_surface,
            details=details or {},
            warnings=warnings,
            errors=errors,
            resume_pointer=request.operation if status not in {TaskStatus.SUCCEEDED, TaskStatus.DEGRADED} else None,
        )
