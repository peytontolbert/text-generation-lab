import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9943_web_weighted_edit_localization_failure_atlas.py"
    spec = importlib.util.spec_from_file_location("stage9943_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9943_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_atlas_reports_web_failure_pattern():
    module = _load_module()
    built = module.build_atlas()
    assert built["passed"] is True
    assert built["metrics"]["web_rows_total"] == 8
    assert built["metrics"]["web_correct_100m"] == 2
    assert built["metrics"]["web_correct_gemma"] == 0
    assert "test_surface" in built["metrics"]["surface_types_with_zero_100m_hits"]
    assert "symbol_definition_or_implementation_surface" in built["metrics"]["surface_types_with_nonzero_100m_hits"]


def test_main_writes_summary_and_atlas(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "ATLAS", tmp_path / "artifacts" / "web_weighted_edit_localization_failure_atlas.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9943_web_weighted_edit_localization_failure_atlas.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "WEB_WEIGHTED_EDIT_LOCALIZATION_FAILURE_ATLAS_STAGE9943.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    atlas = json.loads(module.ATLAS.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert atlas["metrics"]["web_rows_total"] == 8
