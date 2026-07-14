#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage10729_semantic_contrast_probe_audit"

BASELINE_STRICT = ROOT / "runs/local/artifacts/stage10721_frontloaded_python_verifier_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
CURRENT_STRICT = ROOT / "runs/local/artifacts/stage10728_semantic_contrast_probe_request/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
CURRENT_EXECUTION = ROOT / "runs/local/artifacts/stage10728_semantic_contrast_probe_request/bounded_decoder_probe/execution_result.json"
REPRESENTATION_AUDIT = ROOT / "runs/local/artifacts/stage10723_mirrormind_tokenizers_representation_audit/mirrormind_tokenizers_representation_audit.json"
SUPPORT_PACKAGE = ROOT / "runs/local/artifacts/stage10727_semantic_contrast_support_package/semantic_contrast_support_package.json"
PROBE_REQUEST = ROOT / "runs/local/artifacts/stage10728_semantic_contrast_probe_request/semantic_contrast_probe_request.json"

PYTHON_ROW_ID = (
    "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_"
    "019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_"
    "mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::verifier_outcome::reviewed_v27_compact"
)
RUST_ROW_ID = "stage10126::tokenizers::tokenizers::rust::evidence_citation::reviewed_v27_compact"


def load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def strict_row_map(strict_audit: dict) -> dict[str, dict]:
    return {row["row_id"]: row for row in strict_audit["row_cards"]}


def parse_language_and_task(row_id: str) -> tuple[str, str]:
    parts = row_id.split("::")
    languages = {"python", "rust", "c_cpp", "web_js_ts_html"}
    for idx, part in enumerate(parts):
        if part in languages and idx + 1 < len(parts):
            return part, parts[idx + 1]
    return "unknown", "unknown"


def language_breakdown(strict_audit: dict) -> dict[str, dict]:
    counts: dict[str, dict] = {}
    for row in strict_audit["row_cards"]:
        language, _ = parse_language_and_task(row["row_id"])
        entry = counts.setdefault(language, {"rows": 0, "correct": 0})
        entry["rows"] += 1
        if row["constrained_choice_match"]:
            entry["correct"] += 1
    for language, entry in counts.items():
        entry["accuracy"] = entry["correct"] / entry["rows"] if entry["rows"] else 0.0
    return counts


def miss_rows(strict_audit: dict) -> list[dict]:
    rows = []
    for row in strict_audit["row_cards"]:
        if row["constrained_choice_match"]:
            continue
        rows.append(
            {
                "row_id": row["row_id"],
                "language_family": parse_language_and_task(row["row_id"])[0],
                "task_type": parse_language_and_task(row["row_id"])[1],
                "predicted_label": row["constrained_choice_top1_label"],
                "target_text": row["target_text"],
                "target_rank_full_vocab": row["target_rank_full_vocab"],
                "full_vocab_top1_text": row["full_vocab_top1_text"],
                "option_labels": row["option_labels"],
            }
        )
    return rows


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    baseline_strict = load_json(BASELINE_STRICT)
    current_strict = load_json(CURRENT_STRICT)
    current_execution = load_json(CURRENT_EXECUTION)
    representation_audit = load_json(REPRESENTATION_AUDIT)
    support_package = load_json(SUPPORT_PACKAGE)
    probe_request = load_json(PROBE_REQUEST)

    baseline_rows = strict_row_map(baseline_strict)
    current_rows = strict_row_map(current_strict)

    baseline_acc = baseline_strict["constrained_choice_top1_accuracy"]
    current_acc = current_strict["constrained_choice_top1_accuracy"]

    python_before = baseline_rows[PYTHON_ROW_ID]
    python_after = current_rows[PYTHON_ROW_ID]
    rust_before = baseline_rows[RUST_ROW_ID]
    rust_after = current_rows[RUST_ROW_ID]

    python_representation = representation_audit["families"]["python_mirrormind_verifier"]
    rust_representation = representation_audit["families"]["rust_tokenizers_citation"]

    result = {
        "stage": 10729,
        "stage_name": "stage10729_semantic_contrast_probe_audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "decision": "semantic_contrast_probe_completed_no_headline_lift",
        "claim_boundary": [
            "Stage10728 executed cleanly after the flash-attn contract repair and wrote all required runtime artifacts.",
            "The semantic-contrast support package preserved the reviewed strict frontier but did not improve it.",
            "Both surviving strict residuals remained unchanged, so this run is diagnostic-only and not promotable."
        ],
        "headline": {
            "baseline_strict_accuracy_stage10721": baseline_acc,
            "current_strict_accuracy_stage10728": current_acc,
            "strict_delta": current_acc - baseline_acc,
            "current_eval_accuracy_stage10728": current_execution["bounded_choice_eval"]["eval"]["constrained_choice_top1_accuracy"],
            "current_full_vocab_strict_accuracy_stage10728": current_strict["full_vocab_top1_accuracy"],
            "current_runtime_weights_sha256": current_execution["runtime_model_bundle"]["weights_sha256"],
        },
        "residual_status": {
            "python_verifier_flip_recovered": python_after["constrained_choice_match"],
            "rust_citation_flip_recovered": rust_after["constrained_choice_match"],
            "same_two_reviewed_v27_misses_remain": True,
        },
        "residuals": {
            "python_verifier": {
                "row_id": PYTHON_ROW_ID,
                "target": python_after["target_text"],
                "pred_stage10721": python_before["constrained_choice_top1_label"],
                "pred_stage10728": python_after["constrained_choice_top1_label"],
                "target_rank_full_vocab_stage10721": python_before["target_rank_full_vocab"],
                "target_rank_full_vocab_stage10728": python_after["target_rank_full_vocab"],
                "representation_audit_best_target_rank": python_representation["best_target_rank"],
                "representation_audit_any_flip": bool(python_representation["correct_variants"]),
            },
            "rust_citation": {
                "row_id": RUST_ROW_ID,
                "target": rust_after["target_text"],
                "pred_stage10721": rust_before["constrained_choice_top1_label"],
                "pred_stage10728": rust_after["constrained_choice_top1_label"],
                "target_rank_full_vocab_stage10721": rust_before["target_rank_full_vocab"],
                "target_rank_full_vocab_stage10728": rust_after["target_rank_full_vocab"],
                "representation_audit_best_target_rank": rust_representation["best_target_rank"],
                "representation_audit_any_flip": bool(rust_representation["correct_variants"]),
            },
        },
        "package_effect": {
            "base_train_rows": support_package["metrics"]["base_train_rows"],
            "merged_train_rows": support_package["metrics"]["merged_train_rows"],
            "python_injected_rows": support_package["metrics"]["python_injected_rows"],
            "rust_injected_rows": support_package["metrics"]["rust_injected_rows"],
            "frontloaded_rows": probe_request["frontload_audit"]["frontloaded_prefix_length"],
        },
        "strict_eval_result": {
            "rows": current_strict["rows"],
            "constrained_choice_top1_accuracy": current_strict["constrained_choice_top1_accuracy"],
            "full_vocab_top1_accuracy": current_strict["full_vocab_top1_accuracy"],
            "language_breakdown": language_breakdown(current_strict),
            "miss_summary": {
                "miss_count": len(miss_rows(current_strict)),
                "miss_row_ids": [row["row_id"] for row in miss_rows(current_strict)],
                "miss_rows": miss_rows(current_strict),
            },
        },
        "next_best_steps": [
            "Do not promote stage10728 as a new frontier result because strict accuracy stayed flat at 22/24.",
            "Treat stage10723 plus stage10728 together as evidence that the residuals are semantic-boundary failures, not simple representation or sampling failures.",
            "Scale the next package by fresh disjoint roots: a Python verifier B-vs-C frontier and a Rust citation E-vs-F/non-candidate-surface frontier, rather than more same-surface support mixing."
        ],
        "sources": {
            "baseline_strict_audit": str(BASELINE_STRICT.relative_to(ROOT)),
            "current_strict_audit": str(CURRENT_STRICT.relative_to(ROOT)),
            "current_execution_result": str(CURRENT_EXECUTION.relative_to(ROOT)),
            "representation_audit": str(REPRESENTATION_AUDIT.relative_to(ROOT)),
            "support_package": str(SUPPORT_PACKAGE.relative_to(ROOT)),
            "probe_request": str(PROBE_REQUEST.relative_to(ROOT)),
        },
        "passed": True,
    }

    out_path = ARTIFACT_DIR / "semantic_contrast_probe_audit.json"
    with out_path.open("w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    print(out_path)


if __name__ == "__main__":
    main()
