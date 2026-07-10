import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9936_v27_closeout_packet.py"
    spec = importlib.util.spec_from_file_location("stage9936_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9936_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_packet_materializes_four_language_closeout_rows():
    module = _load_module()
    built = module.build_packet()
    assert built["passed"] is True
    assert built["metrics"]["language_packets"] == 4
    assert built["metrics"]["total_human_tasks_remaining"] == 8
    assert built["metrics"]["languages_with_external_harness_handoff"] == 4


def test_main_writes_summary_and_packet(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "PACKET", tmp_path / "artifacts" / "v27_closeout_packet.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9936_v27_closeout_packet.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "V27_CLOSEOUT_PACKET_STAGE9936.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    packet = json.loads(module.PACKET.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert packet["metrics"]["language_packets"] == 4
