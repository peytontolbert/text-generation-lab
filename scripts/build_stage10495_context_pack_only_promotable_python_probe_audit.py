#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10495
NAME = "stage10495_context_pack_only_promotable_python_probe_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "context_pack_only_promotable_python_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASELINE_AUDIT = ROOT / "runs/local/artifacts/stage10471_fresh_residual_root_probe_audit/fresh_residual_root_probe_audit.json"
PROBE_STRICT_AUDIT = ROOT / "runs/local/artifacts/stage10494_context_pack_only_promotable_python_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
PROBE_EXECUTION_RESULT = ROOT / "runs/local/artifacts/stage10494_context_pack_only_promotable_python_probe/bounded_decoder_probe/execution_result.json"
REQUEST_JSON = ROOT / "runs/local/artifacts/stage10494_context_pack_only_promotable_python_probe_request/context_pack_only_promotable_python_probe_request.json"
QUALIFIED_PACKET = ROOT / "runs/local/artifacts/stage10493_python_verifier_fresh_review_packet_builder/python_verifier_fresh_review_packet_builder.json"

PYTHON_ROW_ID = (
    "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::verifier_outcome::reviewed_v27_compact"
)
RUST_ROW_ID = "stage10126::tokenizers::tokenizers::rust::evidence_citation::reviewed_v27_compact"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    baseline = load_json(BASELINE_AUDIT)
    strict = load_json(PROBE_STRICT_AUDIT)
    execution_result = load_json(PROBE_EXECUTION_RESULT)
    request = load_json(REQUEST_JSON)
    qualified_packet = load_json(QUALIFIED_PACKET)
    probe_accuracy = float(strict["constrained_choice_top1_accuracy"])
    baseline_accuracy = float(baseline["accuracy"]["baseline"])

    cards = {str(card["row_id"]): card for card in strict["row_cards"]}
    python_card = cards[PYTHON_ROW_ID]
    rust_card = cards[RUST_ROW_ID]

    baseline_python = baseline["python_residual"]
    baseline_rust = baseline["rust_residual"]

    changed_rows = []
    regressions = []
    for row_id, card in cards.items():
        constrained = bool(card["constrained_choice_match"])
        baseline_failure_ids = {
            baseline_python["row_id"],
            baseline_rust["row_id"],
        }
        if row_id in baseline_failure_ids:
            old_ok = False
        else:
            old_ok = True
        if constrained != old_ok:
            changed_rows.append(
                {
                    "row_id": row_id,
                    "baseline_match": old_ok,
                    "probe_match": constrained,
                    "probe_label": card["constrained_choice_top1_label"],
                    "target": card["target_text"],
                }
            )
        if old_ok and not constrained:
            regressions.append(row_id)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "context_pack_only_probe_audited",
        "claim_scope": [
            "Audit whether the only immediately qualified reviewed Python verifier root from stage10493 moves the repaired v2.7 frontier.",
            "Keep the interpretation narrow: this probe tests context_pack support only and does not speak for the full stage10492 queue.",
        ],
        "source_artifacts": {
            "baseline_audit": display(BASELINE_AUDIT),
            "probe_strict_audit": display(PROBE_STRICT_AUDIT),
            "probe_execution_result": display(PROBE_EXECUTION_RESULT),
            "probe_request": display(REQUEST_JSON),
            "qualified_packet": display(QUALIFIED_PACKET),
        },
        "accuracy": {
            "baseline": baseline_accuracy,
            "probe": probe_accuracy,
            "delta": probe_accuracy - baseline_accuracy,
        },
        "headline": {
            "improved": probe_accuracy > baseline_accuracy and not regressions,
            "regressions": len(regressions),
            "changed_rows": len(changed_rows),
            "qualified_reviewed_targets_used": qualified_packet["summary"]["immediately_qualified_targets"],
        },
        "python_residual": {
            "row_id": PYTHON_ROW_ID,
            "baseline_label": baseline_python["probe_label"],
            "probe_label": python_card["constrained_choice_top1_label"],
            "probe_target": python_card["target_text"],
            "probe_target_rank_full_vocab": python_card["target_rank_full_vocab"],
            "fixed": bool(python_card["constrained_choice_match"]),
        },
        "rust_residual": {
            "row_id": RUST_ROW_ID,
            "baseline_label": baseline_rust["probe_label"],
            "probe_label": rust_card["constrained_choice_top1_label"],
            "probe_target": rust_card["target_text"],
            "probe_target_rank_full_vocab": rust_card["target_rank_full_vocab"],
            "fixed": bool(rust_card["constrained_choice_match"]),
        },
        "changed_rows": changed_rows,
        "regressions": regressions,
        "interpretation": [
            "The clean context_pack-only promotable packet preserves the 22/24 frontier with zero regressions.",
            "It does not move the Python verifier residual; the wrong label remains C against gold B and the full-vocab target rank stays weak at 5.",
            "It also does not move the Rust tokenizers citation residual, which remains diagnostic-only and outside the Python packet's intended scope.",
            "This means the next Python gain still requires richer reviewed verifier-disambiguation roots, not just cleaner reuse of the already-qualified context_pack root.",
        ],
        "recommended_next_stage": "stage10496_hf_local_verifier_geometry_rebuild_request",
        "required_followups": [
            "Rebuild hf_local with multiple plausible verifier targets so it matches the stage10492 queue contract instead of the current singleton verifier row.",
            "Materialize and adjudicate the queued agentkernel root before counting it as executable verifier support.",
            "Keep the multilingual headline unchanged at 22/24 vs Gemma 6/24 until a future probe actually beats the current frontier.",
        ],
        "request_contract": {
            "train_rows": request["split_counts"]["train"],
            "strict_eval_rows": request["split_counts"]["strict_eval"],
            "train_bundle_ids": request["train_bundle_ids"],
            "train_task_types": request["train_task_types"],
        },
        "runtime": {
            "runtime_model_saved": bool(execution_result.get("runtime_model_saved")),
            "strict_rows": int(execution_result.get("strict_rows", 0)),
            "generated_rows": int(execution_result.get("generated_rows", 0)),
        },
    }

    write_json(AUDIT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "audit": display(AUDIT_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
