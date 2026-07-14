#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "scripts/build_stage11688_routed_web_identity_scorer_audit.py"
spec = importlib.util.spec_from_file_location("stage11688_base", BASE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to load {BASE}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11700_web_verifier_transition_preservation_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_verifier_transition_preservation_postrun_audit.json"

WEB_RUNTIME = ART / "stage11675_web_canonical_same_role_listwise_probe/runtime_model/runtime_model_bundle.json"
IDENTITY_RUNTIME = ART / "stage11699_web_verifier_transition_preservation_probe/runtime_model/runtime_model_bundle.json"
BRIDGED_WEB = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridged_rows.jsonl"
STAGE11691 = ART / "stage11691_original_web_canonical_bridge_gemma_and_anticheat/original_web_canonical_bridge_gemma_and_anticheat.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def eval_rows(rowset_name: str, rows: list[dict[str, Any]], web_model: Any, web_tokenizer: Any, identity_model: Any, identity_tokenizer: Any) -> dict[str, Any]:
    identity_rows = [row for row in rows if base.route(row) == "identity"]
    web_rows = [row for row in rows if base.route(row) == "web"]
    identity_result = base.eval_group(
        name=f"{rowset_name}__identity",
        rows=identity_rows,
        model=identity_model,
        tokenizer=identity_tokenizer,
        scorer=base.IDENTITY_SCORER,
    )
    web_result = base.eval_group(
        name=f"{rowset_name}__web",
        rows=web_rows,
        model=web_model,
        tokenizer=web_tokenizer,
        scorer=base.WEB_SCORER,
    )
    return {
        **base.combine({"identity": identity_result, "web": web_result}),
        "route": "identity_if_same_role_else_web",
        "parts": {"identity": identity_result, "web": web_result},
        "route_counts": {"identity": len(identity_rows), "web": len(web_rows)},
    }


def eval_protected(name: str, path: Path, identity_model: Any, identity_tokenizer: Any) -> dict[str, Any]:
    rows = [base.base.normalize_row(row) for row in base.base.load_jsonl(path)]
    result = base.eval_group(
        name=f"{name}__protected",
        rows=rows,
        model=identity_model,
        tokenizer=identity_tokenizer,
        scorer=base.PROTECTED_SCORER,
    )
    return {**result, "route": "protected", "scorer": base.PROTECTED_SCORER}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    web_model, web_tokenizer, web_init, web_bundle = base.load_runtime(WEB_RUNTIME)
    identity_model, identity_tokenizer, identity_init, identity_bundle = base.load_runtime(IDENTITY_RUNTIME)
    rowsets = {
        "canonical_heldout": ART / "stage11663_web_canonical_renderer_package/web_canonical_heldout.jsonl",
        "bridged_original_web": BRIDGED_WEB,
        "sealed_remaining_miss_diagnostics": ART / "stage11678_web_remaining_miss_counterfactual_builder/web_remaining_canonical_miss_sealed_diagnostics.jsonl",
    }
    results: dict[str, Any] = {}
    for name, path in rowsets.items():
        rows = [base.base.normalize_row(row) for row in base.base.load_jsonl(path)]
        results[name] = eval_rows(name, rows, web_model, web_tokenizer, identity_model, identity_tokenizer)
    protected_paths = {
        "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
        "filtered_validation": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl",
        "old_canary_strict": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
        "old_canary_validation": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl",
        "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
    }
    for name, path in protected_paths.items():
        results[name] = eval_protected(name, path, identity_model, identity_tokenizer)
    gemma = load_json(STAGE11691).get("comparison", {})
    gates = {
        "bridged_web_beats_gemma_56_of_66": results["bridged_original_web"]["correct"] > 56 and results["bridged_original_web"]["rows"] == 66,
        "bridged_web_beats_previous_53_of_66": results["bridged_original_web"]["correct"] > 53 and results["bridged_original_web"]["rows"] == 66,
        "canonical_heldout_at_least_53_of_66": results["canonical_heldout"]["correct"] >= 53 and results["canonical_heldout"]["rows"] == 66,
        "filtered_strict_22_of_22": results["filtered_strict"]["correct"] == 22 and results["filtered_strict"]["rows"] == 22,
        "old_canary_strict_23_of_23": results["old_canary_strict"]["correct"] == 23 and results["old_canary_strict"]["rows"] == 23,
        "filtered_validation_at_least_20_of_22": results["filtered_validation"]["correct"] >= 20 and results["filtered_validation"]["rows"] == 22,
        "old_validation_at_least_21_of_23": results["old_canary_validation"]["correct"] >= 21 and results["old_canary_validation"]["rows"] == 23,
        "residual_at_least_7_of_10": results["residual_bank"]["correct"] >= 7 and results["residual_bank"]["rows"] == 10,
    }
    protected_ok = all(
        gates[key]
        for key in [
            "filtered_strict_22_of_22",
            "old_canary_strict_23_of_23",
            "filtered_validation_at_least_20_of_22",
            "old_validation_at_least_21_of_23",
            "residual_at_least_7_of_10",
        ]
    )
    if gates["bridged_web_beats_gemma_56_of_66"] and protected_ok:
        decision = "web_verifier_transition_preservation_promotable_web_win_candidate"
    elif gates["bridged_web_beats_previous_53_of_66"] and protected_ok:
        decision = "web_verifier_transition_preservation_improves_not_yet_gemma_win"
    elif protected_ok:
        decision = "web_verifier_transition_preservation_preserves_but_no_web_gain"
    else:
        decision = "web_verifier_transition_preservation_rejected_protected_regression"
    summary = {
        "stage": 11700,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "results": results,
        "gates": gates,
        "protected_ok": protected_ok,
        "gemma_stage11691": gemma,
        "runtime": {
            "web_runtime": rel(WEB_RUNTIME),
            "web_runtime_weights_sha256": web_bundle.get("weights_sha256"),
            "identity_runtime": rel(IDENTITY_RUNTIME),
            "identity_runtime_weights_sha256": identity_bundle.get("weights_sha256"),
            "web_runtime_initialization": web_init,
            "identity_runtime_initialization": identity_init,
        },
        "claim_boundary": [
            "This is a routed two-runtime postrun audit: Stage11675 Web head plus Stage11699 identity head.",
            "Promotion requires same-manifest comparison against Stage11691 Gemma and all protected gates preserved.",
        ],
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "compact": {k: {"correct": v["correct"], "rows": v["rows"]} for k, v in results.items()}, "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
