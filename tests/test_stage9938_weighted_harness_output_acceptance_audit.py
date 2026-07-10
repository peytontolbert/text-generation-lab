import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9938_weighted_harness_output_acceptance_audit.py"
    spec = importlib.util.spec_from_file_location("stage9938_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9938_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_audit_reports_stub_only_current_state():
    module = _load_module()
    built = module.build_audit()
    assert built["passed"] is True
    assert built["metrics"]["weighted_cells"] == 4
    assert built["metrics"]["cells_acceptance_ready"] == 0
    assert built["metrics"]["cells_still_stub_only"] == 4


def test_main_writes_summary_and_audit(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "AUDIT", tmp_path / "artifacts" / "weighted_harness_output_acceptance_audit.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9938_weighted_harness_output_acceptance_audit.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "WEIGHTED_HARNESS_OUTPUT_ACCEPTANCE_AUDIT_STAGE9938.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    audit = json.loads(module.AUDIT.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert audit["metrics"]["cells_still_stub_only"] == 4
