import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9929_weighted_harness_runner_plan.py"
    spec = importlib.util.spec_from_file_location("stage9929_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9929_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_plan_materializes_four_weighted_harness_cells():
    module = _load_module()
    built = module.build_plan()
    assert built["passed"] is True
    assert built["metrics"]["weighted_harness_proxy_cells"] == 4
    assert built["metrics"]["cell_plans_written"] == 4
    assert built["metrics"]["cells_with_all_stub_paths_present"] == 4
    for row in built["cell_plans"]:
        assert row["runner_surface_status"] == "dry_run_contract_ready_real_harness_runtime_still_missing"
        assert row["remaining_machine_gap"] == "real_full_product_harness_runtime_integration_and_capture"
        assert len(row["runner_steps"]) == 7


def test_main_writes_summary_and_plan(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "PLAN", tmp_path / "artifacts" / "weighted_harness_runner_plan.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9929_weighted_harness_runner_plan.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "WEIGHTED_HARNESS_RUNNER_PLAN_STAGE9929.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    plan = json.loads(module.PLAN.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert plan["metrics"]["weighted_harness_proxy_cells"] == 4
