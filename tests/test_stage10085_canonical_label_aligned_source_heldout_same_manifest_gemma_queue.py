import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage10085_canonical_label_aligned_source_heldout_same_manifest_gemma_queue.py"
    spec = importlib.util.spec_from_file_location("stage10085_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage10085_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_queue_materializes_canonical_source_heldout_gemma_queue():
    module = _load_module()
    built = module.build_queue()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 55
    packet = built["packet"]
    assert packet["same_surface_packet"]["heldout_compare_rows"] == 55
    assert packet["review_packet_paths"]["shortcut_validity_audit"].endswith("stage10082_canonical_label_aligned_shortcut_validity_audit/canonical_label_aligned_shortcut_validity_audit.json")


def test_main_writes_summary_and_queue(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "QUEUE", tmp_path / "artifacts" / "canonical_label_aligned_source_heldout_same_manifest_gemma_queue.json")
    monkeypatch.setattr(module, "PACKETS", tmp_path / "artifacts" / "canonical_label_aligned_source_heldout_same_manifest_gemma_packets.jsonl")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage10085_canonical_label_aligned_source_heldout_same_manifest_gemma_queue.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "CANONICAL_LABEL_ALIGNED_SOURCE_HELDOUT_SAME_MANIFEST_GEMMA_QUEUE_STAGE10085.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    queue = json.loads(module.QUEUE.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert queue["queue_entries"][0]["same_surface_packet"]["heldout_compare_rows"] == 55
