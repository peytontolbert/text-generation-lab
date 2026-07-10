import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9945_web_targeted_blended_structured_mix.py"
    spec = importlib.util.spec_from_file_location("stage9945_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9945_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_blend_increases_web_edit_coverage():
    module = _load_module()
    built = module.build_blend()
    assert built["passed"] is True
    assert built["metrics"]["base_structured_rows"] == 392
    assert built["metrics"]["targeted_web_rows_added"] == 12
    assert built["metrics"]["blended_structured_rows"] == 404
    assert built["metrics"]["web_edit_rows_before"] == 15
    assert built["metrics"]["web_edit_rows_after"] == 27
    assert built["metrics"]["targeted_web_weight_sum"] == 30
    assert built["metrics"]["loss_counts"]["edit_localization_ce"] == 72


def test_main_writes_summary_and_audit(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "BLEND", tmp_path / "artifacts" / "web_targeted_blended_structured_state.jsonl")
    monkeypatch.setattr(module, "AUDIT", tmp_path / "artifacts" / "web_targeted_blended_structured_mix_audit.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9945_web_targeted_blended_structured_mix.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "WEB_TARGETED_BLENDED_STRUCTURED_MIX_STAGE9945.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    audit = json.loads(module.AUDIT.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert audit["metrics"]["blended_structured_rows"] == 404
