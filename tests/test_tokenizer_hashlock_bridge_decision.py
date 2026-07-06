from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8927_tokenizer_hashlock_bridge_decision import (  # noqa: E402
    AK_SPECIALS,
    AUTHORITY_CLOSED,
    CORE_TOKENS,
    V2_RESERVED,
    build_bridge_rows,
    build_decision,
    validate_decision,
)


def registry(latest: int = 8924) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_bridge_rows_keep_core_identity_and_block_special_copy() -> None:
    rows = build_bridge_rows()
    assert len(rows) == len(CORE_TOKENS) + len(AK_SPECIALS) + len(V2_RESERVED)
    core = [row for row in rows if row["bridge_policy"] == "identity_core_id_lock"]
    assert all(row["source_id"] == row["target_id"] for row in core)
    assert all(row["embedding_copy_authorized"] is False for row in rows)
    assert all(row["tokenizer_swap_authorized"] is False for row in rows)


def test_decision_keeps_target_tokenizer_and_blocks_authority() -> None:
    decision = build_decision()
    assert decision["bridge_policy"]["current_decision"] == "keep_recovered_target_tokenizer_1506"
    assert decision["bridge_policy"]["direct_source_tokenizer_swap"] == "blocked"
    assert decision["bridge_policy"]["embedding_resize"] == "blocked"
    assert decision["authority"] == AUTHORITY_CLOSED


def test_validate_decision_accepts_current_decision() -> None:
    decision = build_decision()
    assert validate_decision(decision, registry()) == []


def test_validate_decision_rejects_unsafe_tokenizer_swap_decision() -> None:
    decision = build_decision()
    decision["bridge_policy"]["current_decision"] = "adopt_source_tokenizer"
    failures = validate_decision(decision, registry())
    assert "unsafe_current_decision" in failures
