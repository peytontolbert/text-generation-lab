from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

FAILURE_TO_OPERATION = {
    "missing_evidence": "add_retrieval_counterfactuals",
    "wrong_file": "add_navigation_examples",
    "symbol_resolution_failure": "add_symbol_binding_examples",
    "overbroad_patch": "add_minimality_preference_pairs",
    "flaky_failure": "hold_flaky_failure_rows",
    "target_leakage": "quarantine_or_rewrite_leaky_rows",
    "schema_drift": "rewrite_schema_or_alias_fields",
    "bad_label": "relabel_or_quarantine",
    "ood": "route_to_ood_holdout_or_collect_neighbors",
    "decoder_invalid": "add_format_repair_or_denoise_rows",
}

ALLOWED_DATASET_OPS = {
    "add",
    "remove",
    "relabel",
    "rebalance",
    "quarantine",
    "rewrite",
    "add_counterfactual",
    "add_preference_pair",
    "holdout",
    "route_change",
    "no_op_review",
}


def stable_id(prefix: str, value: str) -> str:
    import hashlib

    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]}"


def failure_type(trace: dict[str, Any]) -> str:
    for key in ["failure_type", "top_failure", "judge_failure_type", "verifier_failure_type"]:
        value = trace.get(key)
        if isinstance(value, str) and value:
            return value
    tags = trace.get("failure_tags") if isinstance(trace.get("failure_tags"), list) else []
    for tag in tags:
        if str(tag) in FAILURE_TO_OPERATION:
            return str(tag)
    return "unknown_failure"


def dataset_op_for_failure(ftype: str) -> tuple[str, str]:
    action = FAILURE_TO_OPERATION.get(ftype, "manual_review")
    if action.startswith("add_") and "counterfactual" in action:
        return "add_counterfactual", action
    if action.startswith("add_") and "preference" in action:
        return "add_preference_pair", action
    if action.startswith("add_"):
        return "add", action
    if action.startswith("quarantine"):
        return "quarantine", action
    if action.startswith("rewrite"):
        return "rewrite", action
    if action.startswith("relabel"):
        return "relabel", action
    if action.startswith("hold"):
        return "holdout", action
    if action.startswith("route"):
        return "route_change", action
    return "no_op_review", action


def compile_trace(trace: dict[str, Any], *, index: int = 0) -> dict[str, Any]:
    trace_id = str(trace.get("trace_id") or trace.get("eval_id") or trace.get("task_id") or f"trace_{index}")
    ftype = failure_type(trace)
    op, action = dataset_op_for_failure(ftype)
    source_examples = trace.get("source_examples") if isinstance(trace.get("source_examples"), list) else []
    affected_slices = trace.get("slice_tags") if isinstance(trace.get("slice_tags"), list) else []
    if not affected_slices and isinstance(trace.get("task_tags"), list):
        affected_slices = trace["task_tags"]
    blocked_reasons: list[str] = []
    if trace.get("locked_eval_trace") is True or trace.get("hidden_final_trace") is True:
        blocked_reasons.append("locked_or_hidden_eval_trace_forbidden_for_training_patch")
    if trace.get("contains_target_answer") is True:
        blocked_reasons.append("trace_contains_target_answer")
    if trace.get("source_body_leak") is True:
        blocked_reasons.append("trace_contains_source_body_leak")
    if op not in ALLOWED_DATASET_OPS:
        blocked_reasons.append("dataset_op_not_allowed")
    route = "BLOCK_DATASET_PATCH" if blocked_reasons else "PROPOSE_DATASET_PATCH"
    patch_id = stable_id("dataset_patch", json.dumps({"trace_id": trace_id, "failure_type": ftype, "op": op}, sort_keys=True))
    return {
        "patch_id": patch_id,
        "trace_id": trace_id,
        "failure_type": ftype,
        "dataset_op": op,
        "recommended_action": action,
        "route": route,
        "blocked": bool(blocked_reasons),
        "blocked_reasons": blocked_reasons,
        "affected_slices": affected_slices,
        "source_examples": source_examples[:50],
        "evidence": {
            "model_id": trace.get("model_id"),
            "dataset_version": trace.get("dataset_version"),
            "eval_run_id": trace.get("eval_run_id"),
            "verifier_result": trace.get("verifier_result"),
            "judge_result": trace.get("judge_result"),
        },
        "expected_controls": [
            "source_inventory_lineage",
            "source_provenance",
            "contamination_leakage_detector",
            "schema_drift_detector",
            "dataset_junk_ood_ranker_v1",
            "cluster_slice_near_duplicate_detector",
        ],
    }


def compile_traces(traces: list[dict[str, Any]]) -> dict[str, Any]:
    patches = [compile_trace(trace, index=i) for i, trace in enumerate(traces)]
    route_counts = Counter(patch["route"] for patch in patches)
    op_counts = Counter(patch["dataset_op"] for patch in patches)
    failure_counts = Counter(patch["failure_type"] for patch in patches)
    return {
        "traces": len(traces),
        "dataset_patches": patches,
        "metrics": {
            "traces": len(traces),
            "proposed_patches": route_counts.get("PROPOSE_DATASET_PATCH", 0),
            "blocked_patches": route_counts.get("BLOCK_DATASET_PATCH", 0),
            "route_counts": dict(route_counts),
            "op_counts": dict(op_counts),
            "failure_counts": dict(failure_counts),
        },
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile eval/failure traces into auditable dataset patch operations without generating training rows.")
    parser.add_argument("traces", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    card = compile_traces(read_jsonl(args.traces))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()

# Backward-compatible Stage8760 API. The newer compiler above emits generic
# dataset operations, while Stage8760 summaries/tests expected typed patch actions.
PATCH_ACTIONS = {
    "ADD_COUNTERFACTUAL_NEIGHBOR",
    "ADD_RETRIEVAL_NEGATIVE",
    "ADD_BOUNDARY_POSITIVE",
    "ADD_BOUNDARY_NEGATIVE",
    "RELABEL_OR_REVIEW",
    "DOWNWEIGHT_OR_PRUNE",
    "HOLDOUT_LONG_OUTPUT",
    "ADD_VERIFIER_REPAIR_ROW",
    "REQUEST_SOURCE_EVIDENCE",
}


def _compat_text(value: Any) -> str:
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True).lower()
    return str(value or "").lower()


def classify_trace(trace: dict[str, Any]) -> dict[str, Any]:
    row_id = str(trace.get("row_id") or trace.get("eval_row_id") or trace.get("id") or "unknown_row")
    failure = str(trace.get("failure_type") or trace.get("error_type") or trace.get("bucket") or "").lower()
    pred = str(trace.get("prediction") or trace.get("pred") or "")
    target = str(trace.get("target") or trace.get("label") or "")
    evidence_state = str(trace.get("evidence_state") or "").lower()
    route = str(trace.get("route") or trace.get("dataset_route") or "")
    surface = str(trace.get("surface") or trace.get("repair_surface") or trace.get("objective_family") or "")
    text = _compat_text(trace)
    reasons: list[str] = []
    if trace.get("target_over_decoder_budget") or "long_output" in failure or "html" in text:
        action = "HOLDOUT_LONG_OUTPUT"
        reasons.append("long_or_budget_bad_output")
    elif trace.get("leak_detected") or "internal_token" in text or "leak" in failure:
        action = "ADD_VERIFIER_REPAIR_ROW"
        reasons.append("internal_or_surface_leak_failure")
    elif trace.get("missing_source_evidence") or evidence_state in {"missing", "insufficient", "evidence_removed"}:
        action = "REQUEST_SOURCE_EVIDENCE"
        reasons.append("missing_or_insufficient_evidence")
    elif trace.get("high_confidence_wrong") or failure in {"label_conflict", "high_confidence_wrong"}:
        action = "RELABEL_OR_REVIEW"
        reasons.append("high_confidence_wrong_or_label_conflict")
    elif pred and target and pred != target:
        if "retrieve" in pred.lower() or "retrieve" in target.lower():
            action = "ADD_RETRIEVAL_NEGATIVE"
            reasons.append("retrieve_boundary_confusion")
        elif any(tok in pred.lower() or tok in target.lower() for tok in ["safe", "unsafe"]):
            action = "ADD_COUNTERFACTUAL_NEIGHBOR"
            reasons.append("safe_unsafe_boundary_confusion")
        else:
            action = "ADD_BOUNDARY_NEGATIVE"
            reasons.append("label_boundary_confusion")
    elif trace.get("duplicate_semantic_key") or trace.get("harmful_train_neighbor"):
        action = "DOWNWEIGHT_OR_PRUNE"
        reasons.append("duplicate_or_harmful_neighbor")
    elif route == "KEEP_STRUCTURED" and surface:
        action = "ADD_BOUNDARY_POSITIVE"
        reasons.append("structured_surface_gap")
    else:
        action = "RELABEL_OR_REVIEW"
        reasons.append("unclassified_eval_failure")
    return {
        "patch_id": f"patch::{row_id}",
        "row_id": row_id,
        "source_eval_trace_id": str(trace.get("trace_id") or trace.get("eval_trace_id") or row_id),
        "dataset_patch_action": action,
        "patch_action_valid": action in PATCH_ACTIONS,
        "reasons": sorted(set(reasons)),
        "target_surface": surface,
        "prediction": pred,
        "target": target,
        "evidence_state": evidence_state,
        "recommended_route": action_to_route(action),
        "authority": authority_closed(),
    }


def action_to_route(action: str) -> str:
    if action == "HOLDOUT_LONG_OUTPUT":
        return "HOLD_LONG_OUTPUT"
    if action == "DOWNWEIGHT_OR_PRUNE":
        return "DROP_DUPLICATE"
    if action == "REQUEST_SOURCE_EVIDENCE":
        return "NEEDS_RETRIEVAL"
    if action == "ADD_VERIFIER_REPAIR_ROW":
        return "USE_FOR_DENOISE_REPAIR"
    if action == "RELABEL_OR_REVIEW":
        return "NEEDS_HUMAN_REVIEW"
    return "KEEP_STRUCTURED"


def authority_closed() -> dict[str, bool]:
    return {
        "model_execution_authorized_next": False,
        "training_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "source_emission_authorized": False,
        "body_emission_authorized": False,
        "gemma_execution_authorized_next": False,
        "harness_execution_authorized_next": False,
        "scoring_authorized_next": False,
        "controller_complete_merge_authorized_next": False,
        "promotion_ready": False,
    }


def build_patch_card(traces: list[dict[str, Any]]) -> dict[str, Any]:
    patches = [classify_trace(trace) for trace in traces]
    action_counts = Counter(patch["dataset_patch_action"] for patch in patches)
    route_counts = Counter(patch["recommended_route"] for patch in patches)
    return {
        "rows": len(traces),
        "patches": patches,
        "metrics": {
            "rows": len(traces),
            "patches": len(patches),
            "valid_patch_actions": sum(int(patch["patch_action_valid"]) for patch in patches),
            "action_counts": dict(action_counts),
            "recommended_route_counts": dict(route_counts),
        },
        "authority": authority_closed(),
    }

