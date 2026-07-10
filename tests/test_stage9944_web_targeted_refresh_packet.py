import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9944_web_targeted_refresh_packet.py"
    spec = importlib.util.spec_from_file_location("stage9944_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9944_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_rows_targets_web_weak_surfaces_with_anchor():
    module = _load_module()
    rows, audit, failures = module.build_rows()
    assert failures == []
    assert audit["rows"] == 12
    assert audit["surface_counts"]["test_surface"] == 3
    assert audit["surface_counts"]["entrypoint_or_invocation_surface"] == 3
    assert audit["surface_counts"]["implementation_file_surface"] == 3
    assert audit["surface_counts"]["symbol_definition_or_implementation_surface"] == 3
    assert audit["split_counts"] == {"eval": 4, "strict_eval": 4, "train": 4}


def test_main_writes_summary_and_audit(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "MANIFEST", tmp_path / "artifacts" / "web_targeted_refresh_manifest.jsonl")
    monkeypatch.setattr(module, "AUDIT", tmp_path / "artifacts" / "web_targeted_refresh_audit.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9944_web_targeted_refresh_packet.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "WEB_TARGETED_REFRESH_PACKET_STAGE9944.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "COMPILED_DIR", tmp_path / "compiled")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    audit = json.loads(module.AUDIT.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert audit["metrics"]["rows"] == 12
