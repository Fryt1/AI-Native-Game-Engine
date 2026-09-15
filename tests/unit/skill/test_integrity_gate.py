import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "integrity_gate.py"


def load_module():
    spec = spec_from_file_location("integrity_gate", MODULE_PATH)
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_integrity_gate_accepts_the_skill_package():
    module = load_module()
    report = module.check_package(REPO_ROOT)

    assert report.ok is True
    assert report.missing == ()


def test_integrity_gate_reports_every_missing_required_file():
    module = load_module()
    report = module.check_package(REPO_ROOT / "knowledge")

    assert report.ok is False
    assert "SKILL.md" in report.missing
