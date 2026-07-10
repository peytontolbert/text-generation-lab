import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage10079_canonical_harness_runner_plan.py"
    spec = importlib.util.spec_from_file_location("stage10079_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage10079_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_plan_materializes_four_canonical_harness_cells():
    module = _load_module()
    built = module.build_plan()
    assert built["passed"] is True
    assert built["metrics"]["canonical_harness_proxy_cells"] == 4
    assert built["metrics"]["runtime_contracts_written"] == 4
    assert built["metrics"]["cells_with_canonical_100m_better_proxy"] == 4
    for row in built["cell_plans"]:
        assert row["runner_surface_status"] == "dry_run_contract_ready_real_harness_runtime_still_missing"
        assert row["standalone_proxy_frontier"]["same_surface_comparison_stage"] == 10072
        assert row["standalone_proxy_frontier"]["completion_boundary_stage"] == 10078


def test_main_writes_summary_and_plan(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "PLAN", tmp_path / "artifacts" / "canonical_harness_runner_plan.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage10079_canonical_harness_runner_plan.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "CANONICAL_HARNESS_RUNNER_PLAN_STAGE10079.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    plan = json.loads(module.PLAN.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert plan["metrics"]["canonical_harness_proxy_cells"] == 4
