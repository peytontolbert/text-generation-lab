#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10419
NAME = "stage10419_reviewed_v27_active_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
EVAL_JSONL = OUT_DIR / "agentkernel_lite_encdec_eval.jsonl"
PACKAGE_JSON = OUT_DIR / "reviewed_v27_active_support_package.json"
FLASH_JSONL = OUT_DIR / "rust_flash_attn_active_support_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_PACKAGE = ROOT / "runs/local/artifacts/stage10149_v27_standalone_compact_permutation_balanced_package/standalone_compact_permutation_balanced_package.json"
BASE_TRAIN = ROOT / "runs/local/artifacts/stage10149_v27_standalone_compact_permutation_balanced_package/agentkernel_lite_encdec_train.jsonl"
BASE_EVAL = ROOT / "runs/local/artifacts/stage10149_v27_standalone_compact_permutation_balanced_package/agentkernel_lite_encdec_eval.jsonl"

PYTHON_SUPPORT_REQ = ROOT / "runs/local/artifacts/stage10327_python_mirrormind_replenishment_execution_request/python_mirrormind_replenishment_execution_request.json"
PYTHON_SUPPORT_ROWS = ROOT / "runs/local/artifacts/stage10327_python_mirrormind_replenishment_execution_request/python_mirrormind_replenishment_train_rows.jsonl"

FLASH_BUNDLE = ROOT / "runs/local/artifacts/stage10413_fresh_rust_flash_attn_preview/fresh_rust_flash_attn_preview_bundle.json"
FLASH_GOLD = ROOT / "runs/local/artifacts/stage10415_rust_flash_attn_review_packets/review_packets/stage10413__candle__candle-flash-attn__rust/perspective_gold_adjudication.json"
FLASH_RUBRIC = ROOT / "runs/local/artifacts/stage10415_rust_flash_attn_review_packets/review_packets/stage10413__candle__candle-flash-attn__rust/expert_maintainer_rubric_review.json"
FLASH_ANTI = ROOT / "runs/local/artifacts/stage10415_rust_flash_attn_review_packets/review_packets/stage10413__candle__candle-flash-attn__rust/anti_cheat_review_card.json"

WEB_GAP_AUDIT = ROOT / "runs/local/artifacts/stage10418_pure_web_verifier_anchor_gap_audit/pure_web_verifier_anchor_gap_audit.json"
WEB_STRESS_PACKAGE = ROOT / "runs/local/artifacts/stage10266_code_assist_web_commit_compact_support_package/code_assist_web_commit_compact_support_package.json"

PERM_LIMIT = 4


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compact(text: str, limit: int = 700) -> str:
    clean = " ".join(str(text or "").split())
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + "..."


def rotate(values: list[str], shift: int) -> list[str]:
    if not values:
        return []
    shift = shift % len(values)
    return values[shift:] + values[:shift]


def flash_task_rows() -> list[dict[str, Any]]:
    bundle = load_json(FLASH_BUNDLE)
    gold = load_json(FLASH_GOLD)
    rubric = load_json(FLASH_RUBRIC)
    anti = load_json(FLASH_ANTI)
    evidence = bundle.get("maintainer_visible_evidence") if isinstance(bundle.get("maintainer_visible_evidence"), dict) else {}
    candidate_paths = [str(value) for value in (bundle.get("candidate_paths") or []) if value]
    selected_tests = [str(value) for value in (bundle.get("selected_tests") or []) if value]
    gold_answers = gold.get("perspective_gold_answers") if isinstance(gold.get("perspective_gold_answers"), list) else []
    gold_by_perspective = {str(row.get("perspective") or ""): row for row in gold_answers}

    bounded_perspectives = [
        "symptom_localization",
        "evidence_citation",
        "patch_impact",
        "minimal_fix_selection",
        "abstention_insufficient_evidence",
    ]
    out: list[dict[str, Any]] = []
    excluded: list[str] = []

    for perspective in bounded_perspectives:
        answer = gold_by_perspective.get(perspective) or {}
        gold_kind = str(answer.get("gold_answer_kind") or "")
        gold_value = str(answer.get("gold_answer_value") or "")
        visible_keys = [str(value) for value in (answer.get("visible_evidence_keys") or []) if value]
        if gold_kind == "visible_evidence_key":
            option_values = visible_keys
        elif gold_kind in {"candidate_path", "abstain"}:
            option_values = list(candidate_paths)
            if gold_value == "ABSTAIN_INSUFFICIENT_EVIDENCE" and gold_value not in option_values:
                option_values.append(gold_value)
        else:
            excluded.append(f"{perspective}::unsupported_gold_kind::{gold_kind}")
            continue

        if gold_value not in option_values:
            option_values.append(gold_value)
        if len(option_values) <= 1:
            excluded.append(f"{perspective}::degenerate_option_count_{len(option_values)}")
            continue

        task = str(((bundle.get("perspective_rows") or [])[0] or {}).get("prompt_contract", {}).get("task") or "")
        perspective_task = task
        for row in bundle.get("perspective_rows") or []:
            if isinstance(row, dict) and row.get("perspective") == perspective:
                perspective_task = str(((row.get("prompt_contract") or {}).get("task")) or perspective)
                break

        for shift in range(min(PERM_LIMIT, len(option_values))):
            ordered = rotate(option_values, shift)
            labels = list("ABCDEFGH")[: len(ordered)]
            options = list(zip(labels, ordered))
            label_by_value = {value: label for label, value in options}
            prompt_lines = [
                "Language: rust",
                f"Perspective: {perspective}",
                f"Task: {perspective_task}",
                "Evidence:",
            ]
            for key in visible_keys[:4]:
                for item in (evidence.get(key) or [])[:2]:
                    prompt_lines.append(f"{key} [{item.get('path','')}]: {compact(item.get('text',''))}")
            prompt_lines.append("Options:")
            prompt_lines.extend(f"{label}. {value}" for label, value in options)
            prompt_lines.append("Answer:")
            prompt = "\n".join(prompt_lines) + "\n"

            out.append(
                {
                    "row_id": f"{bundle['bundle_id']}::{perspective}::compact_bounded::perm_{shift:02d}",
                    "language_family": "rust",
                    "route": "KEEP_BOUNDED_DECODER",
                    "objective_family": "bounded_decoder_ce",
                    "surface": "maintainer_bundle_compact_bounded_choice",
                    "task_type": perspective,
                    "split": "train",
                    "prompt_text": prompt,
                    "input_text": prompt,
                    "query_text": f"compact_bounded::rust::{perspective}::{gold_kind}::perm_{shift:02d}",
                    "target_text": label_by_value[gold_value],
                    "decoder_text": label_by_value[gold_value],
                    "target_token_len": len(label_by_value[gold_value].encode("utf-8")),
                    "loss_mask": {"decoder_ce": True},
                    "expected_enabled_loss": "decoder_ce",
                    "disable_losses": ["denoise_ce", "runtime_reward", "structured_aux"],
                    "source_skill_area": "maintainer_bundle_compact_bounded_choice",
                    "source_stage": STAGE,
                    "source_row_id": f"{bundle['bundle_id']}::{perspective}::compact_bounded",
                    "source_bundle_id": bundle["bundle_id"],
                    "semantic_key": f"rust_flash_attn_reviewed_support::{perspective}::perm_{shift:02d}",
                    "anti_cheat": {
                        "compact_prompt_contract": True,
                        "deterministic_option_shuffle": True,
                        "fresh_source_backed_root": True,
                        "reviewed_bundle_source": True,
                        "train_support_only": True,
                        "opaque_labels": True,
                        "not_for_primary_maintainer_claim": True,
                        "same_surface_eval_admissible": False,
                        "expert_rubric_passed": rubric.get("bundle_valid_for_eval") is True,
                        "anti_cheat_review_passed": anti.get("admissible_for_same_surface_comparison") is True,
                    },
                    "authority": {
                        "model_execution_authorized_next": False,
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
                    },
                    "standalone_projection_source": {
                        "projection_stage": STAGE,
                        "projection_mode": "compact_bounded_choice_auxiliary",
                        "gold_answers_path": display(FLASH_GOLD),
                        "opaque_options": [{"label": label, "value": value} for label, value in options],
                        "original_answer_kind": gold_kind,
                        "gold_value": gold_value,
                        "claim_boundary": {
                            "fresh_reviewed_rust_root": True,
                            "same_surface_eval_admissible": False,
                            "train_support_only": True,
                        },
                    },
                }
            )
    return out


def main() -> None:
    base_package = load_json(BASE_PACKAGE)
    base_train = load_jsonl(BASE_TRAIN)
    base_eval = load_jsonl(BASE_EVAL)
    python_support_request = load_json(PYTHON_SUPPORT_REQ)
    python_support_rows = load_jsonl(PYTHON_SUPPORT_ROWS)
    flash_rows = flash_task_rows()
    web_gap = load_json(WEB_GAP_AUDIT)
    web_stress = load_json(WEB_STRESS_PACKAGE)

    active_train_rows = [*base_train, *python_support_rows, *flash_rows]
    active_eval_rows = list(base_eval)

    write_jsonl(TRAIN_JSONL, active_train_rows)
    write_jsonl(EVAL_JSONL, active_eval_rows)
    write_jsonl(FLASH_JSONL, flash_rows)

    train_language_counts = Counter(str(row.get("language_family") or "") for row in active_train_rows)
    base_train_language_counts = Counter(str(row.get("language_family") or "") for row in base_train)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "base_package": display(BASE_PACKAGE),
        "train_dataset_path": display(TRAIN_JSONL),
        "eval_dataset_path": display(EVAL_JSONL),
        "active_support_additions": [
            {
                "source": display(PYTHON_SUPPORT_REQ),
                "claim_scope": "fresh source-backed python train support only",
                "rows_added": len(python_support_rows),
                "language_family": "python",
                "same_surface_eval_admissible": False,
            },
            {
                "source": display(FLASH_BUNDLE),
                "claim_scope": "fresh reviewed rust train support only",
                "rows_added": len(flash_rows),
                "language_family": "rust",
                "same_surface_eval_admissible": False,
            },
        ],
        "stress_only_or_excluded_support": [
            {
                "source": display(WEB_STRESS_PACKAGE),
                "claim_scope": "repo-overlap web support only; do not merge into active v2.7 support by default",
                "reason": "stage10273 showed large Python and web regressions when the old code_assist web support blend was merged directly",
                "rows_if_enabled": int((web_stress.get("metrics") or {}).get("augmented_train_rows", 0) or 0),
            },
            {
                "source": display(WEB_GAP_AUDIT),
                "claim_scope": "headline web verifier-anchor boundary",
                "reason": "no fresh source-heldout pure-web verifier-anchored candidates currently exist",
            },
        ],
        "metrics": {
            "base_train_rows": len(base_train),
            "base_strict_eval_rows": len(base_eval),
            "python_support_rows_added": len(python_support_rows),
            "rust_support_rows_added": len(flash_rows),
            "final_train_rows": len(active_train_rows),
            "final_strict_eval_rows": len(active_eval_rows),
            "base_train_language_counts": dict(sorted(base_train_language_counts.items())),
            "final_train_language_counts": dict(sorted(train_language_counts.items())),
        },
        "fit_for": {
            "standalone_decoder_ce_training": True,
            "full_product_harness_training": False,
            "expert_maintainer_primary_score": False,
            "compact_bounded_auxiliary_projection_only": True,
        },
        "required_honesty_gates": [
            "strict eval remains unchanged from stage10149",
            "python replenishment rows are train-support only and excluded from headline same-surface Gemma claims",
            "flash-attn rust rows are train-support only and excluded from headline same-surface Gemma claims until independently re-evaluated",
            "repo-overlap web support remains stress-only unless a dedicated regression-safe merge audit passes",
            "freeform maintainer rows remain excluded from compact standalone package",
        ],
        "next_best_step": (
            "Use this active reviewed support package for the next standalone warm-start training candidate, "
            "then audit whether fresh Python and Rust support improve transfer without reopening the known-bad repo-overlap web regression path."
        ),
    }
    write_json(PACKAGE_JSON, summary)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "package": display(PACKAGE_JSON),
            "metrics": summary["metrics"],
        },
    )


if __name__ == "__main__":
    main()
