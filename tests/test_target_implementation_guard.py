from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from target_implementation_guard import evaluate_implementation_selection, assert_implementation_allowed


def test_transformer_allowed_for_recovered_target() -> None:
    result = evaluate_implementation_selection("transformer")
    assert result["allowed_for_recovered_100m_target"] is True
    assert result["missing_features"] == []
    assert result["features"]["has_rotary"] is True
    assert result["features"]["has_agent_policy_heads"] is True
    assert result["features"]["has_retrieval_heads"] is True
    assert result["features"]["has_scalar_invariant"] is True


def test_scaffold_blocked_for_recovered_target() -> None:
    result = evaluate_implementation_selection("scaffold")
    assert result["allowed_for_recovered_100m_target"] is False
    assert "recovered 100M target requires implementation=transformer" in result["errors"]
    assert set(result["missing_features"]) == {"has_rotary", "has_agent_policy_heads", "has_retrieval_heads", "has_scalar_invariant"}


def test_assert_blocks_scaffold() -> None:
    try:
        assert_implementation_allowed("scaffold")
    except ValueError as exc:
        assert "implementation selection blocked" in str(exc)
    else:
        raise AssertionError("scaffold should be blocked")
