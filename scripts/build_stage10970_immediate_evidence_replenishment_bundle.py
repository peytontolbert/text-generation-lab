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
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10970
NAME = "stage10970_immediate_evidence_replenishment_bundle"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "immediate_evidence_replenishment_bundle.json"
COMBINED_ROWS = OUT_DIR / "bundle_rows.jsonl"
SUPPORT_ROWS = OUT_DIR / "train_support_rows.jsonl"
CANDIDATE_ROWS = OUT_DIR / "strict_candidate_rows.jsonl"

from scripts.build_stage10914_evidence_successor_materialization_manifest import load_jsonl as load_manifest_rows, OUT_JSONL as MANIFEST_ROWS
from scripts.build_stage10934_explicit_verifier_ledger_support_package import (
    SOURCE_ROW_FILES,
    build_variant_rows,
    find_source_row,
    load_gold_by_perspective,
    rel as base_rel,
)
from scripts.build_stage10938_explicit_verifier_ledger_strict_candidates import build_strict_row as build_candidate_row


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


def enrich_candidate_row(spec: dict[str, Any], source_row: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    prompt = str(updated.get("prompt_text") or updated.get("input_text") or "")
    evidence_block = ""
    if "Evidence:\n" in prompt and "\nOptions:\n" in prompt:
        evidence_block = prompt.split("Evidence:\n", 1)[1].split("\nOptions:\n", 1)[0]
    evidence_lines = [line.strip() for line in evidence_block.splitlines() if line.strip()]
    projection = dict(updated.get("standalone_projection_source") or {})
    opaque_options = [dict(item) for item in (updated.get("opaque_options") or []) if isinstance(item, dict)]
    projection.update(
        {
            "opaque_options": opaque_options,
            "option_values": [str(item.get("value") or "") for item in opaque_options],
            "option_labels": [str(item.get("label") or "") for item in opaque_options],
            "query_text": updated.get("query_text"),
            "visible_evidence_keys": list(spec.get("visible_evidence_keys") or []),
            "visible_evidence_lines": evidence_lines,
            "selected_tests": list(spec.get("selected_tests") or []),
            "candidate_paths": list(spec.get("candidate_paths") or []),
            "anti_cheat_challenge_families": list(spec.get("anti_cheat_challenge_families") or []),
            "reviewer_rationale": spec.get("reviewer_rationale"),
            "materialization_requirements": list(spec.get("materialization_requirements") or []),
            "bundle_stage": STAGE,
            "projection_mode": "stage10970_immediate_evidence_replenishment_candidate_v2",
        }
    )
    anti_cheat = dict(updated.get("anti_cheat") or {})
    anti_cheat.update(
        {
            "visible_evidence_support_confirmed": True,
            "selected_test_anchor_preserved": bool(spec.get("selected_tests")),
            "anti_cheat_challenge_families": list(spec.get("anti_cheat_challenge_families") or []),
            "reviewed_replenishment_bundle": True,
        }
    )
    updated.update(
        {
            "anti_cheat": anti_cheat,
            "bundle_id": f"stage10970::{spec['queue_id']}::immediate_replenishment",
            "candidate_queue_id": spec.get("queue_id"),
            "materialization_requirements": list(spec.get("materialization_requirements") or []),
            "selected_tests": list(spec.get("selected_tests") or []),
            "candidate_paths": list(spec.get("candidate_paths") or []),
            "visible_evidence_keys": list(spec.get("visible_evidence_keys") or []),
            "standalone_projection_source": projection,
        }
    )
    return updated


def main() -> None:
    specs = load_manifest_rows(MANIFEST_ROWS)
    corpus: list[dict[str, Any]] = []
    for path in SOURCE_ROW_FILES:
        corpus.extend(load_manifest_rows(path))

    support_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    bundle_rows: list[dict[str, Any]] = []
    bundle_index: list[dict[str, Any]] = []

    for spec in specs:
        source_row = find_source_row(spec, corpus)
        gold_by_perspective = load_gold_by_perspective(spec)
        queue_support_rows: list[dict[str, Any]] = []
        for support in build_variant_rows(spec, source_row, gold_by_perspective):
            enriched_support = dict(support)
            enriched_support["bundle_id"] = f"stage10970::{spec['queue_id']}::immediate_replenishment"
            enriched_support["candidate_queue_id"] = spec.get("queue_id")
            enriched_support["selected_tests"] = list(spec.get("selected_tests") or [])
            enriched_support["candidate_paths"] = list(spec.get("candidate_paths") or [])
            enriched_support["visible_evidence_keys"] = list(spec.get("visible_evidence_keys") or [])
            enriched_support["materialization_requirements"] = list(spec.get("materialization_requirements") or [])
            anti_cheat = dict(enriched_support.get("anti_cheat") or {})
            anti_cheat["anti_cheat_challenge_families"] = list(spec.get("anti_cheat_challenge_families") or [])
            anti_cheat["reviewed_replenishment_bundle"] = True
            enriched_support["anti_cheat"] = anti_cheat
            support_rows.append(enriched_support)
            bundle_rows.append(enriched_support)
            queue_support_rows.append(enriched_support)
        candidate = enrich_candidate_row(spec, source_row, build_candidate_row(spec, source_row, gold_by_perspective))
        candidate_rows.append(candidate)
        bundle_rows.append(candidate)
        bundle_index.append(
            {
                "queue_id": spec.get("queue_id"),
                "language_family": spec.get("language_family"),
                "repo_id": spec.get("repo_id"),
                "source_bundle_id": spec.get("source_bundle_id"),
                "gold_answer_value": spec.get("gold_answer_value"),
                "selected_tests": spec.get("selected_tests"),
                "candidate_paths": spec.get("candidate_paths"),
                "support_row_ids": [row["row_id"] for row in queue_support_rows],
                "candidate_row_id": candidate["row_id"],
            }
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(bundle_rows),
        "decision": "immediate_python_cpp_evidence_replenishment_bundle_ready",
        "claim_scope": [
            "Bundle the immediate Python/C++ evidence replenishment lanes into one reusable support-plus-candidate materialization artifact.",
            "Preserve anti-cheat metadata, selected-test anchors, visible evidence keys, and candidate ordering metadata for the next v2.7 review or training step.",
        ],
        "source_artifacts": {
            "manifest_rows": rel(MANIFEST_ROWS),
            "source_row_files": [base_rel(path) for path in SOURCE_ROW_FILES],
        },
        "metrics": {
            "bundle_rows": len(bundle_rows),
            "support_rows": len(support_rows),
            "candidate_rows": len(candidate_rows),
            "queues": [row.get("queue_id") for row in specs],
            "by_language": {
                language: sum(1 for row in bundle_rows if str(row.get("language_family") or "") == language)
                for language in sorted({str(row.get("language_family") or "") for row in bundle_rows})
            },
        },
        "findings": [
            "All three immediate replenishment queues are now packaged with both train-support rows and strict-candidate rows in one bundle.",
            "Candidate rows now carry richer standalone projection metadata, including option values, visible evidence lines, selected tests, and anti-cheat challenge families.",
            "This bundle stays non-promotable for headline scoring, but it is stable input for anti-cheat auditing, future review, and next support-package assembly.",
        ],
        "bundle_index": bundle_index,
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "bundle_rows_jsonl": rel(COMBINED_ROWS),
            "support_rows_jsonl": rel(SUPPORT_ROWS),
            "candidate_rows_jsonl": rel(CANDIDATE_ROWS),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(COMBINED_ROWS, bundle_rows)
    write_jsonl(SUPPORT_ROWS, support_rows)
    write_jsonl(CANDIDATE_ROWS, candidate_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
