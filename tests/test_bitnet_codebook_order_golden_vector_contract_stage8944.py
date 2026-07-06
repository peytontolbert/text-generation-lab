from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8944_bitnet_codebook_order_golden_vector_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    CODEBOOK_CANDIDATES,
    REQUIRED_FUTURE_GATES,
    SYNTHETIC_GOLDEN_ROWS,
    build_contract,
    validate_contract,
)


def registry(latest: int = 8943) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_codebook_and_synthetic_golden_rows_are_recorded() -> None:
    assert len(CODEBOOK_CANDIDATES) >= 3
    assert len(SYNTHETIC_GOLDEN_ROWS) >= 3
    assert len(REQUIRED_FUTURE_GATES) >= 10
    assert all("packed_bytes_hex" in row for row in SYNTHETIC_GOLDEN_ROWS)
    assert all("real" not in row["golden_id"] for row in SYNTHETIC_GOLDEN_ROWS)


def test_stage8944_contract_keeps_real_decode_and_checkpoint_blocked() -> None:
    contract = build_contract(registry())
    assert contract["checks"]["synthetic_golden_rows_recorded"] is True
    assert contract["metrics"]["real_weight_read_authorized"] is False
    assert contract["metrics"]["real_packed_decode_authorized"] is False
    assert contract["metrics"]["checkpoint_load_authorized"] is False
    assert contract["metrics"]["checkpoint_write_authorized"] is False
    assert all(value is False for value in contract["authority"].values())


def test_stage8944_validation_rejects_bad_frontier_or_open_authority() -> None:
    contract = build_contract(registry())
    assert validate_contract(contract, registry()) == []
    bad_contract = build_contract(registry())
    bad_contract["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(bad_contract, registry())
    assert "unexpected_registry_frontier:9999" in validate_contract(contract, registry(latest=9999))
