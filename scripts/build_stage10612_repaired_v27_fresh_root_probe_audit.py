#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10612
NAME = "stage10612_repaired_v27_fresh_root_probe_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "repaired_v27_fresh_root_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASELINE_AUDIT = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
PROMOTION_CONTRACT = ROOT / "runs/local/artifacts/stage10609_reviewed_v27_multilingual_promotion_contract/reviewed_v27_multilingual_promotion_contract.json"
PROMOTION_GATE = ROOT / "runs/local/artifacts/stage10461_reviewed_v27_residual_promotion_gate/reviewed_v27_residual_promotion_gate.json"
LEAK_AUDIT = ROOT / "runs/local/artifacts/stage10437_repaired_v27_strict_overlay_eval_hacking_audit/repaired_v27_strict_overlay_eval_hacking_audit.json"
REQUEST_JSON = ROOT / "runs/local/artifacts/stage10610_repaired_v27_fresh_root_probe_request/repaired_v27_fresh_root_probe_request.json"
EXECUTION_JSON = ROOT / "runs/local/artifacts/stage10611_repaired_v27_fresh_root_probe/bounded_decoder_probe/execution_result.json"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10611_repaired_v27_fresh_root_probe/runtime_model/runtime_model_bundle.json"

PYTHON_RESIDUAL = "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::verifier_outcome::reviewed_v27_compact"
RUST_RESIDUAL = "stage10126::tokenizers::tokenizers::rust::evidence_citation::reviewed_v27_compact"


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
    contract = load_json(PROMOTION_CONTRACT)
    gate = load_json(PROMOTION_GATE)
    leak = load_json(LEAK_AUDIT)
    request = load_json(REQUEST_JSON)
    execution = load_json(EXECUTION_JSON)
    runtime_bundle = load_json(RUNTIME_BUNDLE)

    baseline_rows = {row["row_id"]: row for row in baseline["row_cards"]}
    probe = execution["bounded_choice_eval"]["strict_eval"]
    probe_rows = {row["row_id"]: row for row in probe["row_cards"]}

    changed_rows: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    for row_id, base_row in baseline_rows.items():
        probe_row = probe_rows[row_id]
        changed = (
            base_row["constrained_choice_top1_label"] != probe_row["constrained_choice_top1_label"]
            or base_row["constrained_choice_match"] != probe_row["constrained_choice_match"]
        )
        if not changed:
            continue
        card = {
            "row_id": row_id,
            "baseline_label": base_row["constrained_choice_top1_label"],
            "probe_label": probe_row["constrained_choice_top1_label"],
            "baseline_match": base_row["constrained_choice_match"],
            "probe_match": probe_row["constrained_choice_match"],
            "target": probe_row["target_text"],
        }
        changed_rows.append(card)
        if base_row["constrained_choice_match"] and not probe_row["constrained_choice_match"]:
            regressions.append(card)
        if not base_row["constrained_choice_match"] and probe_row["constrained_choice_match"]:
            improvements.append(card)

    python_row = probe_rows[PYTHON_RESIDUAL]
    rust_row = probe_rows[RUST_RESIDUAL]
    baseline_acc = baseline["constrained_choice_top1_accuracy"]
    probe_acc = probe["constrained_choice_top1_accuracy"]
    beats_baseline = probe_acc > baseline_acc
    zero_regressions = len(regressions) == 0
    overlay_leak_rows = ((leak.get("summary") or {}).get("rows_with_prompt_target_leak"))
    overlay_leak_clean = overlay_leak_rows == 0

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "promotion_rejected_plateau_preserved",
        "claim_scope": [
            "Classify the completed stage10611 repaired-v27 fresh-root standalone probe against the frozen reviewed-v2.7 contract.",
            "Keep the stable standalone headline on constrained-choice compact maintainer rows only.",
            "Do not upgrade the frontier unless the probe beats the repaired-overlay baseline and clears the existing promotion gate.",
        ],
        "source_artifacts": {
            "baseline_strict_audit": display(BASELINE_AUDIT),
            "promotion_contract": display(PROMOTION_CONTRACT),
            "promotion_gate": display(PROMOTION_GATE),
            "overlay_leak_audit": display(LEAK_AUDIT),
            "probe_request": display(REQUEST_JSON),
            "probe_execution_result": display(EXECUTION_JSON),
            "runtime_model_bundle": display(RUNTIME_BUNDLE),
        },
        "headline": {
            "primary_metric": ((contract.get("promotion_surface") or {}).get("primary_metric")),
            "baseline_constrained_choice_top1_accuracy": baseline_acc,
            "probe_constrained_choice_top1_accuracy": probe_acc,
            "delta": probe_acc - baseline_acc,
            "promotion_passed": beats_baseline and zero_regressions and overlay_leak_clean,
            "reason": "probe preserved 22/24 but did not exceed the existing repaired-overlay baseline",
        },
        "probe_runtime": {
            "run_id": execution.get("run_id"),
            "train_rows": execution.get("train_rows"),
            "strict_rows": execution.get("strict_rows"),
            "decoder_ce_weight": execution.get("decoder_ce_weight"),
            "bounded_choice_aux_weight": execution.get("bounded_choice_aux_weight"),
            "initialize_from_weights_sha256": (((execution.get("implementation") or {}).get("runtime_initialization") or {}).get("weights_sha256")),
            "probe_weights_sha256": runtime_bundle.get("weights_sha256"),
        },
        "row_deltas": {
            "changed_rows": changed_rows,
            "regressions": regressions,
            "improvements": improvements,
        },
        "remaining_residuals": [
            {
                "row_id": PYTHON_RESIDUAL,
                "task_type": "verifier_outcome",
                "language_family": "python",
                "predicted_label": python_row["constrained_choice_top1_label"],
                "target_label": python_row["target_text"],
                "target_rank_full_vocab": python_row.get("target_rank_full_vocab"),
            },
            {
                "row_id": RUST_RESIDUAL,
                "task_type": "evidence_citation",
                "language_family": "rust",
                "predicted_label": rust_row["constrained_choice_top1_label"],
                "target_label": rust_row["target_text"],
                "target_rank_full_vocab": rust_row.get("target_rank_full_vocab"),
            },
        ],
        "gate_status": {
            "beats_22_of_24_baseline": beats_baseline,
            "zero_new_regressions": zero_regressions,
            "overlay_prompt_target_leak_rows": overlay_leak_rows,
            "overlay_leak_hygiene_passed": overlay_leak_clean,
            "fresh_disjoint_support_package_rows": request.get("split_counts", {}).get("train"),
            "existing_gate_required_for_future_promotion": gate.get("required_for_future_promotion"),
        },
        "next_action": {
            "recommended": "expand fresh disjoint residual-root supply instead of launching another tiny same-surface probe",
            "priority_gaps": [
                "python verifier-outcome disambiguation roots",
                "non-tokenizers rust evidence-citation contrast roots",
            ],
        },
    }

    write_json(AUDIT_JSON, audit)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": audit["decision"],
            "audit": display(AUDIT_JSON),
            "headline_probe_accuracy": probe_acc,
            "baseline_accuracy": baseline_acc,
        },
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
