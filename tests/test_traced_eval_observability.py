from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from traced_eval_observability import trace_observability_card, validate_trace


GOOD_SPAN = {"span_id": "s1", "span_type": "tool", "name": "read_file"}


def test_passes_successful_trace() -> None:
    record = validate_trace({"eval_id": "ok", "spans": [GOOD_SPAN], "metric_events": [{"metric": "exact", "value": 1.0}]})
    assert record["trace_route"] == "PASS_EVAL_TRACE"
    assert record["dataset_patch_link"]["eligible"] is False
    assert record["authority"]["training_authorized"] is False


def test_failure_trace_becomes_dataset_patch_eligible() -> None:
    record = validate_trace({"eval_id": "fail", "spans": [GOOD_SPAN], "failure_type": "symbol_binding_failure"})
    assert record["trace_route"] == "PASS_FAILURE_TRACE_PACKET"
    assert record["failure_packet"]["dataset_patch_eligible"] is True
    assert record["dataset_patch_link"]["patch_op"] == "compile_failure_to_dataset_patch"


def test_missing_span_fields_route_schema_review() -> None:
    record = validate_trace({"eval_id": "bad", "spans": [{"span_id": "s1"}]})
    assert record["trace_route"] == "HOLD_TRACE_SCHEMA_REVIEW"
    assert any(reason.startswith("span_missing_") for reason in record["reasons"])


def test_contamination_blocks_trace_even_if_failure() -> None:
    record = validate_trace({"eval_id": "locked", "spans": [GOOD_SPAN], "failure_type": "x", "locked_eval_source": True})
    assert record["trace_route"] == "BLOCK_TRACE_CONTAMINATION"
    assert record["dataset_patch_link"]["eligible"] is False


def test_trace_observability_card_counts_routes() -> None:
    card = trace_observability_card([
        {"eval_id": "ok", "spans": [GOOD_SPAN]},
        {"eval_id": "fail", "spans": [GOOD_SPAN], "failed": True},
        {"eval_id": "review", "spans": []},
        {"eval_id": "block", "spans": [GOOD_SPAN], "target_answer_included": True},
    ])
    assert card["metrics"]["pass_trace_rows"] == 1
    assert card["metrics"]["failure_packet_rows"] == 1
    assert card["metrics"]["schema_review_rows"] == 1
    assert card["metrics"]["blocked_rows"] == 1
    assert card["metrics"]["dataset_patch_eligible_rows"] == 1
    assert card["metrics"]["authority_rows"] == 0
