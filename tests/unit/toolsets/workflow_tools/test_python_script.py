from pathlib import Path

from ainative.orchestration.contracts.results import TaskStatus
from ainative.toolsets.ports.host_executor import HostOperationRequest
from ainative.toolsets.workflow_tools import (
    PythonScriptWorkflowProvider,
    PythonScriptWorkflowSpec,
)


def test_python_script_workflow_is_published_as_a_project_tool(tmp_path: Path):
    script = tmp_path / "workflow.py"
    script.write_text(
        "import json, sys\npayload = json.load(sys.stdin)\nprint(json.dumps({'status': 'succeeded', 'details': {'value': payload['value'] * 2}}))\n",
        encoding="utf-8",
    )
    provider = PythonScriptWorkflowProvider(
        provider_id="blender-workflows",
        toolset_id="blender.workflow",
        host_id="blender",
        specs=(PythonScriptWorkflowSpec("double", script),),
    )

    tool = provider.toolsets()[0].tools[0]
    result = provider.execute(HostOperationRequest("workflow-1", "double", parameters={"value": 3}))

    assert tool.metadata["implementation"] == "python_script"
    assert result.status is TaskStatus.SUCCEEDED
    assert result.details == {"value": 6}

