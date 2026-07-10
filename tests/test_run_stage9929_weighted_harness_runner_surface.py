import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "run_stage9929_weighted_harness_runner_surface.py"
    spec = importlib.util.spec_from_file_location("stage9929_runner_surface", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9929_runner_surface"] = module
    spec.loader.exec_module(module)
    return module


def test_select_cells_and_contract_payload():
    module = _load_module()
    plan = module.load_json(module.PLAN)
    cells = module.select_cells(plan, cell_key=None)
    assert len(cells) == 4
    payload = module.contract_payload(cells[0])
    assert payload["runner_mode"] == "dry_run_contract_only"
    assert payload["runtime_integration_ready"] is True
    assert payload["executable_now"] is False
    assert len(payload["support_modules"]) == 4


def test_main_writes_contracts(monkeypatch, tmp_path):
    module = _load_module()
    source_plan = module.load_json(module.PLAN)
    packet_dir = tmp_path / "packet"
    rewritten_cells = []
    for row in source_plan["cell_plans"]:
        clone = dict(row)
        paths = dict(clone["artifact_paths"])
        paths["packet_dir"] = str(packet_dir.relative_to(tmp_path)) if False else str(packet_dir)
        clone["artifact_paths"] = paths
        rewritten_cells.append(clone)
    local_plan = {"cell_plans": rewritten_cells}
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(local_plan), encoding="utf-8")

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "PLAN", plan_path)
    monkeypatch.setattr(module, "SUPPORT_MODULES", {"fake": tmp_path / "fake_support.py"})
    (tmp_path / "fake_support.py").write_text("# fake\n", encoding="utf-8")

    old_argv = sys.argv
    try:
        sys.argv = ["runner", "--plan", str(plan_path)]
        module.main()
    finally:
        sys.argv = old_argv

    contract = json.loads((packet_dir / "harness_runtime_contract.json").read_text(encoding="utf-8"))
    assert contract["runner_mode"] == "dry_run_contract_only"
    assert contract["support_modules"]["fake"]["present"] is True
