from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9718_locked_multilingual_acceptance_evidence_ledger.py"
    spec = importlib.util.spec_from_file_location("stage9718_acceptance_ledger", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9718_real_ledger_has_no_claim_ready_cells_and_four_seeded_support_cells():
    mod = _load()
    contract = mod.load_json(mod.SOURCE_CONTRACT)
    suite = mod.load_json(mod.SOURCE_PACKS)
    anti_hack = mod.load_json(mod.SOURCE_ANTI_HACK)
    probe = mod.load_json(mod.SOURCE_SYMBOL_BINDING_PROBE)
    ledger = mod.build_ledger(contract, suite["benchmark_packs"], anti_hack, probe)
    assert ledger["passed"] is True
    assert ledger["metrics"]["records"] == 72
    assert ledger["metrics"]["claim_ready_cells"] == 0
    assert len(ledger["metrics"]["seeded_supporting_evidence_cells"]) == 4
    assert all("::symbol_binding" in key for key in ledger["metrics"]["seeded_supporting_evidence_cells"])


def test_stage9718_symbol_binding_standalone_cells_get_supporting_probe_but_not_claim_ready():
    mod = _load()
    contract = mod.load_json(mod.SOURCE_CONTRACT)
    suite = mod.load_json(mod.SOURCE_PACKS)
    anti_hack = mod.load_json(mod.SOURCE_ANTI_HACK)
    probe = mod.load_json(mod.SOURCE_SYMBOL_BINDING_PROBE)
    ledger = mod.build_ledger(contract, suite["benchmark_packs"], anti_hack, probe)
    target = [
        record for record in ledger["records"]
        if record["mode"] == "standalone_100m_weights" and record["skill_area"] == "symbol_binding"
    ]
    assert len(target) == 4
    for record in target:
        assert record["attached_evidence"]
        assert record["claim_ready"] is False
        assert "same_surface_100m_vs_gemma12b_evidence_missing" in record["blockers"]
        assert "missing_required_evidence:same_prompt_surface_gemma12b_outputs" in record["blockers"]


def test_stage9718_fails_if_stage9717_is_not_passed():
    mod = _load()
    contract = mod.load_json(mod.SOURCE_CONTRACT)
    suite = mod.load_json(mod.SOURCE_PACKS)
    anti_hack = dict(mod.load_json(mod.SOURCE_ANTI_HACK))
    anti_hack["passed"] = False
    probe = mod.load_json(mod.SOURCE_SYMBOL_BINDING_PROBE)
    ledger = mod.build_ledger(contract, suite["benchmark_packs"], anti_hack, probe)
    assert ledger["passed"] is False
    assert "stage9717_not_passed" in ledger["failures"]
