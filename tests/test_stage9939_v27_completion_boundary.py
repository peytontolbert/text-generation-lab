import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9939_v27_completion_boundary.py"
    spec = importlib.util.spec_from_file_location("stage9939_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9939_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_boundary_reports_live_harness_acceptance_gap():
    module = _load_module()
    built = module.build_boundary()
    assert built["passed"] is True
    assert built["metrics"]["languages_with_standalone_win"] == 4
    assert built["metrics"]["standalone_human_signoff_tasks_remaining"] == 8
    assert built["metrics"]["languages_with_harness_handoff_ready"] == 4
    assert built["metrics"]["languages_with_harness_acceptance_ready"] == 0
    assert built["metrics"]["languages_still_stub_only"] == 4
    assert built["metrics"]["total_pending_harness_artifacts"] == 28
    assert built["metrics"]["objective_complete"] is False


def test_main_writes_summary_and_boundary(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "BOUNDARY", tmp_path / "artifacts" / "v27_completion_boundary.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9939_v27_completion_boundary.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "V27_COMPLETION_BOUNDARY_STAGE9939.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    boundary = json.loads(module.BOUNDARY.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert boundary["metrics"]["languages_with_harness_acceptance_ready"] == 0
    assert boundary["metrics"]["languages_still_stub_only"] == 4
