from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8939_bitnet_layout_decoder_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_assertion_rows,
    build_contract,
    load_rows,
    target_weight_count,
    validate_contract,
)


def registry(latest: int = 8938) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_target_weight_count_and_file_size_assertions() -> None:
    assert target_weight_count([640, 640]) == 409600
    rows = build_assertion_rows(load_rows())
    assert len(rows) >= 100
    mismatches = [row for row in rows if not row["file_size_matches_2bit_shape"]]
    assert len(mismatches) == 1
    assert mismatches[0]["mismatch_class"] == "source_vocab_lm_head_blocked_by_tokenizer_policy"
    assert all(row["decode_authorized"] is False for row in rows)


def test_stage8939_contract_keeps_decode_and_checkpoint_blocked() -> None:
    contract = build_contract(registry())
    assert contract["checks"]["non_vocab_file_sizes_match_2bit_shape"] is True
    assert contract["checks"]["lm_head_vocab_projection_isolated"] is True
    assert contract["metrics"]["decode_packed_bitnet_authorized"] is False
    assert contract["metrics"]["checkpoint_load_authorized"] is False
    assert contract["metrics"]["checkpoint_write_authorized"] is False
    assert all(value is False for value in contract["authority"].values())


def test_stage8939_validation_rejects_bad_frontier_or_open_authority() -> None:
    contract = build_contract(registry())
    assert validate_contract(contract, registry()) == []
    bad_contract = build_contract(registry())
    bad_contract["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(bad_contract, registry())
    assert "unexpected_registry_frontier:9999" in validate_contract(contract, registry(latest=9999))
