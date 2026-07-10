import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9942_weighted_winner_claim_readiness_matrix_refresh.py"
    spec = importlib.util.spec_from_file_location("stage9942_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9942_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_matrix_reports_stronger_review_packets_after_attachment():
    module = _load_module()
    built = module.build_matrix()
    assert built["passed"] is True
    assert built["metrics"]["languages_with_narrow_machine_supported_claim"] == 4
    assert built["metrics"]["languages_with_stronger_review_packets"] == 4
    assert built["metrics"]["languages_with_full_human_signoff"] == 0
    assert built["metrics"]["languages_broader_v27_claim_ready"] == 0
    assert built["metrics"]["weakest_language_family"] == "web_js_ts_html"


def test_main_writes_summary_and_matrix(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "MATRIX", tmp_path / "artifacts" / "weighted_winner_claim_readiness_matrix_refresh.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9942_weighted_winner_claim_readiness_matrix_refresh.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "WEIGHTED_WINNER_CLAIM_READINESS_MATRIX_REFRESH_STAGE9942.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    matrix = json.loads(module.MATRIX.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert matrix["metrics"]["languages_with_stronger_review_packets"] == 4
