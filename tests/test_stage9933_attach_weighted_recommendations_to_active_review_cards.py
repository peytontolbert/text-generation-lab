import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9933_attach_weighted_recommendations_to_active_review_cards.py"
    spec = importlib.util.spec_from_file_location("stage9933_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9933_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_refresh_enriches_four_active_winner_cards():
    module = _load_module()
    built = module.build_refresh()
    assert built["passed"] is True
    assert built["metrics"]["winner_cells_enriched"] == 4
    assert built["metrics"]["rubric_cards_with_recommendations"] == 4
    assert built["metrics"]["anti_cheat_cards_with_recommendations"] == 4


def test_main_writes_summary_and_manifest(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "MANIFEST", tmp_path / "artifacts" / "attach_weighted_recommendations_to_active_review_cards.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9933_attach_weighted_recommendations_to_active_review_cards.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "ATTACH_WEIGHTED_RECOMMENDATIONS_TO_ACTIVE_REVIEW_CARDS_STAGE9933.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    manifest = json.loads(module.MANIFEST.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert manifest["metrics"]["winner_cells_enriched"] == 4
