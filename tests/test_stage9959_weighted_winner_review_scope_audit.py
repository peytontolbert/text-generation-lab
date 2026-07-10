import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9959_weighted_winner_review_scope_audit.py"
    spec = importlib.util.spec_from_file_location("stage9959_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9959_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_audit_reports_scope_partition_and_web_fragility():
    module = _load_module()
    built = module.build_audit()
    assert built["passed"] is True
    assert built["metrics"]["languages_with_machine_supported_applicable_rubric_scope"] == 4
    assert built["metrics"]["languages_with_confident_machine_supported_applicable_rubric_scope"] == 3
    assert built["metrics"]["languages_with_clean_out_of_scope_partition"] == 4
    assert built["metrics"]["languages_with_direct_plus_inherited_anti_cheat_support"] == 4
    assert built["metrics"]["weakest_language_family"] == "web_js_ts_html"
    web = next(row for row in built["language_rows"] if row["language_family"] == "web_js_ts_html")
    assert web["rubric_applicable_supported_count"] == 8
    assert web["rubric_confidently_supported_count"] == 0
    assert web["same_surface_confidence_tier"] == "fragile"


def test_main_writes_summary_and_audit(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "AUDIT", tmp_path / "artifacts" / "weighted_winner_review_scope_audit.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9959_weighted_winner_review_scope_audit.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "WEIGHTED_WINNER_REVIEW_SCOPE_AUDIT_STAGE9959.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    audit = json.loads(module.AUDIT.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert audit["metrics"]["languages_with_confident_machine_supported_applicable_rubric_scope"] == 3
    assert audit["metrics"]["weakest_language_family"] == "web_js_ts_html"
