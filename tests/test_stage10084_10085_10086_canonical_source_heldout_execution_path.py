import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(script_name: str, module_name: str):
    path = ROOT / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_stage10084_target100m_request_builds():
    mod = _load("build_stage10084_canonical_label_aligned_source_heldout_target100m_execution_request.py", "stage10084")
    built = mod.build_request()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 95
    assert built["metrics"]["heldout_compare_rows"] == 55


def test_stage10085_gemma_queue_builds():
    mod = _load("build_stage10085_canonical_label_aligned_source_heldout_same_manifest_gemma_queue.py", "stage10085")
    built = mod.build_queue()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 55
    assert built["packet"]["same_surface_packet"]["heldout_compare_rows"] == 55


def test_stage10086_comparison_audit_scaffold_exists_and_is_empty_until_execution():
    mod = _load("build_stage10086_canonical_label_aligned_source_heldout_same_manifest_comparison_audit.py", "stage10086")
    built = mod.build_audit()
    assert built["passed"] is True
    assert built["metrics"]["execution_ready"] is False
    assert built["metrics"]["comparison_rows"] == 0
