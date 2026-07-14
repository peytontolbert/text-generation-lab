#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_stage10934_explicit_verifier_ledger_support_package import (
    MANIFEST_ROWS,
    SOURCE_ROW_FILES,
    build_prompt,
    build_variant_rows,
    find_source_row,
    load_gold_by_perspective,
    load_jsonl,
    relabel_options,
    reorder_options,
    build_option_pool,
    write_json,
    write_jsonl,
    rel,
    now_utc,
)

ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10938
NAME = "stage10938_explicit_verifier_ledger_strict_candidates"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "explicit_verifier_ledger_strict_candidates.json"
ROWS_JSONL = OUT_DIR / "strict_candidate_rows.jsonl"
BUNDLE_JSON = OUT_DIR / "strict_candidate_bundle.json"


def build_strict_row(spec: dict[str, Any], source_row: dict[str, Any], gold_by_perspective: dict[str, dict[str, Any]]) -> dict[str, Any]:
    gold_value = str((gold_by_perspective.get("evidence_citation") or {}).get("gold_answer_value") or "")
    variant_name = "ledger_full_verifier_first" if gold_value == "verifier_and_test_constraint" else "ledger_full_candidate_first"
    option_pool = build_option_pool(source_row, variant_name)
    ordered = reorder_options(option_pool, f"strict::{spec['queue_id']}::{variant_name}")
    relabeled = relabel_options(ordered)
    target_label = next((item["label"] for item in relabeled if item["value"] == gold_value), None)
    if target_label is None:
        raise ValueError(f"missing gold value {gold_value} for queue={spec['queue_id']}")
    prompt = build_prompt(spec, source_row, variant_name, relabeled, gold_by_perspective)
    return {
        "anti_cheat": {
            "explicit_selected_test_ledger": True,
            "fresh_successor_candidate_only": True,
            "opaque_labels": True,
            "option_order_changed_from_source": True,
            "reviewed_bundle_source": True,
            "same_surface_eval_admissible": False,
            "target_path_strings_hidden_pre_options": True,
        },
        "decoder_text": target_label,
        "expected_enabled_loss": "decoder_ce",
        "input_text": prompt,
        "language_family": spec.get("language_family"),
        "loss_mask": {"decoder_ce": True},
        "objective_family": "bounded_decoder_ce",
        "opaque_options": relabeled,
        "prompt_text": prompt,
        "query_text": f"strict_candidate_explicit_ledger::{spec.get('language_family')}::{spec['queue_id']}",
        "repo_family": spec.get("repo_id"),
        "repo_id": spec.get("repo_id"),
        "row_id": f"stage10938::{spec['queue_id']}::evidence_citation::strict_candidate_explicit_ledger_v1",
        "selected_test_anchor": bool(spec.get("selected_tests")),
        "source_bundle_id": spec.get("source_bundle_id"),
        "source_heldout_admissible": False,
        "source_root_id": spec.get("source_bundle_id"),
        "split": "strict_eval_candidate",
        "split_role": "heldout_candidate_not_admitted",
        "standalone_projection_source": {
            "current_checked_row_id": spec.get("current_checked_row_id"),
            "current_checked_target_value": spec.get("current_checked_target_value"),
            "gold_value": gold_value,
            "opaque_options": relabeled,
            "projection_mode": "stage10938_explicit_verifier_ledger_strict_candidate_v1",
            "queue_id": spec.get("queue_id"),
            "variant": variant_name,
        },
        "strict_eval_eligible": False,
        "surface": "maintainer_bundle_compact_bounded_choice",
        "target_text": target_label,
        "target_token_len": 1,
        "task_type": "evidence_citation",
        "train_support_only": False,
        "verifier_anchor": bool(spec.get("selected_tests")),
    }


def main() -> None:
    specs = load_jsonl(MANIFEST_ROWS)
    corpus: list[dict[str, Any]] = []
    for path in SOURCE_ROW_FILES:
        corpus.extend(load_jsonl(path))

    rows = []
    bundle_rows = []
    for spec in specs:
        source_row = find_source_row(spec, corpus)
        gold_by_perspective = load_gold_by_perspective(spec)
        row = build_strict_row(spec, source_row, gold_by_perspective)
        rows.append(row)
        bundle_rows.append(
            {
                "queue_id": spec.get("queue_id"),
                "repo_id": spec.get("repo_id"),
                "language_family": spec.get("language_family"),
                "gold_value": (gold_by_perspective.get("evidence_citation") or {}).get("gold_answer_value"),
                "selected_tests": spec.get("selected_tests"),
                "candidate_paths": spec.get("candidate_paths"),
                "strict_candidate_row_id": row["row_id"],
                "strict_candidate_target_label": row["target_text"],
                "strict_candidate_options": row["opaque_options"],
            }
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(rows),
        "decision": "explicit_verifier_ledger_successor_candidates_materialized",
        "claim_scope": [
            "Rebuild the 3-row fresh evidence successor slice with explicit selected-test verifier ledgers derived from reviewed packet adjudication.",
            "Keep the slice non-promotable and candidate-only; this artifact exists to test whether the previous slice under-materialized the decisive verifier evidence.",
        ],
        "headline_findings": [
            "The Python and parametergolf B-vs-F rows now visibly materialize verifier_and_test_constraint in the prompt body instead of leaving it absent or implicit.",
            "The agentkernel counter-family still uses candidate_change_surface as the gold evidence key, preserving a non-verifier positive control.",
            "These rows remain heldout_candidate_not_admitted and are not a headline benchmark surface.",
        ],
        "inputs": {
            "manifest_rows": rel(MANIFEST_ROWS),
            "source_row_files": [rel(path) for path in SOURCE_ROW_FILES],
        },
        "row_count": len(rows),
        "rows_by_language": {
            language: sum(1 for row in rows if str(row.get("language_family") or "") == language)
            for language in sorted({str(row.get("language_family") or "") for row in rows})
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "row_jsonl": rel(ROWS_JSONL),
            "bundle_json": rel(BUNDLE_JSON),
        },
        "next_best_step": "Score the current 100M runtime and Gemma on this explicit-ledger candidate slice to separate model weakness from successor-prompt under-materialization.",
    }
    bundle = {
        "bundle_id": "stage10938::explicit_verifier_ledger_successor_candidates",
        "claim_boundary": {
            "strict_candidate_only": True,
            "headline_eligible": False,
            "requires_review_before_scoring": False,
            "same_surface_eval_admissible": False,
            "explicit_verifier_ledger": True,
        },
        "rows": bundle_rows,
    }
    write_json(SUMMARY_JSON, summary)
    write_json(BUNDLE_JSON, bundle)
    write_jsonl(ROWS_JSONL, rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
