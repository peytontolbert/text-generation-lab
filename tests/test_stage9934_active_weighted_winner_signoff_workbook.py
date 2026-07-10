import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9934_active_weighted_winner_signoff_workbook.py"
    spec = importlib.util.spec_from_file_location("stage9934_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9934_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_workbook_materializes_eight_live_signoff_tasks():
    module = _load_module()
    built = module.build_workbook()
    assert built["passed"] is True
    assert built["metrics"]["signoff_tasks"] == 8
    assert built["metrics"]["unique_cells"] == 4
    assert built["metrics"]["tasks_with_recommendation_source"] == 8


def test_main_writes_summary_and_workbook(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "WORKBOOK", tmp_path / "artifacts" / "active_weighted_winner_signoff_workbook.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9934_active_weighted_winner_signoff_workbook.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "ACTIVE_WEIGHTED_WINNER_SIGNOFF_WORKBOOK_STAGE9934.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    workbook = json.loads(module.WORKBOOK.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert workbook["metrics"]["signoff_tasks"] == 8
