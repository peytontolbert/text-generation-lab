from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "scripts/build_stage9220_no_execution_trainer_readiness_gap_ledger.py"
spec = importlib.util.spec_from_file_location("stage9220", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_stage9220_records_coverage_but_not_execution_readiness():
    card = mod.build_card()
    assert sorted(card["covered_families"]) == sorted(mod.COVERED_FAMILIES)
    assert card["metrics"]["ticket_coverage_ready"] is True
    assert card["metrics"]["trainer_ready_for_execution"] is False
    assert card["metrics"]["final_pre_execution_audit_ready"] is False
    assert card["metrics"]["explicit_one_family_request_present"] is False


def test_stage9220_keeps_execution_cleanup_arxiv_and_training_closed():
    card = mod.build_card()
    for key in [
        "trainer_executed_now",
        "model_forward_attempted",
        "backward_attempted",
        "optimizer_created",
        "checkpoint_written_now",
        "cleanup_authorized_now",
        "runtime_authorized_flag",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
        "data_mining_authorized",
    ]:
        assert card["metrics"][key] is False
    assert not any(card["authority"].values())


def test_stage9220_validation_rejects_open_execution_or_missing_blockers():
    card = mod.build_card()
    card["metrics"]["trainer_ready_for_execution"] = True
    assert "trainer_ready_for_execution" in mod.validate_card(card)

    card = mod.build_card()
    card["metrics"]["cleanup_authorized_now"] = True
    assert "cleanup_authorized_now" in mod.validate_card(card)

    card = mod.build_card()
    card["blockers_before_any_trainer_invocation"] = []
    assert "required_blockers_missing" in mod.validate_card(card)
