import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9961_blended_weak_language_recovery_packet.py"
    spec = importlib.util.spec_from_file_location("stage9961_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9961_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_rows_targets_weak_languages_with_rust_anchors():
    module = _load_module()
    rows, audit, failures = module.build_rows()
    assert failures == []
    assert audit["rows"] == 48
    assert audit["language_root_counts"] == {"c_cpp": 5, "python": 3, "rust": 2, "web_js_ts_html": 6}
    assert audit["split_counts"] == {"eval": 16, "strict_eval": 16, "train": 16}
    assert audit["reason_counts"]["gemma_advantage_recovery"] == 15
    assert audit["reason_counts"]["hundred_m_miss_recovery"] == 27
    assert audit["reason_counts"]["rust_anchor_preserve_winning_pattern"] == 6


def test_main_writes_summary_and_audit(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "MANIFEST", tmp_path / "artifacts" / "blended_weak_language_recovery_manifest.jsonl")
    monkeypatch.setattr(module, "AUDIT", tmp_path / "artifacts" / "blended_weak_language_recovery_audit.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9961_blended_weak_language_recovery_packet.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "BLENDED_WEAK_LANGUAGE_RECOVERY_PACKET_STAGE9961.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "COMPILED_DIR", tmp_path / "compiled")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    audit = json.loads(module.AUDIT.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert audit["metrics"]["rows"] == 48
    assert audit["metrics"]["language_root_counts"]["web_js_ts_html"] == 6
