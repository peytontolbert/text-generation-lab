from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

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


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True).lower()
    return str(value or "").lower()


def classify_trace(trace: dict[str, Any]) -> dict[str, Any]:
    row_id = str(trace.get("row_id") or trace.get("eval_row_id") or trace.get("id") or "unknown_row")
    failure_type = str(trace.get("failure_type") or trace.get("error_type") or trace.get("bucket") or "").lower()
    pred = str(trace.get("prediction") or trace.get("pred") or "")
    target = str(trace.get("target") or trace.get("label") or "")
    evidence_state = str(trace.get("evidence_state") or "").lower()
    route = str(trace.get("route") or trace.get("dataset_route") or "")
    surface = str(trace.get("surface") or trace.get("repair_surface") or trace.get("objective_family") or "")
    text = _text(trace)
    reasons: list[str] = []

    if trace.get("target_over_decoder_budget") or "long_output" in failure_type or "html" in text:
        action = "HOLDOUT_LONG_OUTPUT"
        reasons.append("long_or_budget_bad_output")
    elif trace.get("leak_detected") or "internal_token" in text or "leak" in failure_type:
        action = "ADD_VERIFIER_REPAIR_ROW"
        reasons.append("internal_or_surface_leak_failure")
    elif trace.get("missing_source_evidence") or evidence_state in {"missing", "insufficient", "evidence_removed"}:
        action = "REQUEST_SOURCE_EVIDENCE"
        reasons.append("missing_or_insufficient_evidence")
    elif trace.get("high_confidence_wrong") or failure_type in {"label_conflict", "high_confidence_wrong"}:
        action = "RELABEL_OR_REVIEW"
        reasons.append("high_confidence_wrong_or_label_conflict")
    elif pred and target and pred != target:
        if "retrieve" in pred.lower() or "retrieve" in target.lower():
            action = "ADD_RETRIEVAL_NEGATIVE"
            reasons.append("retrieve_boundary_confusion")
        elif "unsafe" in pred.lower() or "unsafe" in target.lower() or "safe" in pred.lower() or "safe" in target.lower():
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert eval failure traces into dataset patch operations.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    card = build_patch_card(read_jsonl(args.manifest))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
