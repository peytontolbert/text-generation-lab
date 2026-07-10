import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9930_weighted_harness_execution_requests.py"
    spec = importlib.util.spec_from_file_location("stage9930_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9930_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_requests_materializes_four_weighted_backend_requests():
    module = _load_module()
    built = module.build_requests()
    assert built["passed"] is True
    assert built["metrics"]["weighted_requests"] == 4
    assert built["metrics"]["request_files_written"] == 4
    assert built["metrics"]["cells_ready_for_backend_adapter"] == 4
    for row in built["requests"]:
        assert row["request_status"] == "awaiting_real_harness_backend_adapter"
        assert row["mode"] == "full_product_harness"
        assert row["skill_area"] == "edit_localization"


def test_main_writes_summary_and_requests(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "REQUESTS", tmp_path / "artifacts" / "weighted_harness_execution_requests.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9930_weighted_harness_execution_requests.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "WEIGHTED_HARNESS_EXECUTION_REQUESTS_STAGE9930.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    requests = json.loads(module.REQUESTS.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert requests["metrics"]["weighted_requests"] == 4
