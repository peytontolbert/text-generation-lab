#!/usr/bin/env python3
"""Preflight admitted sentencepiece C++ source-heldout smoke rows.

This stage verifies that Stage11720 rows are admissible for compact
source-heldout smoke scoring while keeping the full-product harness boundary
explicit. It does not run models.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROWS = ROOT / "runs/local/artifacts/stage11720_sentencepiece_cpp_admitted_smoke_packet/sentencepiece_cpp_admitted_smoke_rows.jsonl"
STAGE11720 = ROOT / "runs/local/artifacts/stage11720_sentencepiece_cpp_admitted_smoke_packet/sentencepiece_cpp_admitted_smoke_packet.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage11721_sentencepiece_cpp_source_heldout_smoke_preflight"
SUMMARY = ROOT / "runs/summaries/stage11721_sentencepiece_cpp_source_heldout_smoke_preflight.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def anti(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("anti_cheat") or {}
    return value if isinstance(value, dict) else {}


def option_count(row: dict[str, Any]) -> int:
    return len(row.get("opaque_options") or row.get("options") or [])


def compact_blockers(row: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    ac = anti(row)
    if row.get("source_heldout_admissible") is not True:
        blockers.append("source_heldout_admissible_not_true")
    if row.get("source_heldout_attestation") != "stage11719_pass_no_exact_new_root_train_overlap":
        blockers.append("missing_stage11719_attestation")
    if row.get("split") != "strict_eval" or row.get("split_role") != "strict_source_heldout_smoke":
        blockers.append("not_strict_source_heldout_smoke_split")
    if row.get("strict_eval_eligible") is not True:
        blockers.append("strict_eval_eligible_not_true")
    if row.get("train_support_only") is True:
        blockers.append("train_support_only_true")
    if not row.get("root_id") or not row.get("root_lineage_key"):
        blockers.append("missing_root_id_or_root_lineage_key")
    if row.get("language_family") != "c_cpp":
        blockers.append("language_family_not_c_cpp")
    if row.get("repo_family") != "sentencepiece":
        blockers.append("repo_family_not_sentencepiece")
    if ac.get("deterministic_option_shuffle") is not True:
        blockers.append("deterministic_option_shuffle_not_true")
    if ac.get("prompt_target_label_leak") is True:
        blockers.append("prompt_target_label_leak_true")
    if ac.get("prompt_target_value_leak") is True:
        blockers.append("prompt_target_value_leak_true")
    if option_count(row) < 2:
        blockers.append("missing_or_singleton_options")
    if not (row.get("target_label") or row.get("expected_label") or row.get("target_text")):
        blockers.append("missing_target")
    if row.get("has_verifier_row_or_transition") is not True:
        blockers.append("missing_has_verifier_row_or_transition")
    if not (row.get("selected_test_anchor") is True or row.get("verifier_anchor") is True):
        blockers.append("missing_selected_test_or_verifier_anchor")
    return blockers


def full_product_blockers(row: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if row.get("has_executable_verifier_result") is not True:
        blockers.append("missing_executable_verifier_result")
    if row.get("harness_run_id") in (None, ""):
        blockers.append("missing_harness_run_id")
    if row.get("tool_trace_spans") in (None, []):
        blockers.append("missing_tool_trace_spans")
    if row.get("patch_minimality_or_abstain_scores") in (None, {}):
        blockers.append("missing_patch_minimality_or_abstain_scores")
    if row.get("has_patch_or_abstain_row") is not True:
        blockers.append("missing_patch_or_abstain_row")
    return blockers


def main() -> None:
    if not ROWS.exists():
        raise FileNotFoundError(ROWS)
    rows = read_jsonl(ROWS)
    source_artifact = json.loads(STAGE11720.read_text(encoding="utf-8")) if STAGE11720.exists() else {}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)

    cards: list[dict[str, Any]] = []
    for row in rows:
        compact = compact_blockers(row)
        full = full_product_blockers(row)
        cards.append(
            {
                "row_id": row.get("row_id"),
                "root_id": row.get("root_id"),
                "task_type": row.get("task_type"),
                "target_label": row.get("target_label"),
                "compact_smoke_status": "admissible" if not compact else "blocked",
                "full_product_status": "ready" if not full else "blocked",
                "compact_blockers": compact,
                "full_product_blockers": full,
                "field_state": {
                    "source_heldout_admissible": row.get("source_heldout_admissible"),
                    "source_heldout_attestation": row.get("source_heldout_attestation"),
                    "split": row.get("split"),
                    "split_role": row.get("split_role"),
                    "option_count": option_count(row),
                    "deterministic_option_shuffle": anti(row).get("deterministic_option_shuffle"),
                    "prompt_target_label_leak": anti(row).get("prompt_target_label_leak"),
                    "prompt_target_value_leak": anti(row).get("prompt_target_value_leak"),
                    "selected_test_anchor": row.get("selected_test_anchor"),
                    "verifier_anchor": row.get("verifier_anchor"),
                    "has_verifier_row_or_transition": row.get("has_verifier_row_or_transition"),
                    "has_executable_verifier_result": row.get("has_executable_verifier_result"),
                    "has_patch_or_abstain_row": row.get("has_patch_or_abstain_row"),
                },
            }
        )

    compact_status = Counter(card["compact_smoke_status"] for card in cards)
    full_status = Counter(card["full_product_status"] for card in cards)
    compact_blocker_counts = Counter(b for card in cards for b in card["compact_blockers"])
    full_blocker_counts = Counter(b for card in cards for b in card["full_product_blockers"])
    compact_ready = compact_status.get("admissible", 0) == len(cards) and len(cards) > 0
    full_product_ready = full_status.get("ready", 0) == len(cards) and len(cards) > 0

    artifact = {
        "stage": 11721,
        "stage_name": "sentencepiece_cpp_source_heldout_smoke_preflight",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "compact_source_heldout_smoke_ready_full_product_not_ready"
        if compact_ready and not full_product_ready
        else ("source_heldout_full_product_ready" if full_product_ready else "source_heldout_smoke_blocked"),
        "passed": compact_ready,
        "compact_source_heldout_smoke_ready": compact_ready,
        "full_product_ready": full_product_ready,
        "source_stage": 11720,
        "source_decision": source_artifact.get("decision"),
        "row_count": len(rows),
        "root_count": len({row.get("root_id") for row in rows}),
        "language_family": "c_cpp",
        "repo_family": "sentencepiece",
        "task_types": sorted({row.get("task_type") for row in rows}),
        "compact_status_counts": dict(compact_status),
        "full_product_status_counts": dict(full_status),
        "compact_blockers": dict(compact_blocker_counts.most_common()),
        "full_product_blockers": dict(full_blocker_counts.most_common()),
        "claim_boundary": [
            "Rows are admitted for compact source-heldout smoke scoring only.",
            "Exact new root/source snapshot train-overlap attestation passed in Stage11719.",
            "Broad repo-family/source-path warning scan is still deferred.",
            "No executable verifier result, harness run, tool trace, or patch minimality score is attached.",
        ],
        "next_stage_acceptance": [
            "run Stage11507 selected product scorer on the 4 admitted rows",
            "run Gemma same-manifest on the same 4 rows",
            "run deterministic option-permutation audit",
            "materialize executable verifier/harness fields before any full-product claim",
        ],
        "source_artifacts": {
            "stage11720_artifact": str(STAGE11720.relative_to(ROOT)),
            "stage11720_rows": str(ROWS.relative_to(ROOT)),
        },
        "outputs": {
            "artifact": "runs/local/artifacts/stage11721_sentencepiece_cpp_source_heldout_smoke_preflight/sentencepiece_cpp_source_heldout_smoke_preflight.json",
            "row_cards": "runs/local/artifacts/stage11721_sentencepiece_cpp_source_heldout_smoke_preflight/sentencepiece_cpp_source_heldout_smoke_preflight_row_cards.jsonl",
            "summary": "runs/summaries/stage11721_sentencepiece_cpp_source_heldout_smoke_preflight.json",
        },
    }

    artifact_path = OUT_DIR / "sentencepiece_cpp_source_heldout_smoke_preflight.json"
    cards_path = OUT_DIR / "sentencepiece_cpp_source_heldout_smoke_preflight_row_cards.jsonl"
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with cards_path.open("w", encoding="utf-8") as fh:
        for card in cards:
            fh.write(json.dumps(card, sort_keys=True) + "\n")
    shutil.copyfile(artifact_path, SUMMARY)
    print(
        json.dumps(
            {
                "artifact": str(artifact_path),
                "summary": str(SUMMARY),
                "compact_ready": compact_ready,
                "full_product_ready": full_product_ready,
                "row_count": len(rows),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
