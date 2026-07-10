import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9931_weighted_harness_backend_handoff_bundle.py"
    spec = importlib.util.spec_from_file_location("stage9931_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9931_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_bundle_materializes_four_backend_handoffs():
    module = _load_module()
    built = module.build_bundle()
    assert built["passed"] is True
    assert built["metrics"]["weighted_handoff_cells"] == 4
    assert built["metrics"]["handoff_bundles_written"] == 4
    for row in built["handoff_cells"]:
        assert row["handoff_status"] == "ready_for_external_backend_adapter"
        assert "metadata_and_threshold_contracts" in row["why_external_backend_is_required"][0]
        assert row["runtime_contract"]["runner_mode"] == "dry_run_contract_only"


def test_main_writes_summary_and_bundle(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "BUNDLE", tmp_path / "artifacts" / "weighted_harness_backend_handoff_bundle.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9931_weighted_harness_backend_handoff_bundle.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "WEIGHTED_HARNESS_BACKEND_HANDOFF_BUNDLE_STAGE9931.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    bundle = json.loads(module.BUNDLE.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert bundle["metrics"]["weighted_handoff_cells"] == 4
