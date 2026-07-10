from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9758_cross_front_execution_ledger.py"
    spec = importlib.util.spec_from_file_location("stage9758", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9758_builds_unified_cross_front_totals():
    mod = _load()
    built = mod.build_ledger(
        mod.load_json(mod.STANDALONE_CHECKLIST),
        mod.load_json(mod.HARNESS_CHECKLIST),
        mod.load_json(mod.STANDALONE_STUBS),
        mod.load_json(mod.HARNESS_STUBS),
    )
    totals = built["totals"]
    assert built["failures"] == []
    assert totals["packets_total"] == 49
    assert totals["checklist_rows_total"] == 49
    assert totals["ready_now_tasks_total"] == 111
    assert totals["runner_blocked_tasks_total"] == 278
    assert totals["standalone_stub_files_total"] == 52
    assert totals["harness_stub_files_total"] == 252
    assert built["fronts"]["standalone_front"]["cells"] == 13
    assert built["fronts"]["standalone_front"]["top_priority_cell"] == "standalone_100m_weights::python::symbol_binding"
    assert built["fronts"]["harness_front"]["cells"] == 36
    assert built["fronts"]["harness_front"]["top_priority_cell"] == "full_product_harness::python::symbol_binding"
