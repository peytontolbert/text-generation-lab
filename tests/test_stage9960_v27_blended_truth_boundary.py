import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9960_v27_blended_truth_boundary.py"
    spec = importlib.util.spec_from_file_location("stage9960_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9960_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_boundary_reports_mixed_blended_result():
    module = _load_module()
    built = module.build_boundary()
    assert built["passed"] is True
    assert built["metrics"]["weighted_frontier_languages_with_narrow_machine_supported_claim"] == 4
    assert built["metrics"]["weighted_scope_confident_languages"] == 3
    assert built["metrics"]["blended_comparison_ready_now"] is True
    assert built["metrics"]["blended_wins_100m"] == 3
    assert built["metrics"]["blended_wins_gemma"] == 3
    assert built["metrics"]["blended_ties"] == 2
    assert built["metrics"]["blended_overall_beats_gemma"] is False
    web = next(row for row in built["language_rows"] if row["language_family"] == "web_js_ts_html")
    assert web["blended_eval_verdict"] == "100m_better"
    assert web["blended_strict_verdict"] == "tie"


def test_main_writes_summary_and_boundary(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "BOUNDARY", tmp_path / "artifacts" / "v27_blended_truth_boundary.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9960_v27_blended_truth_boundary.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "V27_BLENDED_TRUTH_BOUNDARY_STAGE9960.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    boundary = json.loads(module.BOUNDARY.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert boundary["metrics"]["blended_wins_100m"] == 3
    assert boundary["metrics"]["blended_wins_gemma"] == 3
    assert boundary["metrics"]["weighted_scope_confident_languages"] == 3
