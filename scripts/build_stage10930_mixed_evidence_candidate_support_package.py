#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10930
NAME = "stage10930_mixed_evidence_candidate_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "mixed_evidence_candidate_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_JSONL = OUT_DIR / "added_mixed_evidence_rows.jsonl"

BASE_DIR = ARTIFACTS / "stage10926_semantic_evidence_multilingual_support_package"
BASE_SUMMARY_JSON = BASE_DIR / "semantic_evidence_multilingual_support_package.json"
BASE_TRAIN_JSONL = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION_JSONL = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT_JSONL = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS_JSONL = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

CANDIDATE_ROWS_JSONL = ARTIFACTS / "stage10826_evidence_role_support_package" / "evidence_role_candidate_rows.jsonl"

TARGET_BUNDLES = {
    "stage10119::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_26t17_53_18_019d2b47_7d2d_7622_8e05_3513_agent_kernel_modeling_ssm_kernels_src_selective_scan_cpp_agent_kernel_modeling_w_5511e7fec6_aug_1500000_8b46e7f662::c_cpp",
    "stage10119::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_56_21_019d3560_1014_7761_9ea7_5638_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_causalmachine_cuda_a018ca0b43_aug_1500000_8b46e7f662::c_cpp",
    "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_26t00_55_44_019abda8_c0d8_7803_8a77_1e0f_scripts_universe_build_py_64d2cf209b_aug_1500000_8b46e7f662::python",
    "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python",
    "stage10413::candle::candle-flash-attn::rust",
    "stage10176::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t13_13_10_019bff96_2dc5_7162_88f8_83eb_src_code_assist_orchestrator_cognitive_perfection_py_src_code_assist_orchestrato_3a0f6d8311_aug_1500000_8b46e7f662::web_js_ts_html",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sanitize_train_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = "train"
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["disable_losses"] = []
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    return updated


def main() -> None:
    base_summary = load_json(BASE_SUMMARY_JSON)
    base_train = [sanitize_train_row(row) for row in load_jsonl(BASE_TRAIN_JSONL)]
    validation_rows = load_jsonl(BASE_VALIDATION_JSONL)
    strict_rows = load_jsonl(BASE_STRICT_JSONL)
    stress_rows = load_jsonl(BASE_STRESS_JSONL)

    candidate_rows = []
    for row in load_jsonl(CANDIDATE_ROWS_JSONL):
        bundle_id = str(row.get("source_bundle_id") or "")
        if bundle_id not in TARGET_BUNDLES:
            continue
        updated = sanitize_train_row(row)
        updated["anti_cheat"] = {
            **(updated.get("anti_cheat") or {}),
            "filtered_selected_test_backed_bundle": True,
            "same_surface_eval_admissible": False,
        }
        candidate_rows.append(updated)

    merged_train = list(base_train) + candidate_rows

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(candidate_rows) and bool(validation_rows) and bool(strict_rows),
        "decision": "mixed_evidence_candidate_support_package_ready",
        "claim_scope": [
            "Add candidate-wise evidence-role supervision from the currently trusted selected-test-backed reviewed bundles on top of the stage10926 multilingual support package.",
            "Move one step closer to the encoder_option_retrieval boundary while leaving the cleaned heldout overlay unchanged.",
        ],
        "required_honesty_gates": [
            "All added candidate-wise evidence rows remain train_support_only and strict_eval_eligible=false.",
            "Validation and strict rows are copied unchanged from stage10926.",
            "Only the currently trusted selected-test-backed reviewed bundles are allowed into the added candidate row set.",
            "The known alias-risk tokenizers evidence lane remains excluded.",
        ],
        "source_artifacts": {
            "base_summary": rel(BASE_SUMMARY_JSON),
            "base_train": rel(BASE_TRAIN_JSONL),
            "base_validation": rel(BASE_VALIDATION_JSONL),
            "base_strict": rel(BASE_STRICT_JSONL),
            "base_stress": rel(BASE_STRESS_JSONL),
            "candidate_rows_source": rel(CANDIDATE_ROWS_JSONL),
        },
        "metrics": {
            "train_rows_before": len(base_train),
            "candidate_rows_added": len(candidate_rows),
            "train_rows_after": len(merged_train),
            "validation_rows_unchanged": len(validation_rows),
            "strict_rows_unchanged": len(strict_rows),
            "stress_rows_unchanged": len(stress_rows),
            "train_by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in merged_train).items())),
            "added_by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in candidate_rows).items())),
            "added_by_role_label": dict(sorted(Counter(str(row.get("target_text") or "unknown") for row in candidate_rows).items())),
            "added_bundle_count": len({str(row.get("source_bundle_id") or "") for row in candidate_rows}),
            "base_metrics_snapshot": base_summary.get("metrics"),
        },
        "interpretation": [
            "This package keeps the semantic support from stage10926 but adds the candidate-wise evidence-role rows that are structurally closer to the retrieval decision boundary.",
            "The added rows are filtered to the same trusted reviewed bundles we are already using for the current evidence successor work, so this does not widen the anti-cheat surface arbitrarily.",
            "Web remains support-only through code_assist overlap, not promotable pure-web heldout evidence.",
        ],
        "next_best_step": "Run a new multilingual probe from the stage10928 runtime, then compare unchanged overlay behavior and the fresh evidence successor slice to see whether the candidate-wise rows move the actual B-vs-F boundary.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
            "added_rows_jsonl": rel(ADDED_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_jsonl(TRAIN_JSONL, merged_train)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)
    write_jsonl(ADDED_JSONL, candidate_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
