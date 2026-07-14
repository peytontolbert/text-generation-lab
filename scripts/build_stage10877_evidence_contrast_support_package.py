#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10877
NAME = "stage10877_evidence_contrast_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "evidence_contrast_support_package.json"
TRAIN_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_ROWS_JSONL = OUT_DIR / "added_evidence_contrast_rows.jsonl"

BASE_DIR = ARTIFACTS / "stage10864_residual_family_support_package_plus_second_python_materialized"
BASE_SUMMARY = BASE_DIR / "residual_family_support_package_plus_second_python_materialized.json"
BASE_TRAIN = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

LABELS = ["A", "B"]
SCARCE_GOLDS = {"symptom_or_call_path_analogue", "verifier_and_test_constraint"}


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


def option_lookup(row: dict[str, Any]) -> dict[str, str]:
    return {str(opt["value"]): str(opt["label"]) for opt in (row.get("opaque_options") or [])}


def prompt_without_answer(row: dict[str, Any]) -> str:
    prompt = str(row.get("prompt_text") or "")
    return prompt.rstrip()


def make_pairwise_row(
    row: dict[str, Any],
    *,
    positive_value: str,
    negative_value: str,
    route: str,
    contrast_kind: str,
) -> dict[str, Any]:
    pairs = [
        {"label": LABELS[0], "value": positive_value},
        {"label": LABELS[1], "value": negative_value},
    ]
    prompt_text = (
        f"{prompt_without_answer(row)}\n"
        "Pairwise evidence contrast:\n"
        f"A. {positive_value}\n"
        f"B. {negative_value}\n"
        "Which evidence candidate is more decisively supported by the visible maintainer evidence?\n"
        "Answer:\n"
    )
    return {
        "abstention_heavy": False,
        "anti_cheat": {
            **(row.get("anti_cheat") or {}),
            "pairwise_evidence_contrast": True,
            "same_surface_eval_admissible": False,
            "non_promotable_support_only": True,
        },
        "bundle_id": row.get("bundle_id"),
        "decoder_text": "A",
        "disable_losses": ["denoise_ce", "runtime_reward", "structured_aux"],
        "expected_answer_kind": "opaque_choice",
        "expected_enabled_loss": "decoder_ce",
        "expected_label": "A",
        "gold_value": positive_value,
        "input_text": prompt_text,
        "language_family": row.get("language_family"),
        "loss_mask": {"decoder_ce": True},
        "objective_family": "bounded_decoder_ce",
        "opaque_options": pairs,
        "perspective": "evidence_pairwise_contrast",
        "prompt_text": prompt_text,
        "query_text": f"{row.get('query_text', row['row_id'])}::{contrast_kind}",
        "repo_family": row.get("repo_family"),
        "repo_id": row.get("repo_id"),
        "route": route,
        "row_id": f"{row['row_id']}::{contrast_kind}",
        "selected_test_anchor": row.get("selected_test_anchor"),
        "semantic_key": "evidence_pairwise_contrast",
        "source_bundle_id": row.get("source_bundle_id"),
        "source_heldout_admissible": False,
        "source_row_id": row.get("source_row_id", row["row_id"]),
        "split": "train",
        "split_role": "train_support",
        "standalone_projection_source": {
            "projection_mode": "stage10877_evidence_pairwise_contrast_v1",
            "base_task_type": row.get("task_type"),
            "base_gold_value": ((row.get("standalone_projection_source") or {}).get("gold_value")),
            "positive_value": positive_value,
            "negative_value": negative_value,
            "contrast_kind": contrast_kind,
        },
        "strict_eval_eligible": False,
        "support_package_stage": STAGE,
        "surface": "maintainer_bundle_compact_bounded_choice",
        "target_text": "A",
        "target_token_len": 1,
        "task_type": "evidence_pairwise_contrast",
        "train_support_only": True,
        "verifier_anchor": row.get("verifier_anchor"),
    }


def main() -> None:
    base_summary = load_json(BASE_SUMMARY)
    base_train = load_jsonl(BASE_TRAIN)
    base_validation = load_jsonl(BASE_VALIDATION)
    base_strict = load_jsonl(BASE_STRICT)
    base_stress = load_jsonl(BASE_STRESS)

    evidence_rows = [row for row in base_train if row.get("task_type") == "evidence_citation"]
    added_rows: list[dict[str, Any]] = []
    counts_by_language = Counter()
    counts_by_kind = Counter()

    candidate_change_calibration_added = set()

    for row in evidence_rows:
        gold_value = str(((row.get("standalone_projection_source") or {}).get("gold_value")) or "")
        value_to_label = option_lookup(row)
        if gold_value in SCARCE_GOLDS and "candidate_change_surface" in value_to_label:
            contrast_kind = f"contrast::{gold_value}__vs__candidate_change_surface"
            added_rows.append(
                make_pairwise_row(
                    row,
                    positive_value=gold_value,
                    negative_value="candidate_change_surface",
                    route="evidence_contrast_scarce_gold",
                    contrast_kind=contrast_kind,
                )
            )
            counts_by_language[str(row.get("language_family") or "unknown")] += 1
            counts_by_kind[gold_value] += 1
        elif gold_value == "candidate_change_surface":
            language = str(row.get("language_family") or "unknown")
            if language in candidate_change_calibration_added:
                continue
            if "verifier_and_test_constraint" not in value_to_label:
                continue
            contrast_kind = "contrast::candidate_change_surface__vs__verifier_and_test_constraint"
            added_rows.append(
                make_pairwise_row(
                    row,
                    positive_value="candidate_change_surface",
                    negative_value="verifier_and_test_constraint",
                    route="evidence_contrast_candidate_change_calibration",
                    contrast_kind=contrast_kind,
                )
            )
            candidate_change_calibration_added.add(language)
            counts_by_language[language] += 1
            counts_by_kind["candidate_change_surface_calibration"] += 1

    merged_train = list(base_train) + added_rows
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(added_rows),
        "decision": "evidence_contrast_support_package_ready",
        "claim_scope": [
            "Add pairwise evidence-contrast supervision that directly pits scarce gold evidence roles against candidate_change_surface as a hard negative.",
            "Use only a small calibration slice in the opposite direction so train does not drift further toward surface dominance.",
        ],
        "source_package": rel(BASE_SUMMARY),
        "metrics": {
            "base_train_rows": len(base_train),
            "base_evidence_rows": len(evidence_rows),
            "added_rows": len(added_rows),
            "merged_train_rows": len(merged_train),
            "rows_by_language": dict(sorted(counts_by_language.items())),
            "rows_by_kind": dict(sorted(counts_by_kind.items())),
            "base_metrics_snapshot": base_summary.get("metrics"),
        },
        "anti_cheat_contract": [
            "All contrast rows are train-support only and remain non-promotable.",
            "Rows use only visible row-local evidence values already present in the original options.",
            "No heldout row is modified; validation and strict stay frozen.",
        ],
        "next_best_steps": [
            "Run a diagnostic probe initialized from the stage10870 runtime so only evidence-contrast geometry changes.",
            "Track strict Rust evidence_citation and eval Python/C++ verifier-constraint evidence rows separately.",
            "If this helps, rebuild fresh heldout evidence roots with the same contrast geometry rather than replaying current eval rows.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_ROWS_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_ROWS_JSONL),
            "strict_rows_jsonl": rel(STRICT_ROWS_JSONL),
            "stress_rows_jsonl": rel(STRESS_ROWS_JSONL),
            "added_rows_jsonl": rel(ADDED_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_jsonl(TRAIN_ROWS_JSONL, merged_train)
    write_jsonl(VALIDATION_ROWS_JSONL, base_validation)
    write_jsonl(STRICT_ROWS_JSONL, base_strict)
    write_jsonl(STRESS_ROWS_JSONL, base_stress)
    write_jsonl(ADDED_ROWS_JSONL, added_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
