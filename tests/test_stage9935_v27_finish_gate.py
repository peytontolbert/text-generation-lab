import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9935_v27_finish_gate.py"
    spec = importlib.util.spec_from_file_location("stage9935_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9935_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_gate_reports_current_finish_state():
    module = _load_module()
    built = module.build_gate()
    assert built["passed"] is True
    assert built["metrics"]["languages_with_standalone_win"] == 4
    assert built["metrics"]["standalone_human_signoff_tasks_remaining"] == 8
    assert built["metrics"]["languages_with_harness_handoff_ready"] == 4
    assert built["metrics"]["objective_complete"] is False


def test_main_writes_summary_and_gate(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "GATE", tmp_path / "artifacts" / "v27_finish_gate.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9935_v27_finish_gate.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "V27_FINISH_GATE_STAGE9935.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    gate = json.loads(module.GATE.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert gate["metrics"]["standalone_human_signoff_tasks_remaining"] == 8
