#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_stage10934_explicit_verifier_ledger_support_package import (
    build_option_pool,
    build_task_line,
    load_json,
    load_jsonl,
    now_utc,
    parse_evidence_map,
    rel,
    relabel_options,
    reorder_options,
    sanitize_train_row,
    split_prompt_sections,
    write_json,
    write_jsonl,
)

ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10941
NAME = "stage10941_scorer_margin_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "scorer_margin_support_package.json"
ADDED_ROWS_JSONL = OUT_DIR / "added_scorer_margin_rows.jsonl"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

BASE_DIR = ARTIFACTS / "stage10934_explicit_verifier_ledger_support_package"
BASE_SUMMARY_JSON = BASE_DIR / "explicit_verifier_ledger_support_package.json"
BASE_TRAIN_JSONL = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION_JSONL = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT_JSONL = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS_JSONL = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

SOURCE_ROWS_JSONL = ARTIFACTS / "stage10828_evidence_role_probe_request" / "evidence_role_probe_manifest.jsonl"

SOURCE_ROW_IDS = [
    "stage10236::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662::python::evidence_citation::reviewed_v27_compact",
    "stage10300::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662::python::evidence_citation::reviewed_v27_compact",
    "stage10674::candle::candle-datasets::evidence_citation::reviewed_v27_compact",
    "stage10733::cccl::q30::evidence_citation::reviewed_v27_compact",
    "stage10733::onnxruntime::q13::evidence_citation::reviewed_v27_compact",
    "stage10733::parametergolf::q2::evidence_citation::reviewed_v27_compact",
    "stage10733::parametergolf::q4::evidence_citation::reviewed_v27_compact",
]


def source_key(row: dict[str, Any]) -> str:
    return str(row.get("row_id") or "")


def load_source_rows() -> list[dict[str, Any]]:
    rows = load_jsonl(SOURCE_ROWS_JSONL)
    wanted = set(SOURCE_ROW_IDS)
    selected = [row for row in rows if source_key(row) in wanted]
    if len(selected) != len(wanted):
        found = {source_key(row) for row in selected}
        missing = sorted(wanted - found)
        raise ValueError(f"missing source evidence rows: {missing}")
    return selected


def existing_gold_value(row: dict[str, Any]) -> str:
    return str((row.get("standalone_projection_source") or {}).get("gold_value") or "")


def rewrite_candidate_line(line: str, gold_value: str) -> str:
    prefix, sep, rest = line.partition("]:")
    if not sep:
        return line
    existing = rest.strip()
    if gold_value == "candidate_change_surface":
        return f"{prefix}]: Changed candidate surface remains the most direct edit anchor. {existing}".strip()
    return f"{prefix}]: Candidate surface remains plausible but can be weaker than the selected-test ledger. {existing}".strip()


def rewrite_verifier_line(line: str, gold_value: str) -> str:
    prefix, sep, rest = line.partition("]:")
    if not sep:
        return line
    existing = rest.strip()
    if gold_value == "verifier_and_test_constraint":
        return f"{prefix}]: Selected-test ledger kept visible. {existing}".strip()
    return f"{prefix}]: Verifier/test ledger is visible but should lose when the changed candidate is the stronger justification. {existing}".strip()


def build_evidence_lines(source_row: dict[str, Any], variant_name: str) -> list[str]:
    prompt = str(source_row.get("prompt_text") or source_row.get("input_text") or "")
    _header, evidence_lines = split_prompt_sections(prompt)
    evidence_map = parse_evidence_map(evidence_lines)
    gold_value = existing_gold_value(source_row)
    if "candidate_change_surface" in evidence_map:
        evidence_map["candidate_change_surface"] = rewrite_candidate_line(evidence_map["candidate_change_surface"], gold_value)
    if "verifier_and_test_constraint" in evidence_map:
        evidence_map["verifier_and_test_constraint"] = rewrite_verifier_line(evidence_map["verifier_and_test_constraint"], gold_value)

    full_order = [
        "algorithmic_background_reference",
        "candidate_change_surface",
        "external_analogue_reference",
        "nearby_definition_or_usage_context",
        "symptom_or_call_path_analogue",
        "verifier_and_test_constraint",
    ]
    contrast_order = [
        "candidate_change_surface",
        "verifier_and_test_constraint",
        "nearby_definition_or_usage_context",
        "symptom_or_call_path_analogue",
    ]
    order = full_order if variant_name.startswith("margin_full") else contrast_order
    if variant_name.endswith("verifier_first"):
        order = ["verifier_and_test_constraint", *[key for key in order if key != "verifier_and_test_constraint"]]
    elif variant_name.endswith("candidate_first"):
        order = ["candidate_change_surface", *[key for key in order if key != "candidate_change_surface"]]
    return [evidence_map[key] for key in order if key in evidence_map]


def build_prompt(source_row: dict[str, Any], variant_name: str, options: list[dict[str, str]]) -> str:
    prompt = str(source_row.get("prompt_text") or source_row.get("input_text") or "")
    header_lines, _evidence_lines = split_prompt_sections(prompt)
    rewritten_header = []
    gold_value = existing_gold_value(source_row)
    for line in header_lines:
        if line.startswith("Task: "):
            rewritten_header.append(build_task_line(gold_value))
        else:
            rewritten_header.append(line)
    evidence_lines = build_evidence_lines(source_row, variant_name)
    option_lines = [f"{item['label']}. {item['value']}" for item in options]
    return "\n".join([*rewritten_header, "Evidence:", *evidence_lines, "Options:", *option_lines, "Answer:", ""])


def build_variant_rows(source_row: dict[str, Any]) -> list[dict[str, Any]]:
    variants = [
        "margin_full_verifier_first",
        "margin_full_candidate_first",
        "margin_contrast_verifier_first",
        "margin_contrast_candidate_first",
    ]
    gold_value = existing_gold_value(source_row)
    rows = []
    for variant_name in variants:
        option_pool = build_option_pool(source_row, variant_name)
        ordered = reorder_options(option_pool, f"{source_key(source_row)}::{variant_name}")
        relabeled = relabel_options(ordered)
        target_label = next((item["label"] for item in relabeled if item["value"] == gold_value), None)
        if target_label is None:
            raise ValueError(f"missing gold value {gold_value} for row {source_key(source_row)}")
        prompt = build_prompt(source_row, variant_name, relabeled)
        rows.append(
            sanitize_train_row(
                {
                    "anti_cheat": {
                        "explicit_selected_test_ledger": True,
                        "opaque_labels": True,
                        "same_surface_eval_admissible": False,
                        "scorer_margin_support_only": True,
                        "source_prompt_rewritten_without_target_path_exposure": True,
                        "train_support_only": True,
                    },
                    "decoder_text": target_label,
                    "input_text": prompt,
                    "language_family": source_row.get("language_family"),
                    "objective_family": "bounded_decoder_ce",
                    "opaque_options": relabeled,
                    "prompt_text": prompt,
                    "query_text": f"scorer_margin_support::{source_row.get('language_family')}::{source_key(source_row)}::{variant_name}",
                    "repo_family": source_row.get("repo_family"),
                    "repo_id": source_row.get("repo_id"),
                    "row_id": f"stage10941::{source_key(source_row)}::{variant_name}",
                    "selected_test_anchor": bool(source_row.get("selected_test_anchor")),
                    "source_bundle_id": source_row.get("source_bundle_id"),
                    "source_heldout_admissible": False,
                    "source_root_id": source_row.get("source_root_id"),
                    "split_role": "train_support_only",
                    "standalone_projection_source": {
                        "gold_value": gold_value,
                        "opaque_options": relabeled,
                        "projection_mode": "stage10941_scorer_margin_support",
                        "source_row_id": source_key(source_row),
                        "variant": variant_name,
                    },
                    "strict_eval_eligible": False,
                    "surface": "maintainer_bundle_compact_bounded_choice",
                    "target_text": target_label,
                    "target_token_len": 1,
                    "task_type": "evidence_citation",
                    "train_support_only": True,
                    "verifier_anchor": bool(source_row.get("verifier_anchor")),
                }
            )
        )
    return rows


def main() -> None:
    base_summary = load_json(BASE_SUMMARY_JSON)
    base_train = [sanitize_train_row(row) for row in load_jsonl(BASE_TRAIN_JSONL)]
    validation_rows = load_jsonl(BASE_VALIDATION_JSONL)
    strict_rows = load_jsonl(BASE_STRICT_JSONL)
    stress_rows = load_jsonl(BASE_STRESS_JSONL)

    source_rows = load_source_rows()
    added_rows: list[dict[str, Any]] = []
    for source_row in source_rows:
        added_rows.extend(build_variant_rows(source_row))

    merged_train = [*base_train, *added_rows]
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(added_rows) and bool(strict_rows),
        "decision": "scorer_margin_support_package_ready",
        "claim_scope": [
            "Add disjoint train-only evidence-citation analogues that preserve the candidate_change_surface vs verifier_and_test_constraint competition while strengthening visible verifier-ledger wording.",
            "Keep the cleaned 23-row overlay and the explicit-ledger 3-row successor slice unchanged for evaluation.",
        ],
        "required_honesty_gates": [
            "All added rows remain train_support_only and strict_eval_eligible=false.",
            "No stage10938 candidate rows are copied into train.",
            "Validation and strict rows are copied unchanged from stage10934.",
            "This package is diagnostic-only and not a promotable new eval surface.",
        ],
        "source_artifacts": {
            "base_summary": rel(BASE_SUMMARY_JSON),
            "base_train": rel(BASE_TRAIN_JSONL),
            "base_validation": rel(BASE_VALIDATION_JSONL),
            "base_strict": rel(BASE_STRICT_JSONL),
            "base_stress": rel(BASE_STRESS_JSONL),
            "source_rows_jsonl": rel(SOURCE_ROWS_JSONL),
            "source_row_ids": SOURCE_ROW_IDS,
        },
        "metrics": {
            "train_rows_before": len(base_train),
            "added_rows": len(added_rows),
            "train_rows_after": len(merged_train),
            "validation_rows_unchanged": len(validation_rows),
            "strict_rows_unchanged": len(strict_rows),
            "stress_rows_unchanged": len(stress_rows),
            "added_by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in added_rows).items())),
            "added_by_target_value": dict(sorted(Counter(str((row.get("standalone_projection_source") or {}).get("gold_value") or "unknown") for row in added_rows).items())),
            "added_by_repo_family": dict(sorted(Counter(str(row.get("repo_family") or "unknown") for row in added_rows).items())),
            "source_rows_by_gold_value": dict(sorted(Counter(existing_gold_value(row) for row in source_rows).items())),
            "base_metrics_snapshot": base_summary.get("metrics"),
        },
        "interpretation": [
            "The prior explicit-ledger repair fixed evidence visibility but left a stable scorer prior favoring candidate_change_surface by roughly 0.056 to 0.058.",
            "This package attacks that measured margin directly with train-only analogue rows instead of replaying the fresh 3-row heldout candidate slice into train.",
            "Python positives come from code_assist verifier-ledger rows, C/C++ controls come from cccl, onnxruntime, and parametergolf candidate-surface rows, and Rust adds one verifier-ledger positive control.",
        ],
        "next_best_step": "Run a scorer-focused probe from the stage10936 runtime with lower preservation KL, then audit both the unchanged overlay and the explicit-ledger 3-row candidate slice for true movement.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "added_rows_jsonl": rel(ADDED_ROWS_JSONL),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_jsonl(ADDED_ROWS_JSONL, added_rows)
    write_jsonl(TRAIN_JSONL, merged_train)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
