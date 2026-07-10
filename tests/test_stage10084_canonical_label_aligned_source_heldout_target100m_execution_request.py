import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage10084_canonical_label_aligned_source_heldout_target100m_execution_request.py"
    spec = importlib.util.spec_from_file_location("stage10084_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage10084_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_request_materializes_canonical_source_heldout_target100m_request():
    module = _load_module()
    built = module.build_request()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 95
    assert built["metrics"]["heldout_compare_rows"] == 55
    request = built["surface_requests"][0]
    assert request["run_id"] == "stage10084_canonical_label_aligned_source_heldout_target100m_probe"
    assert request["required_contract_invariants"]["source_stage10083_passed"] is True


def test_main_writes_summary_and_request(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "REQUEST", tmp_path / "artifacts" / "canonical_label_aligned_source_heldout_target100m_execution_request.json")
    monkeypatch.setattr(module, "SURFACE_REQUEST", tmp_path / "artifacts" / "surface_requests" / "edit_localization.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage10084_canonical_label_aligned_source_heldout_target100m_execution_request.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "CANONICAL_LABEL_ALIGNED_SOURCE_HELDOUT_TARGET100M_EXECUTION_REQUEST_STAGE10084.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    request = json.loads(module.REQUEST.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert request["metrics"]["heldout_compare_rows"] == 55
