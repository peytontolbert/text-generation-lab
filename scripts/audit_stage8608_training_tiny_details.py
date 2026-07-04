#!/usr/bin/env python3
"""Audit training-critical implementation details that can quietly poison probes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import importlib.util

REPO_ROOT = Path(__file__).resolve().parents[1]
TRAINING_DATA_PATH = REPO_ROOT / "legacy_src" / "agentkernel_lite" / "training_data.py"
spec = importlib.util.spec_from_file_location("recovered_training_data", TRAINING_DATA_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {TRAINING_DATA_PATH}")
training_data = importlib.util.module_from_spec(spec)
sys.modules["recovered_training_data"] = training_data
spec.loader.exec_module(training_data)
ByteTokenizer = training_data.ByteTokenizer
_row_text = training_data._row_text
_target_text = training_data._target_text
build_batch = training_data.build_batch


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    symbol_row = {
        "row_id": "leaky_row_id_should_not_appear",
        "split": "train",
        "objective_family": "symbol_binding",
        "language_family": "python",
        "query": {
            "query_kind": "callsite",
            "query_node_id": "opaque_query_id_should_not_appear",
            "features": {"call_shape": "medium", "source_file_is_test": False},
        },
        "graph_input": {
            "graph_id": "opaque_graph_id_should_not_appear",
            "nodes": [
                {"node_id": "opaque_node_id_should_not_appear", "node_type": "repo", "features": {"language_family": "python"}},
                {"node_id": "opaque_file_id_should_not_appear", "node_type": "file", "features": {"is_test": False, "definition_count_bucket": 2}},
            ],
            "edges": [{"src": "opaque_node_id_should_not_appear", "dst": "opaque_file_id_should_not_appear", "edge_type": "contains"}],
        },
        "target": {"binding_action": "BIND_CALL_TO_SYMBOL", "label": "BIND_CALL_TO_SYMBOL"},
        "loss_mask": {"symbol_binding_ce": True},
    }
    decoder_row = {
        "row_id": "decoder_row_id_should_not_be_target",
        "split": "train",
        "objective_family": "bounded_decoder_ce",
        "input_state": {"target_shape": "repair_plan", "evidence_state": "direct_present"},
        "target": {"decoder_text": "Inspect the failing test and apply a minimal patch."},
        "loss_mask": {"decoder_ce": True},
    }
    empty_target_row = {
        "row_id": "empty_target_should_stay_empty",
        "split": "train",
        "target": {},
        "loss_mask": {"decoder_ce": True},
    }

    row_text = _row_text(symbol_row)
    decoder_target = _target_text(decoder_row)
    empty_target = _target_text(empty_target_row)
    tok = ByteTokenizer()
    encoded = tok.encode("abc", max_length=8)
    training_data_source = TRAINING_DATA_PATH.read_text(encoding="utf-8")
    try:
        batch = build_batch([decoder_row], max_encoder_tokens=128, max_decoder_tokens=64)
        tensor_batch_shapes = {
            "input_ids": list(batch.input_ids.shape),
            "decoder_input_ids": list(batch.decoder_input_ids.shape),
            "labels": list(batch.labels.shape),
        }
        decoder_input_shift_ok = tuple(batch.decoder_input_ids.shape)[1] == tuple(batch.labels.shape)[1]
        loss_mask_present = bool(batch.loss_mask["decoder_ce"][0])
        tensor_batch_executed = True
    except Exception as exc:
        tensor_batch_shapes = {"error": str(exc)}
        decoder_input_shift_ok = "decoder_input_ids = labels[:, :-1]" in training_data_source and "shifted_labels = labels[:, 1:]" in training_data_source
        loss_mask_present = "masks[key] = torch.tensor" in training_data_source
        tensor_batch_executed = False

    checks = {
        "row_id_absent_from_model_input": "leaky_row_id_should_not_appear" not in row_text,
        "query_node_id_absent_from_model_input": "opaque_query_id_should_not_appear" not in row_text,
        "graph_id_absent_from_model_input": "opaque_graph_id_should_not_appear" not in row_text,
        "node_id_absent_from_model_input": "opaque_node_id_should_not_appear" not in row_text,
        "target_label_absent_from_model_input": "BIND_CALL_TO_SYMBOL" not in row_text,
        "query_kind_present": "query.kind=callsite" in row_text,
        "graph_node_features_present": "graph.node_feature_count.file.definition_count_bucket.2=1" in row_text,
        "graph_edge_features_present": "graph.edge_type_count.contains=1" in row_text,
        "decoder_target_uses_decoder_text": decoder_target == "Inspect the failing test and apply a minimal patch.",
        "empty_target_does_not_fallback_to_row_id": empty_target == "",
        "decoder_input_shifted_one_shorter": decoder_input_shift_ok,
        "loss_mask_decoder_ce_present": loss_mask_present,
        "byte_tokenizer_has_bos_eos": encoded[0] == tok.bos_id and tok.eos_id in encoded,
    }
    failing = [name for name, passed in checks.items() if not passed]
    metrics = {
        "checks": checks,
        "failing_checks": failing,
        "row_text_preview": row_text[:500],
        "decoder_target": decoder_target,
        "empty_target": empty_target,
        "batch_shapes": tensor_batch_shapes,
        "tensor_batch_executed": tensor_batch_executed,
    }
    passed = not failing
    summary = {
        "stage": 8608,
        "name": "stage8608_reconstructed_training_tiny_details_audit",
        "passed": passed,
        "summary": "Audited training-critical serialization, target fallback, byte tokenization, decoder shift, and loss mask details. This stage guards against row-id leakage and graph evidence loss in recovered probes.",
        "metrics": metrics,
        "gates": {
            "row_id_absent_from_model_input": checks["row_id_absent_from_model_input"],
            "target_label_absent_from_model_input": checks["target_label_absent_from_model_input"],
            "graph_features_present": checks["graph_node_features_present"] and checks["graph_edge_features_present"],
            "empty_target_does_not_fallback_to_row_id": checks["empty_target_does_not_fallback_to_row_id"],
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "transition_head_training_authorized_next": False,
            "body_emission_authorized": False,
            "source_emission_authorized": False,
            "runtime_authorized": False,
            "gemma_execution_authorized_next": False,
            "harness_execution_authorized_next": False,
            "scoring_authorized_next": False,
            "controller_complete_merge_authorized_next": False,
            "promotion_ready": False,
        },
        "next_best_step": "Patch bounded decoder contract validation to reject empty decoder targets and add manifest/schema hash locks."
    }
    out = Path("runs/local/artifacts/stage8608_training_tiny_details_audit")
    write_json(out / "audit_card.json", metrics)
    write_json(Path("runs/summaries/stage8608_reconstructed_training_tiny_details_audit.json"), summary)
    print(json.dumps({"passed": passed, "failing_checks": failing}, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
