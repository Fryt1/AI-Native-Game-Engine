"""Every enum field must accept its plain string value.

`reading/deserialize.py` normalizes enums on the JSON path, so a Workflow or a
submitted result that arrives as JSON always works. But the same objects are also
built directly, in tests and by any Python caller, and there `to_dict()` reaches
`self.field.value` and raises `AttributeError: 'str' object has no attribute
'value'`.

This test constructs one instance of every dataclass that has an enum field,
passing the plain string, and asserts the field came back as the enum member.
"""

import dataclasses
import enum
import inspect
import typing

import pytest

import ainative.model as m

MODULES = [m.artifacts, m.checklists, m.tools, m.tree, m.results, m.task]

# A minimal valid constructor per class, so a string can be passed for one field.
CTORS = {
    "ArtifactRef": lambda **kw: m.ArtifactRef(artifact_id="a", uri="file:///a", **kw),
    "ExecutionChecklistItem": lambda **kw: m.ExecutionChecklistItem(item_id="i", description="d", **kw),
    "AcceptanceCheck": lambda **kw: m.AcceptanceCheck(check_id="k", description="d", **kw),
    "ExecutionItemResult": lambda **kw: m.ExecutionItemResult(item_id="i", **kw),
    "CheckResult": lambda **kw: m.CheckResult(check_id="k", **kw),
    "ToolCall": lambda **kw: m.ToolCall(call_id="c", target=m.CallTarget("o", "n"), **kw),
    "ExecutionResult": lambda **kw: m.ExecutionResult(call_id="c", **kw),
    "StageResult": lambda **kw: m.StageResult(node_path="/s/", **kw),
    "TaskResult": lambda **kw: m.TaskResult(route="host_operation", **kw),
    "StageBody": lambda **kw: m.StageBody(**kw),
    "WorkflowNode": lambda **kw: m.WorkflowNode(node_id="n", purpose="p", **kw),
    "WorkflowTree": lambda **kw: m.WorkflowTree(
        workflow_id="w",
        root=m.WorkflowNode(node_id="root", purpose="p", kind="workflow"),
        **{"route": "host_operation", **kw},
    ),
    "TaskContract": lambda **kw: m.TaskContract(
        task_id="t", objective="o", **{"route": "host_operation", **kw}
    ),
}

# One valid string value per enum.
ENUM_VALUES = {
    "ArtifactKind": "unknown",
    "CheckStatus": "pass",
    "CheckOperator": "exists",
    "NodeKind": "stage",
    "StageKind": "change",
    "TaskRoute": "host_operation",
    "TaskStatus": "succeeded",
    "WorkflowStatus": "draft",
}


def _enum_name(cls, field) -> str | None:
    """Resolve a field's enum name, whether the annotation is a string or a type.

    Every model module uses `from __future__ import annotations`, so `field.type`
    is the annotation *source text*, not the resolved type.
    """

    hints = typing.get_type_hints(cls)
    resolved = hints.get(field.name, field.type)
    name = getattr(resolved, "__name__", None)
    if name in ENUM_VALUES:
        return name
    # fall back to the raw text for the `X | None` cases, dropping the alternative
    text = str(field.type).split(".")[-1].strip("'\"").split("|")[0].strip()
    return text if text in ENUM_VALUES else None


def enum_fields():
    """Yield (class_name, field_name, enum_name) for every enum field in the model."""

    seen = set()
    for mod in MODULES:
        for name, obj in vars(mod).items():
            if not (inspect.isclass(obj) and dataclasses.is_dataclass(obj)):
                continue
            if name not in CTORS or (name, obj) in seen:
                continue
            seen.add((name, obj))
            for f in dataclasses.fields(obj):
                enum_name = _enum_name(obj, f)
                if enum_name:
                    yield name, f.name, enum_name


FIELDS = sorted(enum_fields())

# Guard: if the model grows an enum field, this list must grow too.
EXPECTED = {
    ("AcceptanceCheck", "operator"),
    ("ArtifactRef", "kind"),
    ("CheckResult", "status"),
    ("ExecutionItemResult", "status"),
    ("ExecutionResult", "status"),
    ("StageBody", "stage_kind"),
    ("StageResult", "status"),
    ("TaskContract", "route"),
    ("TaskResult", "status"),
    ("WorkflowNode", "kind"),
    ("WorkflowTree", "route"),
    ("WorkflowTree", "status"),
}


def test_every_enum_field_is_covered():
    """A new enum field must be added here, so it cannot go untested."""

    assert {(cls, field) for cls, field, _ in FIELDS} == EXPECTED


@pytest.mark.parametrize(("cls", "field", "enum_name"), FIELDS)
def test_enum_field_accepts_a_plain_string(cls, field, enum_name):
    instance = CTORS[cls](**{field: ENUM_VALUES[enum_name]})

    value = getattr(instance, field)

    assert isinstance(value, enum.Enum), f"{cls}.{field} did not coerce {ENUM_VALUES[enum_name]!r}"
    assert value.value == ENUM_VALUES[enum_name]


@pytest.mark.parametrize(("cls", "field", "enum_name"), FIELDS)
def test_enum_field_rejects_an_unknown_value(cls, field, enum_name):
    """Coercion must reject, never guess."""

    with pytest.raises(ValueError):
        CTORS[cls](**{field: "definitely-not-a-value"})
