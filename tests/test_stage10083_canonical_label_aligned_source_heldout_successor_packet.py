import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage10083_canonical_label_aligned_source_heldout_successor_packet.py"
    spec = importlib.util.spec_from_file_location("stage10083_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage10083_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_packet_materializes_canonical_source_heldout_manifest():
    module = _load_module()
    built = module.build_packet()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 95
    assert built["metrics"]["heldout_rows"] == 55
    assert built["metrics"]["heldout_per_language_label_map"]["python"]["A"] == "TARGET_TEST"
    assert built["metrics"]["heldout_per_language_label_map"]["c_cpp"]["E"] == "TARGET_CONFIG"
    assert built["policy"]["preserve_stage10036_source_heldout_row_composition"] is True


def test_main_writes_summary_and_packet(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "PACKET", tmp_path / "artifacts" / "canonical_label_aligned_source_heldout_successor_packet.json")
    monkeypatch.setattr(module, "MANIFEST", tmp_path / "artifacts" / "canonical_label_aligned_source_heldout_manifest.jsonl")
    monkeypatch.setattr(module, "ROWS", tmp_path / "artifacts" / "canonical_label_aligned_source_heldout_rows.jsonl")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage10083_canonical_label_aligned_source_heldout_successor_packet.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "CANONICAL_LABEL_ALIGNED_SOURCE_HELDOUT_SUCCESSOR_PACKET_STAGE10083.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    packet = json.loads(module.PACKET.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert packet["metrics"]["heldout_rows"] == 55
