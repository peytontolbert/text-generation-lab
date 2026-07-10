import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(script_name: str, module_name: str):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    path = ROOT / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_stage10089_target100m_request_builds():
    mod = _load("build_stage10089_canonical_source_heldout_realistic_shell_target100m_execution_request.py", "stage10089")
    built = mod.build_request()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 95
    assert built["metrics"]["heldout_compare_rows"] == 55
    assert built["metrics"]["l2_rows"] == 95


def test_stage10090_gemma_queue_builds():
    mod = _load("build_stage10090_canonical_source_heldout_realistic_shell_same_manifest_gemma_queue.py", "stage10090")
    built = mod.build_queue()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 55
    assert built["metrics"]["l2_shell_rows"] == 55
    assert built["packet"]["same_surface_packet"]["heldout_compare_rows"] == 55


def test_stage10091_comparison_audit_scaffold_exists_and_is_empty_until_execution():
    mod = _load("build_stage10091_canonical_source_heldout_realistic_shell_same_manifest_comparison_audit.py", "stage10091")
    built = mod.build_audit()
    assert built["passed"] is True
    assert built["metrics"]["execution_ready"] is False
    assert built["metrics"]["comparison_rows"] == 0
