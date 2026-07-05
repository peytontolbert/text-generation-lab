from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from semantic_equivalence_metamorphic_verifier import (
    api_compatibility_check,
    determinism_contract_check,
    metamorphic_relation_check,
    property_contract_check,
    semantic_equivalence_check,
    verifier_card,
)


def test_semantic_equivalence_accepts_same_code_shape() -> None:
    card = semantic_equivalence_check("def f(x):\n    return x\n", "def f(y):\n    return y\n", required_symbols=["f"])
    assert card["passed"] is True
    assert card["authority"]["runtime_authorized"] is False


def test_semantic_equivalence_rejects_shape_mismatch() -> None:
    card = semantic_equivalence_check("def g(x):\n    return x\n", "def f(y):\n    return y\n")
    assert card["passed"] is False
    assert "function_shape_mismatch" in card["failures"]


def test_property_contract_checks_symbols_and_forbidden_text() -> None:
    card = property_contract_check(
        "def validate_token(x):\n    return x\n",
        [
            {"property_id": "has_symbol", "kind": "must_define_symbol", "value": "validate_token"},
            {"property_id": "no_eval", "kind": "must_not_contain", "value": "eval("},
        ],
    )
    assert card["passed"] is True


def test_metamorphic_relation_preserves_key_and_detects_failure() -> None:
    ok = metamorphic_relation_check({"status": "ok"}, {"status": "ok"}, {"relation_id": "status", "kind": "preserve_key", "key": "status"})
    bad = metamorphic_relation_check({"score": 2}, {"score": 1}, {"relation_id": "score", "kind": "monotonic_non_decrease", "key": "score"})
    assert ok["passed"] is True
    assert bad["passed"] is False
    assert "metamorphic_failed:score:monotonic_non_decrease:score" in bad["failures"]


def test_api_compatibility_checks_symbols_and_signatures() -> None:
    card = api_compatibility_check(
        {"symbols": ["validate_token"], "signatures": {"validate_token": "(token: str) -> bool"}},
        {"symbols": ["validate_token"], "signatures": {"validate_token": "(token: str) -> bool"}},
    )
    assert card["passed"] is True
    bad = api_compatibility_check({"symbols": []}, {"symbols": ["validate_token"]})
    assert bad["passed"] is False
    assert "missing_api_symbol:validate_token" in bad["failures"]


def test_determinism_contract_rejects_different_outputs() -> None:
    ok = determinism_contract_check([{"x": 1}, {"x": 1}])
    bad = determinism_contract_check([{"x": 1}, {"x": 2}])
    assert ok["passed"] is True
    assert bad["passed"] is False
    assert "non_deterministic_outputs" in bad["failures"]


def test_verifier_card_aggregates_failures_and_keeps_authority_closed() -> None:
    card = verifier_card([
        {"row_id": "eq", "verifier_type": "semantic_equivalence", "candidate": "def f(x):\n    return x\n", "reference": "def f(y):\n    return y\n"},
        {"row_id": "det", "verifier_type": "determinism_contract", "outputs": [1, 2]},
    ])
    assert card["rows"] == 2
    assert card["passed"] is False
    assert card["failed_rows"] == 1
    assert card["authority"]["training_authorized_next"] is False
