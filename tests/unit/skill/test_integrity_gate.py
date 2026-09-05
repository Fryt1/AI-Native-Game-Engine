import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).parents[3] / "skills" / "ai-native-workflow-orchestration" / "scripts" / "integrity_gate.py"


def load_module():
    spec = spec_from_file_location("integrity_gate", MODULE_PATH)
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_integrity_gate_accepts_the_skill_package():
    module = load_module()
    report = module.check_package(MODULE_PATH.parents[1])

    assert report.ok is True
    assert report.missing == ()


def test_workflow_plan_template_and_schema_are_valid_json():
    template_root = MODULE_PATH.parents[1] / "templates"
    template = json.loads((template_root / "workflow-plan-template.json").read_text(encoding="utf-8"))
    schema = json.loads((template_root / "workflow-plan-schema.json").read_text(encoding="utf-8"))

    assert template["workflow"]["steps"][0]["stages"][0]["execution_checklist"]
    assert template["workflow"]["steps"][0]["stages"][0]["acceptance_checklist"]
    assert schema["$defs"]["stage"]["properties"]["stage_kind"]["enum"] == [
        "change",
        "investigation",
        "planning",
    ]
