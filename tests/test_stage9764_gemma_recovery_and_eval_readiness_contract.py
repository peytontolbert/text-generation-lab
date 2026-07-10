from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9764_gemma_recovery_and_eval_readiness_contract.py"
    spec = importlib.util.spec_from_file_location("stage9764", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9764_contract_matches_current_frontier():
    mod = _load()
    contract = mod.build_contract(
        mod.load_json(mod.GAP_LEDGER),
        mod.load_jsonl(mod.STANDALONE_PACKETS),
        mod.load_jsonl(mod.HARNESS_PACKETS),
        mod.load_json(mod.HARNESS_PREP_AUDIT),
        mod.load_json(mod.GEMMA_GAP_AUDIT),
    )

    assert contract["failures"] == []
    assert contract["operational_state"]["standalone_ready_now_tasks_remaining"] == 26
    assert contract["operational_state"]["supported_standalone_cells"] == 13
    assert contract["operational_state"]["harness_prep_tasks_already_complete"] == 72
    assert contract["operational_state"]["gemma_12b_present"] is False
    assert contract["operational_state"]["standalone_gemma_runner_present"] is False
    assert contract["operational_state"]["full_product_harness_runner_present"] is False
    assert contract["phase_4_eval_readiness"]["expert_maintainer_subskill_count"] == 16
    assert contract["phase_4_eval_readiness"]["anti_cheat_challenge_family_count"] == 6
    assert contract["phase_1_ready_now_evidence"]["top_queue_entry"] == (
        "standalone_100m_weights::python::symbol_binding::expert_maintainer_rubric_review"
    )
