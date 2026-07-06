from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from counterfactual_obligation_audit import audit_rows  # noqa: E402
from program_state_call_graph_extractor import extract_python_call_graph  # noqa: E402
from program_state_symbol_table_extractor import extract_python_symbols  # noqa: E402
from structured_dataset_junk_ranker import rank_row, rank_rows  # noqa: E402


PY_SOURCE = """
import math

class Accumulator:
    def add(self, value: int) -> int:
        return int(math.sqrt(value))

def run(x: int) -> int:
    acc = Accumulator()
    return acc.add(x)
"""


def test_symbol_extractor_recovers_import_class_function_method_and_calls() -> None:
    packet = extract_python_symbols(PY_SOURCE, row_id="row_a", path="pkg/mod.py").to_dict()
    assert packet["failures"] == []
    kinds = {symbol["symbol_kind"] for symbol in packet["symbols"]}
    names = {symbol["name"] for symbol in packet["symbols"]}
    assert {"import", "class", "method", "function", "callsite", "local"}.issubset(kinds)
    assert {"math", "Accumulator", "add", "run", "math.sqrt", "Accumulator", "acc.add"}.intersection(names)
    assert any(edge["edge_type"] == "imports" for edge in packet["edges"])
    assert any(edge["edge_type"] == "calls" for edge in packet["edges"])


def test_call_graph_extractor_recovers_call_edges_and_syntax_failures() -> None:
    packet = extract_python_call_graph(PY_SOURCE, row_id="row_b", path="pkg/mod.py").to_dict()
    assert packet["failures"] == []
    call_names = {node["name"] for node in packet["call_nodes"]}
    assert "math.sqrt" in call_names
    assert "Accumulator" in call_names
    assert "acc.add" in call_names
    assert any(edge["edge_type"] == "calls_reference" for edge in packet["edges"])
    bad = extract_python_call_graph("def broken(:\n", row_id="bad", path="bad.py").to_dict()
    assert bad["call_nodes"] == []
    assert bad["failures"] and bad["failures"][0].startswith("syntax_error:")


def test_structured_junk_ranker_routes_budget_internal_and_safe_rows() -> None:
    hold = rank_row({"row_id": "long", "decoder_token_len": 1000, "decoder_text": "bounded content for a long target", "decode_allowed": True, "decoder_budget_ok": False})
    repair = rank_row({"row_id": "leak", "decoder_text": "<MTC> hidden", "decode_allowed": True, "decoder_budget_ok": True})
    keep = rank_row({"row_id": "safe", "decoder_text": "bounded answer", "decode_allowed": True, "decoder_budget_ok": True})
    assert hold["recommended_action"] == "HOLD_LONG_OUTPUT"
    assert "target_over_decoder_budget" in hold["reasons"]
    assert repair["recommended_action"] == "USE_FOR_DENOISE_REPAIR"
    assert "raw_internal_token_in_decoder" in repair["reasons"]
    assert keep["recommended_action"] == "KEEP_BOUNDED_DECODER"
    card = rank_rows([
        {"row_id": "long", "decoder_token_len": 1000, "decoder_text": "bounded content for a long target", "decode_allowed": True, "decoder_budget_ok": False},
        {"row_id": "leak", "decoder_text": "<MTC> hidden", "decode_allowed": True, "decoder_budget_ok": True},
        {"row_id": "safe", "decoder_text": "bounded answer", "decode_allowed": True, "decoder_budget_ok": True},
    ])
    assert card["rows"] == 3
    assert card["route_counts"]["HOLD_LONG_OUTPUT"] == 1


def test_counterfactual_obligation_audit_accepts_complete_group_and_flags_missing() -> None:
    complete = [
        {"row_id": "a", "semantic_key": "g1", "objective_family": "intent", "obligation_type": "POSITIVE_ORIGINAL"},
        {"row_id": "b", "semantic_key": "g1", "objective_family": "intent", "obligation_type": "EVIDENCE_REMOVED_OR_RETRIEVE"},
        {"row_id": "c", "semantic_key": "g1", "objective_family": "intent", "obligation_type": "CONTRASTIVE_BOUNDARY_SIBLING"},
    ]
    complete_card = audit_rows(complete)
    assert complete_card["counterfactual_obligations_complete"] is True
    missing_card = audit_rows(complete[:2])
    assert missing_card["counterfactual_obligations_complete"] is False
    assert missing_card["missing_obligation_groups"] == 1
