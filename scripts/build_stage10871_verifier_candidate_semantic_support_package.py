#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10871
NAME = "stage10871_verifier_candidate_semantic_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "verifier_candidate_semantic_support_package.json"
TRAIN_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_ROWS_JSONL = OUT_DIR / "added_verifier_candidate_rows.jsonl"

BASE_DIR = ARTIFACTS / "stage10864_residual_family_support_package_plus_second_python_materialized"
BASE_SUMMARY = BASE_DIR / "residual_family_support_package_plus_second_python_materialized.json"
BASE_TRAIN = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

ROLE_TO_LABEL = {
    "DIRECT_VERIFIER_TARGET": "A",
    "SIBLING_TEST_DISTRACTOR": "B",
    "ABSTAIN_OPTION": "C",
    "OTHER_CONSTRAINT_DISTRACTOR": "D",
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


def option_map(row: dict[str, Any]) -> dict[str, str]:
    return {str(opt.get("label")): str(opt.get("value")) for opt in (row.get("opaque_options") or [])}


def looks_like_test_target(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in ("test", "tests/", "spec", "benchmark", "profile_", "integration"))


def role_for_candidate(option_value: str, gold_value: str) -> str:
    if option_value == gold_value:
        return "DIRECT_VERIFIER_TARGET"
    if option_value == "ABSTAIN_INSUFFICIENT_EVIDENCE":
        return "ABSTAIN_OPTION"
    if looks_like_test_target(option_value):
        return "SIBLING_TEST_DISTRACTOR"
    return "OTHER_CONSTRAINT_DISTRACTOR"


def build_candidate_prompt(row: dict[str, Any], option: dict[str, str], role: str) -> str:
    return (
        f"{row['prompt_text']}\n"
        f"Candidate under review: {option['label']}. {option['value']}\n"
        "Classify how this verifier candidate relates to the visible changed-path consequence.\n\n"
        "Choices:\n"
        "A. DIRECT_VERIFIER_TARGET\n"
        "B. SIBLING_TEST_DISTRACTOR\n"
        "C. ABSTAIN_OPTION\n"
        "D. OTHER_CONSTRAINT_DISTRACTOR\n"
        "Answer:\n"
    )


def build_candidate_row(row: dict[str, Any], option: dict[str, str], gold_value: str) -> dict[str, Any]:
    role = role_for_candidate(str(option["value"]), gold_value)
    return {
        "abstention_heavy": False,
        "anti_cheat": {
            **(row.get("anti_cheat") or {}),
            "semantic_verifier_candidate_projection": True,
            "same_surface_eval_admissible": False,
            "non_promotable_support_only": True,
        },
        "bundle_id": row.get("bundle_id"),
        "decoder_text": ROLE_TO_LABEL[role],
        "disable_losses": ["denoise_ce", "runtime_reward", "structured_aux"],
        "expected_answer_kind": "opaque_choice",
        "expected_enabled_loss": "decoder_ce",
        "expected_label": ROLE_TO_LABEL[role],
        "gold_value": gold_value,
        "input_text": build_candidate_prompt(row, option, role),
        "language_family": row.get("language_family"),
        "loss_mask": {"decoder_ce": True},
        "objective_family": "bounded_decoder_ce",
        "opaque_options": [{"label": label, "value": name} for name, label in ROLE_TO_LABEL.items()],
        "perspective": "verifier_candidate_role_classification",
        "prompt_text": build_candidate_prompt(row, option, role),
        "query_text": f"{row.get('query_text', row['row_id'])}::candidate::{option['label']}",
        "repo_family": row.get("repo_family"),
        "repo_id": row.get("repo_id"),
        "route": "verifier_candidate_semantic_support",
        "row_id": f"{row['row_id']}::candidate::{option['label']}::verifier_role",
        "selected_test_anchor": row.get("selected_test_anchor"),
        "semantic_key": "verifier_candidate_role",
        "source_bundle_id": row.get("source_bundle_id"),
        "source_heldout_admissible": False,
        "source_row_id": row.get("source_row_id", row["row_id"]),
        "split": "train",
        "split_role": "train_support",
        "standalone_projection_source": {
            "projection_mode": "stage10871_verifier_candidate_role_projection_v1",
            "base_task_type": row.get("task_type"),
            "base_target_label": row.get("target_text"),
            "gold_option_value": gold_value,
            "candidate_label": option["label"],
            "candidate_value": option["value"],
            "derived_role": role,
        },
        "strict_eval_eligible": False,
        "support_package_stage": STAGE,
        "surface": "maintainer_bundle_compact_bounded_choice",
        "target_text": ROLE_TO_LABEL[role],
        "target_token_len": 1,
        "task_type": "verifier_candidate_role_classification",
        "train_support_only": True,
        "verifier_anchor": row.get("verifier_anchor"),
    }


def main() -> None:
    base_summary = load_json(BASE_SUMMARY)
    base_train = load_jsonl(BASE_TRAIN)
    base_validation = load_jsonl(BASE_VALIDATION)
    base_strict = load_jsonl(BASE_STRICT)
    base_stress = load_jsonl(BASE_STRESS)

    added_rows: list[dict[str, Any]] = []
    rows_by_language = Counter()
    rows_by_role = Counter()

    for row in base_train:
        if row.get("task_type") != "verifier_outcome":
            continue
        options = row.get("opaque_options") or []
        if len(options) < 2:
            continue
        label_to_value = option_map(row)
        gold_label = str(row.get("target_text") or "")
        gold_value = label_to_value.get(gold_label)
        if not gold_value:
            continue
        if not (row.get("selected_test_anchor") or row.get("verifier_anchor")):
            continue
        for option in options:
            candidate_row = build_candidate_row(row, {"label": str(option["label"]), "value": str(option["value"])}, gold_value)
            added_rows.append(candidate_row)
            rows_by_language[str(row.get("language_family") or "unknown")] += 1
            rows_by_role[str(candidate_row["target_text"])] += 1

    merged_train = list(base_train) + added_rows

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(added_rows),
        "decision": "verifier_candidate_semantic_support_package_ready",
        "claim_scope": [
            "Augment the current residual-family support package with candidate-wise verifier semantics rather than only opaque verifier answer letters.",
            "Teach the model to separate the direct verifier target from sibling test distractors and abstain alternatives using the same visible evidence surface.",
        ],
        "source_package": rel(BASE_SUMMARY),
        "metrics": {
            "base_train_rows": len(base_train),
            "added_rows": len(added_rows),
            "merged_train_rows": len(merged_train),
            "rows_by_language": dict(sorted(rows_by_language.items())),
            "rows_by_role_label": dict(sorted(rows_by_role.items())),
            "base_verifier_rows": sum(1 for row in base_train if row.get("task_type") == "verifier_outcome"),
            "base_multi_option_verifier_rows": sum(
                1
                for row in base_train
                if row.get("task_type") == "verifier_outcome" and len(row.get("opaque_options") or []) >= 2
            ),
            "base_metrics_snapshot": base_summary.get("metrics"),
        },
        "anti_cheat_contract": [
            "All derived verifier candidate rows are train-support only and remain non-promotable.",
            "Target labels describe verifier-candidate semantics, not the original opaque answer letter.",
            "Rows reuse only currently visible maintainer evidence and candidate options; no hidden post-fix target text is introduced.",
        ],
        "next_best_steps": [
            "Run a diagnostic probe initialized from the saved stage10870 runtime so only the support geometry changes.",
            "Track Python verifier_outcome and Rust evidence_citation deltas separately from headline strict accuracy.",
            "If this improves the Python residual without regressions, rebuild fresh heldout verifier-transition roots with the same semantic candidate interface.",
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
