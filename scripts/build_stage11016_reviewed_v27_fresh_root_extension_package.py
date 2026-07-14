#!/usr/bin/env python3
"""Build a fresh-root extension package on top of the reviewed v2.7 baseline.

Principles:
- Preserve the current reviewed-v2.7 train/validation/strict/stress splits.
- Add only honest abstention-safe fresh support rows into train.
- Keep fresh scoreable Rust rows out of train and expose them as a separate
  successor-eval slice.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
BASE_DIR = ROOT / "runs/local/artifacts/stage10881_evidence_alias_quarantine_successor"
FRESH_ROWS_PATH = ROOT / "runs/local/artifacts/stage11015_ai_adjudicated_fresh_root_package/ai_adjudicated_fresh_root_rows.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts/stage11016_reviewed_v27_fresh_root_extension_package"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=True) for r in rows) + "\n")


def make_abstention_support_row(row: dict[str, Any]) -> dict[str, Any]:
    view = row["packet_view"]
    candidate_choices = view["candidate_choices"]
    lines = [
        f"Language: {row['language_family']}",
        "Perspective: abstention_insufficient_evidence",
        "Task: Decide whether the visible evidence supports a unique candidate or whether abstention is more honest.",
        "Evidence:",
    ]
    for idx, snippet in enumerate(view["visible_evidence"], start=1):
        lines.append(f"visible_evidence_{idx}: {snippet}")
    lines.append("Options:")
    opaque_options = []
    used_labels = []
    for choice in candidate_choices:
        label = choice["candidate_id"]
        used_labels.append(label)
        value = f"CANDIDATE::{label}"
        opaque_options.append({"label": label, "value": value})
        lines.append(f"{label}. {value}")
    abstain_label = "Z" if "Z" not in used_labels else "Y"
    opaque_options.append({"label": abstain_label, "value": "ABSTAIN_INSUFFICIENT_EVIDENCE"})
    lines.append(f"{abstain_label}. ABSTAIN_INSUFFICIENT_EVIDENCE")
    lines.append("Answer:")
    input_text = "\n".join(lines) + "\n"
    return {
        "row_id": row["materialized_id"],
        "source_root_id": row["materialized_id"],
        "source_bundle_id": row.get("review_packet_dir") or row.get("bundle_id") or row["materialized_id"],
        "repo_id": row["repo_id"],
        "repo_family": row["repo_id"],
        "language_family": row["language_family"],
        "surface": row.get("successor_template") or "fresh_root_abstention_support",
        "task_type": "abstention_insufficient_evidence",
        "input_text": input_text,
        "prompt_text": input_text,
        "query_text": "Decide whether abstention is more honest than forcing a singleton candidate.",
        "target_text": abstain_label,
        "decoder_text": abstain_label,
        "target_token_len": 1,
        "opaque_options": opaque_options,
        "objective_family": "bounded_decoder_ce",
        "disable_losses": ["denoise_ce", "runtime_reward", "structured_aux"],
        "expected_enabled_loss": "decoder_ce",
        "loss_mask": {"decoder_ce": True},
        "package_source_kind": "fresh_root_support_extension",
        "package_split": "train",
        "split": "train",
        "split_role": "train_support_extension",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "selected_test_anchor": bool(view.get("selected_tests")),
        "verifier_anchor": bool(view.get("selected_tests")),
        "abstention_heavy": True,
        "standalone_projection_source": {"opaque_options": opaque_options, "source_stage": "stage11015_ai_adjudicated_fresh_root_package"},
        "anti_cheat": {
            "compact_prompt_contract": True,
            "opaque_labels": True,
            "fresh_root_extension": True,
            "repo_overlap_stress_only": row["language_family"] == "web_js_ts_html",
            "reviewed_bundle_source": bool(row.get("review_packet_dir")),
            "same_surface_eval_admissible": False,
            "ai_adjudicated_support_only": True,
            "prompt_target_leak": False,
        },
    }


def build_rust_successor_eval_row(row: dict[str, Any]) -> dict[str, Any] | None:
    perspective = row["perspective"]
    if perspective not in {"symptom_localization", "evidence_citation"}:
        return None

    if perspective == "symptom_localization":
        values = row["candidate_paths"]
        task = "Choose the most justified edit target from the visible evidence."
        query = "Pick the candidate path that best matches the visible maintenance evidence."
        task_type = "symptom_localization"
    else:
        values = row["visible_evidence_keys"]
        task = "Choose the visible evidence key that best supports the answer."
        query = "Pick the decisive evidence key from the visible evidence ledger."
        task_type = "evidence_citation"

    labels = [chr(ord("A") + i) for i in range(len(values))]
    opaque_options = [{"label": label, "value": value} for label, value in zip(labels, values)]
    try:
        target_idx = values.index(row["gold_answer_value"])
    except ValueError:
        return None
    target_label = labels[target_idx]

    lines = [
        "Language: rust",
        f"Perspective: {perspective}",
        f"Task: {task}",
        "Evidence:",
    ]
    for key in row["visible_evidence_keys"]:
        lines.append(f"{key}")
    lines.append("Candidates:")
    for option in opaque_options:
        lines.append(f"{option['label']}. {option['value']}")
    lines.append("Answer:")
    input_text = "\n".join(lines) + "\n"
    return {
        "row_id": row["materialized_id"],
        "source_root_id": row["bundle_id"],
        "source_bundle_id": row["bundle_id"],
        "repo_id": row["repo_id"],
        "repo_family": row["repo_id"],
        "language_family": "rust",
        "surface": "fresh_rust_successor_eval",
        "task_type": task_type,
        "input_text": input_text,
        "prompt_text": input_text,
        "query_text": query,
        "target_text": target_label,
        "decoder_text": target_label,
        "target_token_len": 1,
        "opaque_options": opaque_options,
        "objective_family": "bounded_decoder_ce",
        "disable_losses": ["denoise_ce", "runtime_reward", "structured_aux"],
        "expected_enabled_loss": "decoder_ce",
        "loss_mask": {"decoder_ce": False},
        "package_source_kind": "fresh_rust_successor_eval",
        "package_split": "successor_eval",
        "split": "successor_eval",
        "split_role": "fresh_root_successor_eval",
        "train_support_only": False,
        "strict_eval_eligible": True,
        "source_heldout_admissible": True,
        "selected_test_anchor": bool(row.get("selected_tests")),
        "verifier_anchor": False,
        "abstention_heavy": False,
        "standalone_projection_source": {"opaque_options": opaque_options, "source_stage": "stage11015_ai_adjudicated_fresh_root_package"},
        "anti_cheat": {
            "compact_prompt_contract": True,
            "opaque_labels": True,
            "fresh_root_extension": True,
            "reviewed_bundle_source": True,
            "same_surface_eval_admissible": False,
            "non_tokenizers_rust_successor": True,
            "prompt_target_leak": False,
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    base_package = read_json(BASE_DIR / "evidence_alias_quarantine_successor.json")
    base_train = read_jsonl(BASE_DIR / "agentkernel_lite_encdec_train.jsonl")
    base_validation = read_jsonl(BASE_DIR / "agentkernel_lite_encdec_validation.jsonl")
    base_strict = read_jsonl(BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl")
    base_stress = read_jsonl(BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl")
    fresh_rows = read_jsonl(FRESH_ROWS_PATH)

    support_rows = []
    successor_eval_rows = []
    quarantined_rows = []

    for row in fresh_rows:
        usage = row["usage_class"]
        if usage in {"ai_adjudicated_abstention_support", "abstention_or_support_only", "support_only_overlap"}:
            support_rows.append(make_abstention_support_row(row))
            continue
        successor = build_rust_successor_eval_row(row)
        if successor is not None:
            successor_eval_rows.append(successor)
        else:
            quarantined_rows.append(row)

    merged_train = base_train + support_rows

    write_jsonl(OUT_DIR / "agentkernel_lite_encdec_train.jsonl", merged_train)
    write_jsonl(OUT_DIR / "agentkernel_lite_encdec_validation.jsonl", base_validation)
    write_jsonl(OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl", base_strict)
    write_jsonl(OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl", base_stress)
    write_jsonl(OUT_DIR / "agentkernel_lite_encdec_successor_eval.jsonl", successor_eval_rows)
    write_jsonl(OUT_DIR / "quarantined_extension_rows.jsonl", quarantined_rows)

    usage_counts = Counter(r["usage_class"] for r in fresh_rows)
    successor_task_counts = Counter(r["task_type"] for r in successor_eval_rows)
    successor_lang_counts = Counter(r["language_family"] for r in successor_eval_rows)
    support_lang_counts = Counter(r["language_family"] for r in support_rows)
    support_repo_counts = Counter(r["repo_family"] for r in support_rows)

    summary = {
        "stage": 11016,
        "stage_name": "reviewed_v27_fresh_root_extension_package",
        "source_artifacts": {
            "base_package": str(BASE_DIR / "evidence_alias_quarantine_successor.json"),
            "fresh_rows": str(FRESH_ROWS_PATH),
        },
        "preserved_baseline": {
            "train_rows": len(base_train),
            "validation_rows": len(base_validation),
            "strict_eval_rows": len(base_strict),
            "stress_eval_rows": len(base_stress),
        },
        "extension_additions": {
            "train_support_rows_added": len(support_rows),
            "successor_eval_rows_added": len(successor_eval_rows),
            "quarantined_extension_rows": len(quarantined_rows),
        },
        "support_extension_breakdown": {
            "language_counts": dict(support_lang_counts),
            "repo_family_counts": dict(support_repo_counts),
        },
        "successor_eval_breakdown": {
            "language_counts": dict(successor_lang_counts),
            "task_type_counts": dict(successor_task_counts),
        },
        "fresh_usage_class_counts": dict(usage_counts),
        "claim_scope": {
            "preserve_current_v27_headline": True,
            "fresh_multilingual_support_added_to_train_only": True,
            "fresh_scoreable_successor_eval_is_currently_rust_only": True,
            "python_successor_rows_converted_to_abstention_support": True,
        },
        "next_best_step": "Run one bounded probe from this extension package, report baseline 24-row overlay unchanged, and evaluate the separate rust successor slice without mixing it into train or headline strict.",
        "outputs": {
            "package_json": str(OUT_DIR / "reviewed_v27_fresh_root_extension_package.json"),
            "train_rows": str(OUT_DIR / "agentkernel_lite_encdec_train.jsonl"),
            "validation_rows": str(OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"),
            "strict_rows": str(OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"),
            "stress_rows": str(OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"),
            "successor_eval_rows": str(OUT_DIR / "agentkernel_lite_encdec_successor_eval.jsonl"),
            "quarantined_extension_rows": str(OUT_DIR / "quarantined_extension_rows.jsonl"),
        },
        "notes": [
            "This package adds only honest abstention-safe fresh support rows to train.",
            "Fresh reviewed Rust localization/evidence rows are kept as a separate successor-eval slice to avoid contaminating train or overstating a multilingual strict upgrade.",
            "Python fresh-root supply exists but is still not promotable because selected-test evidence remains hidden from the prompt and review artifacts do not establish unique identifiability.",
        ],
    }
    (OUT_DIR / "reviewed_v27_fresh_root_extension_package.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n"
    )


if __name__ == "__main__":
    main()
