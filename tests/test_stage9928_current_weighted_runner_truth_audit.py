import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9928_current_weighted_runner_truth_audit.py"
    spec = importlib.util.spec_from_file_location("stage9928_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9928_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_audit_confirms_weighted_runner_truth():
    module = _load_module()
    audit = module.build_audit()
    assert audit["passed"] is True
    assert audit["metrics"]["weighted_frontier_winner_cells"] == 4
    assert audit["metrics"]["machine_complete_winner_cells"] == 4
    assert audit["metrics"]["human_review_only_winner_cells"] == 4
    assert audit["metrics"]["weighted_harness_proxy_runner_blocked_cells"] == 4
    assert audit["standalone_runner_surface"]["present"] is True
    assert audit["standalone_runner_surface"]["has_build_prompt"] is True
    assert audit["standalone_runner_surface"]["has_ollama_generate"] is True
    assert audit["harness_runner_surface"]["present"] is False
    assert audit["gemma_execution_state"]["gemma_executed"] is True


def test_main_writes_summary_and_artifacts(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "AUDIT", tmp_path / "artifacts" / "current_weighted_runner_truth_audit.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9928_current_weighted_runner_truth_audit.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "CURRENT_WEIGHTED_RUNNER_TRUTH_AUDIT_STAGE9928.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    audit = json.loads(module.AUDIT.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert "standalone Gemma execution is already real and attached" in summary["decision"]
    assert audit["metrics"]["machine_complete_winner_cells"] == 4
