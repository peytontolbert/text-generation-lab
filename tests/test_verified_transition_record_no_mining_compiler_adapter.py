from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8901_verified_transition_record_no_mining_compiler_adapter import (
    AUTHORITY_CLOSED,
    DEFAULT_LOSS_MASK,
    FORBIDDEN_RAW_KEYS,
    compile_candidate,
    contains_forbidden_raw_key,
    example_candidate,
    validate_record,
)


def test_compile_candidate_outputs_closed_verified_transition_record() -> None:
    record = compile_candidate(example_candidate())
    assert record["schema_version"] == "verified_transition_record_v1"
    assert record["authority"] == AUTHORITY_CLOSED
    assert record["loss_mask"] == DEFAULT_LOSS_MASK
    assert not any(record["loss_mask"].values())
    assert validate_record(record)["passed"] is True


def test_forbidden_raw_key_detector_is_recursive() -> None:
    assert contains_forbidden_raw_key({"nested": {"raw_source_body": "x"}}) is True
    assert contains_forbidden_raw_key({"nested": [{"decoder_text": "x"}]}) is True
    assert contains_forbidden_raw_key({"safe_ref": "source_inventory:abc"}) is False


def test_raw_candidate_compiles_to_failed_anticheat_validation() -> None:
    candidate = example_candidate()
    candidate["raw_patch_body"] = "diff --git ..."
    record = compile_candidate(candidate)
    audit = validate_record(record)
    assert audit["passed"] is False
    assert "anti_cheat_flag_open" in audit["failures"]


def test_open_loss_or_runtime_fails_validation() -> None:
    record = compile_candidate(example_candidate())
    record["loss_mask"]["train_decoder_ce"] = True
    record["tool_result"]["runtime_executed"] = True
    audit = validate_record(record)
    assert audit["passed"] is False
    assert "loss_mask_open" in audit["failures"]
    assert "runtime_executed" in audit["failures"]


def test_forbidden_key_set_covers_known_body_surfaces() -> None:
    for key in ["raw_source_body", "raw_patch_body", "raw_decoder_target_text", "runtime_output_body", "gemma_score_body"]:
        assert key in FORBIDDEN_RAW_KEYS
