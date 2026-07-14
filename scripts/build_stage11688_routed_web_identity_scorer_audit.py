#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "scripts/build_stage11656_same_root_grouped_head_only_postrun_audit.py"
spec = importlib.util.spec_from_file_location("stage11656_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to load base audit helpers: {BASE_PATH}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11688_routed_web_identity_scorer_audit"
OUT = ART / NAME
SUMMARY = OUT / "routed_web_identity_scorer_audit.json"

WEB_RUNTIME = ART / "stage11675_web_canonical_same_role_listwise_probe/runtime_model/runtime_model_bundle.json"
IDENTITY_RUNTIME = ART / "stage11685_counterfactual_identity_semantic_head_fixed_probe/runtime_model/runtime_model_bundle.json"
ROWSETS = {
    "canonical_heldout": ART / "stage11663_web_canonical_renderer_package/web_canonical_heldout.jsonl",
    "original_web_heldout": ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl",
    "sealed_remaining_miss_diagnostics": ART / "stage11678_web_remaining_miss_counterfactual_builder/web_remaining_canonical_miss_sealed_diagnostics.jsonl",
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "old_canary_strict": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "filtered_validation": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl",
    "old_canary_validation": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl",
    "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
}
WEB_SCORER = "encoder_option_retrieval_web_task_candidate_head"
IDENTITY_SCORER = "encoder_option_retrieval_semantic_candidate_head"
PROTECTED_SCORER = "encoder_option_retrieval_evidence_judgment_head"
IDENTITY_TASKS = {"symptom_localization", "minimal_fix_selection", "patch_impact", "verifier_outcome"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_runtime(path: Path) -> tuple[Any, Any, dict[str, Any], dict[str, Any]]:
    old_runtime = base.RUNTIME
    try:
        base.RUNTIME = path
        return base.load_runtime()
    finally:
        base.RUNTIME = old_runtime


def option_role(option: dict[str, Any]) -> str:
    obj = option.get("canonical_candidate_object") if isinstance(option.get("canonical_candidate_object"), dict) else {}
    semantic = option.get("semantic_candidate") if isinstance(option.get("semantic_candidate"), dict) else {}
    return str(option.get("role") or obj.get("role") or semantic.get("role") or "")


def route(row: dict[str, Any]) -> str:
    task = str(row.get("task_type") or "")
    if task not in IDENTITY_TASKS:
        return "web"
    options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or row.get("opaque_options") or [])
    role_counts = Counter(option_role(opt) for opt in options if isinstance(opt, dict))
    role_counts.pop("", None)
    if role_counts and max(role_counts.values()) >= 2:
        return "identity"
    return "web"


def metric_from_card(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "correct": int(card.get("constrained_choice_correct") or 0),
        "rows": int(card.get("constrained_choice_rows") or card.get("rows") or 0),
        "accuracy": card.get("constrained_choice_top1_accuracy"),
        "misses": card.get("misses") or [],
    }


def eval_group(
    *,
    name: str,
    rows: list[dict[str, Any]],
    model: Any,
    tokenizer: Any,
    scorer: str,
) -> dict[str, Any]:
    if not rows:
        return {"correct": 0, "rows": 0, "accuracy": None, "misses": []}
    card = base._write_bounded_choice_eval_audit(
        OUT,
        model=model,
        rows=rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=16,
        split_name=name,
        bounded_choice_aux_source=scorer,
        eval_batch_size=8,
    )
    return metric_from_card(card)


def combine(parts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = sum(part["rows"] for part in parts.values())
    correct = sum(part["correct"] for part in parts.values())
    misses = []
    for part in parts.values():
        misses.extend(part.get("misses") or [])
    return {"correct": correct, "rows": rows, "accuracy": (correct / rows) if rows else None, "misses": misses}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    web_model, web_tokenizer, web_init, web_bundle = load_runtime(WEB_RUNTIME)
    identity_model, identity_tokenizer, identity_init, identity_bundle = load_runtime(IDENTITY_RUNTIME)
    results: dict[str, Any] = {}
    route_counts: dict[str, Any] = {}
    for rowset_name, path in ROWSETS.items():
        rows = [base.normalize_row(row) for row in base.load_jsonl(path)]
        if rowset_name in {"filtered_strict", "old_canary_strict", "filtered_validation", "old_canary_validation", "residual_bank"}:
            protected = eval_group(
                name=f"{rowset_name}__protected",
                rows=rows,
                model=identity_model,
                tokenizer=identity_tokenizer,
                scorer=PROTECTED_SCORER,
            )
            results[rowset_name] = {**protected, "route": "protected", "scorer": PROTECTED_SCORER}
            route_counts[rowset_name] = {"protected": len(rows)}
            continue
        identity_rows = [row for row in rows if route(row) == "identity"]
        web_rows = [row for row in rows if route(row) == "web"]
        identity_result = eval_group(
            name=f"{rowset_name}__identity",
            rows=identity_rows,
            model=identity_model,
            tokenizer=identity_tokenizer,
            scorer=IDENTITY_SCORER,
        )
        web_result = eval_group(
            name=f"{rowset_name}__web",
            rows=web_rows,
            model=web_model,
            tokenizer=web_tokenizer,
            scorer=WEB_SCORER,
        )
        results[rowset_name] = {
            **combine({"identity": identity_result, "web": web_result}),
            "route": "identity_if_same_role_else_web",
            "parts": {"identity": identity_result, "web": web_result},
        }
        route_counts[rowset_name] = {"identity": len(identity_rows), "web": len(web_rows)}
    gates = {
        "canonical_heldout_beats_stage11673_51_of_66": results["canonical_heldout"]["correct"] > 51 and results["canonical_heldout"]["rows"] == 66,
        "original_web_beats_routed_38_of_66": results["original_web_heldout"]["correct"] > 38 and results["original_web_heldout"]["rows"] == 66,
        "sealed_diag_beats_stage11686_5_of_15": results["sealed_remaining_miss_diagnostics"]["correct"] > 5 and results["sealed_remaining_miss_diagnostics"]["rows"] == 15,
        "filtered_strict_22_of_22": results["filtered_strict"]["correct"] == 22 and results["filtered_strict"]["rows"] == 22,
        "old_canary_strict_23_of_23": results["old_canary_strict"]["correct"] == 23 and results["old_canary_strict"]["rows"] == 23,
        "filtered_validation_at_least_20_of_22": results["filtered_validation"]["correct"] >= 20 and results["filtered_validation"]["rows"] == 22,
        "old_validation_at_least_21_of_23": results["old_canary_validation"]["correct"] >= 21 and results["old_canary_validation"]["rows"] == 23,
        "residual_at_least_7_of_10": results["residual_bank"]["correct"] >= 7 and results["residual_bank"]["rows"] == 10,
    }
    protected_ok = all(gates[key] for key in ["filtered_strict_22_of_22", "old_canary_strict_23_of_23", "filtered_validation_at_least_20_of_22", "old_validation_at_least_21_of_23", "residual_at_least_7_of_10"])
    if not protected_ok:
        decision = "routed_identity_rejected_protected_gate_regression"
    elif gates["original_web_beats_routed_38_of_66"]:
        decision = "routed_identity_candidate_web_frontier_gain"
    elif gates["canonical_heldout_beats_stage11673_51_of_66"]:
        decision = "routed_identity_canonical_gain_only"
    else:
        decision = "routed_identity_not_sufficient"
    summary = {
        "stage": 11688,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "web_runtime": rel(WEB_RUNTIME),
        "web_runtime_weights_sha256": web_bundle.get("weights_sha256"),
        "identity_runtime": rel(IDENTITY_RUNTIME),
        "identity_runtime_weights_sha256": identity_bundle.get("weights_sha256"),
        "route_policy": "identity scorer for target-independent same-role candidate competition on selected Web tasks; Web task head otherwise",
        "route_counts": route_counts,
        "results": results,
        "gates": gates,
        "protected_ok": protected_ok,
        "runtime_initialization": {"web": web_init, "identity": identity_init},
        "source_artifacts": {name: rel(path) for name, path in ROWSETS.items()},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
        "claim_boundary": [
            "This is a two-runtime routing audit, not a single packaged product runtime.",
            "It tests whether the fitted identity head can improve heldout routing when applied only to same-role candidate competition rows.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "route_counts": route_counts, "compact": {k: {"correct": v["correct"], "rows": v["rows"]} for k, v in results.items()}, "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
