import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage10081_canonical_harness_backend_handoff_bundle.py"
    spec = importlib.util.spec_from_file_location("stage10081_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage10081_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_bundle_materializes_four_canonical_backend_handoffs():
    module = _load_module()
    built = module.build_bundle()
    assert built["passed"] is True
    assert built["metrics"]["canonical_handoff_cells"] == 4
    assert built["metrics"]["handoff_bundles_written"] == 4
    assert built["metrics"]["cells_with_canonical_100m_better_proxy"] == 4
    for row in built["handoff_cells"]:
        assert row["handoff_status"] == "ready_for_external_backend_adapter"
        assert row["runtime_contract"]["standalone_proxy_frontier"]["same_surface_comparison_stage"] == 10086


def test_main_writes_summary_and_bundle(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "BUNDLE", tmp_path / "artifacts" / "canonical_harness_backend_handoff_bundle.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage10081_canonical_harness_backend_handoff_bundle.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "CANONICAL_HARNESS_BACKEND_HANDOFF_BUNDLE_STAGE10081.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    bundle = json.loads(module.BUNDLE.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert bundle["metrics"]["canonical_handoff_cells"] == 4
