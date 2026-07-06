from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage9043_domain_twin_operator_bridge import (  # noqa: E402
    OPERATOR_BRIDGE,
    build_card,
    validate_card,
)


def test_stage9043_bridge_covers_domain_twin_and_critical_ops() -> None:
    card = build_card({"metrics": {"authority_counts": {}}})
    assert validate_card(card) == []
    assert card["checks"]["domain_graph_variables_recorded"] is True
    assert card["checks"]["twin_memory_variables_recorded"] is True
    assert {row["operator"] for row in OPERATOR_BRIDGE} == {"OP030", "OP053", "OP048", "OP059", "OP086"}
    assert card["metrics"]["domain_graph_materialized_now"] is False
    assert card["metrics"]["operator_bridge_training_authorized_now"] is False
    assert card["metrics"]["arxiv_scan_authorized_now"] is False


def test_stage9043_validation_rejects_open_training_or_authority() -> None:
    card = build_card({"metrics": {"authority_counts": {}}})
    card["metrics"]["training_authorized"] = True
    card["authority"]["model_execution_authorized_next"] = True
    failures = validate_card(card)
    assert "training_authorized" in failures
    assert "authority_open" in failures
