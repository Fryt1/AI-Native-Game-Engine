import pytest

from ainative.orchestration.contracts import (
    ToolCall,
    ToolDefinition,
    ToolExecutionKind,
    ToolsetDefinition,
)
from ainative.registry import (
    ToolResolutionError,
    ToolsetRegistry,
    toolset_from_operations,
)


class FakeToolOwner:
    def is_ready(self):
        return True

    def toolsets(self):
        return (
            ToolsetDefinition(
                toolset_id="ue5.editor",
                provider_id="ue5",
                title="UE5 Editor",
                description="UE5 editor tools",
                tools=(
                    ToolDefinition(
                        tool_id="ue5.editor.set_actor_transform",
                        operation="set_actor_transform",
                        execution_kind=ToolExecutionKind.HOST,
                        description="Set an Actor transform",
                        input_schema={"type": "object"},
                        output_schema={"type": "object"},
                    ),
                    ToolDefinition(
                        tool_id="ue5.editor.save_level",
                        operation="save_level",
                        execution_kind=ToolExecutionKind.HOST,
                        description="Save the current Level",
                    ),
                ),
            ),
        )


def test_registry_queries_toolset_before_tools_and_resolves_exact_call():
    owner = FakeToolOwner()
    registry = ToolsetRegistry({"ue5": owner})

    assert [toolset.toolset_id for toolset in registry.search_toolsets("UE5 Editor")] == ["ue5.editor"]
    assert [tool.tool_id for tool in registry.search_tools("ue5.editor", "actor transform")] == [
        "ue5.editor.set_actor_transform"
    ]
    assert registry.describe_tool("ue5.editor", "ue5.editor.save_level").operation == "save_level"

    resolved = registry.resolve_call(
        ToolCall(
            call_id="set-1",
            toolset_id="ue5.editor",
            tool_id="ue5.editor.set_actor_transform",
        )
    )
    assert resolved.provider is owner
    assert resolved.tool.tool_id == "ue5.editor.set_actor_transform"


def test_registry_re_resolves_selected_tool_from_live_owner_state():
    class MutableOwner:
        operation = "inspect"

        def is_ready(self):
            return True

        def toolsets(self):
            return (
                ToolsetDefinition(
                    toolset_id="ue5.editor",
                    provider_id="ue5",
                    tools=(
                        ToolDefinition(
                            tool_id=f"ue5.editor.{self.operation}",
                            operation=self.operation,
                            execution_kind=ToolExecutionKind.HOST,
                        ),
                    ),
                ),
            )

    owner = MutableOwner()
    registry = ToolsetRegistry({"ue5": owner})
    owner.operation = "save_level"

    resolved = registry.resolve_call(
        ToolCall(
            call_id="save-1",
            toolset_id="ue5.editor",
            tool_id="ue5.editor.save_level",
        )
    )
    assert resolved.tool.operation == "save_level"


def test_toolset_factory_deduplicates_dashed_operation_aliases():
    toolset = toolset_from_operations(
        toolset_id="ue5.editor",
        provider_id="ue5",
        execution_kind=ToolExecutionKind.HOST,
        operations=("set_actor_transform", "set-actor-transform"),
    )

    assert [tool.tool_id for tool in toolset.tools] == ["ue5.editor.set_actor_transform"]
    assert toolset.tools[0].operation == "set_actor_transform"


def test_registry_matches_dashed_operation_in_selected_call():
    class Owner:
        host_id = "ue5"

        def is_ready(self):
            return True

        def toolsets(self):
            return (
                toolset_from_operations(
                    toolset_id="ue5.editor",
                    provider_id="ue5",
                    execution_kind=ToolExecutionKind.HOST,
                    operations=("set_actor_transform", "set-actor-transform"),
                ),
            )

    resolved = ToolsetRegistry({"ue5": Owner()}).resolve_call(
        ToolCall(
            call_id="set-1",
            toolset_id="ue5.editor",
            tool_id="ue5.editor.set_actor_transform",
        )
    )

    assert resolved.tool.operation == "set_actor_transform"


def test_registry_rejects_missing_required_tool_arguments_before_execution():
    class Owner:
        def is_ready(self):
            return True

        def toolsets(self):
            return (
                toolset_from_operations(
                    toolset_id="blender.editor",
                    provider_id="blender",
                    execution_kind=ToolExecutionKind.HOST,
                    operations=("set-location",),
                    input_schemas={
                        "set-location": {
                            "type": "object",
                            "required": ["location"],
                            "properties": {"location": {"type": "array", "minItems": 3, "maxItems": 3}},
                        }
                    },
                ),
            )

    with pytest.raises(ToolResolutionError, match="location is required"):
        ToolsetRegistry({"blender": Owner()}).resolve_call(
            ToolCall(
                call_id="missing-location",
                toolset_id="blender.editor",
                tool_id="blender.editor.set_location",
            )
        )



def test_registry_validates_recorded_tool_output_against_declared_schema():
    class Owner:
        def is_ready(self):
            return True

        def toolsets(self):
            return (
                toolset_from_operations(
                    toolset_id="validator",
                    provider_id="validator",
                    execution_kind=ToolExecutionKind.VALIDATOR,
                    operations=("check",),
                    output_schemas={
                        "check": {
                            "type": "object",
                            "required": ["valid"],
                            "properties": {"valid": {"type": "boolean"}},
                        }
                    },
                ),
            )

    registry = ToolsetRegistry({"validator": Owner()})
    call = ToolCall(call_id="check", toolset_id="validator", tool_id="validator.check")

    with pytest.raises(ToolResolutionError, match="valid is required"):
        registry.validate_output(call, {})
