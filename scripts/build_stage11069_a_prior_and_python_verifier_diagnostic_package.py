#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11069
NAME = "stage11069_a_prior_and_python_verifier_diagnostic_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "a_prior_and_python_verifier_diagnostic_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_ROWS_JSONL = OUT_DIR / "added_diagnostic_rows.jsonl"
CONTAMINATED_RESERVED_JSON = OUT_DIR / "contaminated_reserved_rows.json"

BASE_PACKAGE = ARTIFACTS / "stage11061_ready_lane_fresh_support_package"
BASE_SUMMARY = BASE_PACKAGE / "ready_lane_fresh_support_package.json"
BASE_TRAIN = BASE_PACKAGE / "agentkernel_lite_encdec_train.jsonl"
BASE_STRESS = BASE_PACKAGE / "agentkernel_lite_encdec_stress_eval.jsonl"

CLEAN_PACKAGE = ARTIFACTS / "stage11065_singleton_eval_quarantine_package"
CLEAN_VALIDATION = CLEAN_PACKAGE / "agentkernel_lite_encdec_validation.jsonl"
CLEAN_STRICT = CLEAN_PACKAGE / "agentkernel_lite_encdec_strict_eval.jsonl"

PY_SUPPORT_PACKAGE = ARTIFACTS / "stage10904_python_verifier_transition_support_package"
PY_SUPPORT_TRAIN = PY_SUPPORT_PACKAGE / "agentkernel_lite_encdec_train.jsonl"

RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "reserved_residual_candidates.jsonl"

TARGET_RESERVED_ROW_IDS = {
    "stage10938::python_repository_library_evidence_b_vs_f_replenishment::evidence_citation::strict_candidate_explicit_ledger_v1",
    "stage10938::cpp_parametergolf_evidence_b_vs_f_replenishment::evidence_citation::strict_candidate_explicit_ledger_v1",
}

TARGET_LABEL_ORDERS = {
    "F": ["A", "B", "C", "D", "E", "F"],
    "C": ["A", "B", "C", "D", "E", "F"],
    "B": ["A", "B", "C", "D", "E", "F"],
    "D": ["A", "B", "C", "D", "E", "F"],
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


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "missing") for row in rows).items()))


def option_map(row: dict[str, Any]) -> dict[str, str]:
    opts = ((row.get("standalone_projection_source") or {}).get("opaque_options")) or row.get("opaque_options") or []
    return {str(opt.get("label") or ""): str(opt.get("value") or "") for opt in opts if isinstance(opt, dict)}


def reorder_row_to_target_label(row: dict[str, Any], target_label: str, variant_name: str) -> dict[str, Any]:
    values_by_label = option_map(row)
    gold_label = str(row.get("target_text") or "")
    gold_value = values_by_label[gold_label]
    all_values = list(values_by_label.values())
    other_values = [value for value in all_values if value != gold_value]
    ordered_values: list[str] = []
    labels = TARGET_LABEL_ORDERS[target_label]
    other_iter = iter(other_values)
    for label in labels:
        if label == target_label:
            ordered_values.append(gold_value)
        else:
            ordered_values.append(next(other_iter))
    options = [{"label": label, "value": ordered_values[idx]} for idx, label in enumerate(labels)]
    prompt = str(row.get("prompt_text") or "")
    if "Options:\n" not in prompt or "\nAnswer:\n" not in prompt:
        raise ValueError(f"unexpected prompt shape for {row.get('row_id')}")
    prefix, _ = prompt.split("Options:\n", 1)
    prompt = prefix + "Options:\n" + "\n".join(f"{opt['label']}. {opt['value']}" for opt in options) + "\nAnswer:\n"
    updated = dict(row)
    updated["row_id"] = f"stage11069::{row.get('row_id')}::{variant_name}"
    updated["decoder_text"] = target_label
    updated["target_text"] = target_label
    updated["input_text"] = prompt
    updated["prompt_text"] = prompt
    updated["opaque_options"] = options
    updated["split"] = "train"
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["diagnostic_only"] = True
    updated["same_surface_diagnostic_support"] = True
    anti_cheat = dict(updated.get("anti_cheat") or {})
    anti_cheat["same_surface_diagnostic_support"] = True
    anti_cheat["reserved_row_clone"] = True
    anti_cheat["non_promotable"] = True
    anti_cheat["deterministic_option_shuffle"] = True
    updated["anti_cheat"] = anti_cheat
    projection = dict(updated.get("standalone_projection_source") or {})
    projection["source_reserved_row_id"] = row.get("row_id")
    projection["projection_mode"] = "stage11069_reserved_clone_permutation"
    projection["forced_target_label"] = target_label
    updated["standalone_projection_source"] = projection
    return updated


def clone_python_verifier_support(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["row_id"] = f"stage11069::{row.get('row_id')}"
    updated["split"] = "train"
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["diagnostic_only"] = True
    anti_cheat = dict(updated.get("anti_cheat") or {})
    anti_cheat["python_verifier_diagnostic_support"] = True
    anti_cheat["non_promotable"] = True
    updated["anti_cheat"] = anti_cheat
    projection = dict(updated.get("standalone_projection_source") or {})
    projection["projection_mode"] = "stage11069_python_verifier_support_clone"
    updated["standalone_projection_source"] = projection
    return updated


def main() -> None:
    base_summary = load_json(BASE_SUMMARY)
    base_train = load_jsonl(BASE_TRAIN)
    base_stress = load_jsonl(BASE_STRESS)
    clean_validation = load_jsonl(CLEAN_VALIDATION)
    clean_strict = load_jsonl(CLEAN_STRICT)
    py_support_rows = load_jsonl(PY_SUPPORT_TRAIN)
    reserved_rows = load_jsonl(RESERVED_ROWS)

    existing_ids = {str(row.get("row_id") or "") for row in base_train}

    py_verifier_rows = [
        clone_python_verifier_support(row)
        for row in py_support_rows
        if str(row.get("task_type") or "") in {"verifier_outcome", "verifier_candidate_role_classification"}
    ]

    reserved_by_id = {str(row.get("row_id") or ""): row for row in reserved_rows}
    cloned_evidence_rows: list[dict[str, Any]] = []
    contaminated_reserved = []
    for row_id in sorted(TARGET_RESERVED_ROW_IDS):
        source = reserved_by_id[row_id]
        contaminated_reserved.append(
            {
                "reserved_row_id": row_id,
                "language_family": source.get("language_family"),
                "repo_family": source.get("repo_family"),
                "task_type": source.get("task_type"),
            }
        )
        for target_label in ["B", "C", "D", "F"]:
            if target_label == str(source.get("target_text") or ""):
                variant = f"forced_{target_label}_gold"
                cloned_evidence_rows.append(reorder_row_to_target_label(source, target_label, variant))
            elif target_label != "A":
                # Only keep valid force targets that are present in the option alphabet.
                variant = f"forced_{target_label}_position"
                cloned_evidence_rows.append(reorder_row_to_target_label(source, target_label, variant))

    added_rows = [*py_verifier_rows, *cloned_evidence_rows]
    deduped_added_rows = [row for row in added_rows if str(row.get("row_id") or "") not in existing_ids]
    train_rows = [*base_train, *deduped_added_rows]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(deduped_added_rows),
        "decision": "a_prior_and_python_verifier_diagnostic_package_ready",
        "claim_scope": [
            "Create a diagnostic-only support package aimed at two surviving failure mechanisms: explicit-ledger evidence rows that collapse to label A and the remaining Python verifier-transition boundary.",
            "Keep the cleaned 22-row validation and 22-row strict surfaces unchanged as the main canary while explicitly marking the affected reserved candidate rows as contaminated for this diagnostic branch.",
        ],
        "source_artifacts": {
            "base_support_package": rel(BASE_SUMMARY),
            "clean_validation": rel(CLEAN_VALIDATION),
            "clean_strict": rel(CLEAN_STRICT),
            "python_verifier_support_train": rel(PY_SUPPORT_TRAIN),
            "reserved_candidates": rel(RESERVED_ROWS),
        },
        "metrics": {
            "train_rows_before": len(base_train),
            "train_rows_after": len(train_rows),
            "rows_added_total": len(deduped_added_rows),
            "python_verifier_rows_added": len(py_verifier_rows),
            "same_surface_evidence_rows_added": len(cloned_evidence_rows),
            "added_by_language": count_by(deduped_added_rows, "language_family"),
            "added_by_task": count_by(deduped_added_rows, "task_type"),
            "added_by_target": count_by(deduped_added_rows, "target_text"),
            "clean_validation_rows": len(clean_validation),
            "clean_strict_rows": len(clean_strict),
            "stress_rows": len(base_stress),
            "base_train_after_stage11061": base_summary.get("metrics", {}).get("train_rows_after"),
        },
        "diagnostic_boundaries": {
            "contaminated_reserved_row_ids": sorted(TARGET_RESERVED_ROW_IDS),
            "clean_reserved_bank_after_exclusion": len(reserved_rows) - len(TARGET_RESERVED_ROW_IDS),
            "python_verifier_source_package": "stage10904_python_verifier_transition_support_package",
            "same_surface_rows_non_promotable": True,
        },
        "findings": [
            "This package deliberately combines the two currently active residual lanes instead of treating evidence and verifier transition as separate sweeps.",
            "The explicit-ledger evidence additions are same-surface diagnostic clones and cannot support a heldout claim; they exist only to test whether the A-prior defect is trainable.",
            "The cleaned validation/strict surfaces remain untouched and are still the only promotable canary for this branch.",
        ],
        "required_honesty_gates": [
            "Do not use the two contaminated reserved candidate rows for postrun generalization claims on this branch.",
            "Any improvement on the same-surface evidence clones is diagnostic only and must not be reported as heldout gain.",
            "Promotion still requires the cleaned 22/22 canary to hold and uncontaminated heldout rows to improve separately.",
        ],
        "next_best_step": "Run one bounded diagnostic probe from the latest clean runtime, report cleaned validation/strict separately, and score only the uncontaminated reserved subset plus the Python verifier strict row for diagnostic movement.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
            "added_rows_jsonl": rel(ADDED_ROWS_JSONL),
            "contaminated_reserved_json": rel(CONTAMINATED_RESERVED_JSON),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, clean_validation)
    write_jsonl(STRICT_JSONL, clean_strict)
    write_jsonl(STRESS_JSONL, base_stress)
    write_jsonl(ADDED_ROWS_JSONL, deduped_added_rows)
    write_json(CONTAMINATED_RESERVED_JSON, contaminated_reserved)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
