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
STAGE = 10972
NAME = "stage10972_rust_reviewed_evidence_bundle"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "rust_reviewed_evidence_bundle.json"
COMBINED_ROWS = OUT_DIR / "bundle_rows.jsonl"
SUPPORT_ROWS = OUT_DIR / "train_support_rows.jsonl"
CANDIDATE_ROWS = OUT_DIR / "strict_candidate_rows.jsonl"
SPECS_JSONL = OUT_DIR / "rust_reviewed_specs.jsonl"

from scripts.build_stage10934_explicit_verifier_ledger_support_package import (
    SOURCE_ROW_FILES,
    build_variant_rows,
    find_source_row,
    load_gold_by_perspective,
    load_json,
    load_jsonl,
    rel as base_rel,
)
from scripts.build_stage10938_explicit_verifier_ledger_strict_candidates import build_strict_row

RUST_PACKET_DIRS = [
    ARTIFACTS / "stage10127_true_source_backed_rust_review_packets_and_signoff" / "review_packets" / "stage10126__tokenizers__tokenizers__rust",
    ARTIFACTS / "stage10415_rust_flash_attn_review_packets" / "review_packets" / "stage10413__candle__candle-flash-attn__rust",
    ARTIFACTS / "stage10127_true_source_backed_rust_review_packets_and_signoff" / "review_packets" / "stage10126__candle__candle-core__rust",
]


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


def anti_cheat_families(card: dict[str, Any]) -> list[str]:
    return sorted([key for key, value in (card.get("challenge_families") or {}).items() if value])


def build_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for packet_dir in RUST_PACKET_DIRS:
        gold = load_json(packet_dir / "perspective_gold_adjudication.json")
        anti = load_json(packet_dir / "anti_cheat_review_card.json")
        rows = gold.get("perspective_gold_answers") or []
        ev = next((row for row in rows if str(row.get("perspective") or "") == "evidence_citation"), None)
        if ev is None:
            continue
        bundle_id = str(gold.get("bundle_id") or packet_dir.name)
        repo_id = bundle_id.split("::")[1] if "::" in bundle_id else packet_dir.name
        specs.append(
            {
                "queue_id": f"rust_reviewed::{bundle_id.replace('::', '__')}",
                "language_family": "rust",
                "repo_id": repo_id,
                "source_bundle_id": bundle_id,
                "packet_dir": rel(packet_dir),
                "current_checked_row_id": None,
                "current_checked_target_value": None,
                "gold_answer_kind": str(ev.get("gold_answer_kind") or ""),
                "gold_answer_value": str(ev.get("gold_answer_value") or ""),
                "selected_tests": list(ev.get("selected_tests") or []),
                "candidate_paths": list(ev.get("candidate_paths") or []),
                "visible_evidence_keys": list(ev.get("visible_evidence_keys") or []),
                "reviewer_rationale": str(ev.get("reviewer_rationale") or ""),
                "anti_cheat_challenge_families": anti_cheat_families(anti),
                "materialization_requirements": [
                    "Preserve visible evidence keys that are already adjudicated in the reviewed Rust packet.",
                    "Keep symptom_or_call_path_analogue and candidate_change_surface textually distinct when both are present.",
                    "Preserve selected-test anchors when the reviewed packet exposes them.",
                    "Do not expose target path strings before options.",
                ],
            }
        )
    return specs


def enrich_row(spec: dict[str, Any], row: dict[str, Any], *, candidate: bool) -> dict[str, Any]:
    updated = dict(row)
    updated["bundle_id"] = f"stage10972::{spec['queue_id']}::rust_reviewed_evidence"
    updated["candidate_queue_id"] = spec.get("queue_id")
    updated["selected_tests"] = list(spec.get("selected_tests") or [])
    updated["candidate_paths"] = list(spec.get("candidate_paths") or [])
    updated["visible_evidence_keys"] = list(spec.get("visible_evidence_keys") or [])
    updated["materialization_requirements"] = list(spec.get("materialization_requirements") or [])
    anti_cheat = dict(updated.get("anti_cheat") or {})
    anti_cheat["anti_cheat_challenge_families"] = list(spec.get("anti_cheat_challenge_families") or [])
    anti_cheat["reviewed_rust_bundle"] = True
    if candidate:
        anti_cheat["candidate_only"] = True
    updated["anti_cheat"] = anti_cheat
    projection = dict(updated.get("standalone_projection_source") or {})
    opaque_options = [dict(item) for item in (updated.get("opaque_options") or []) if isinstance(item, dict)]
    projection["opaque_options"] = opaque_options
    projection["option_values"] = [str(item.get("value") or "") for item in opaque_options]
    projection["option_labels"] = [str(item.get("label") or "") for item in opaque_options]
    projection["visible_evidence_keys"] = list(spec.get("visible_evidence_keys") or [])
    projection["selected_tests"] = list(spec.get("selected_tests") or [])
    projection["candidate_paths"] = list(spec.get("candidate_paths") or [])
    projection["reviewer_rationale"] = spec.get("reviewer_rationale")
    projection["anti_cheat_challenge_families"] = list(spec.get("anti_cheat_challenge_families") or [])
    projection["bundle_stage"] = STAGE
    updated["standalone_projection_source"] = projection
    return updated


def main() -> None:
    specs = build_specs()
    corpus: list[dict[str, Any]] = []
    for path in SOURCE_ROW_FILES:
        corpus.extend(load_jsonl(path))

    support_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    bundle_rows: list[dict[str, Any]] = []
    bundle_index: list[dict[str, Any]] = []

    for spec in specs:
        source_row = find_source_row(spec, corpus)
        gold_by_perspective = load_gold_by_perspective(spec)
        queue_support_rows: list[dict[str, Any]] = []
        for row in build_variant_rows(spec, source_row, gold_by_perspective):
            enriched = enrich_row(spec, row, candidate=False)
            support_rows.append(enriched)
            bundle_rows.append(enriched)
            queue_support_rows.append(enriched)
        candidate = enrich_row(spec, build_strict_row(spec, source_row, gold_by_perspective), candidate=True)
        candidate_rows.append(candidate)
        bundle_rows.append(candidate)
        bundle_index.append(
            {
                "queue_id": spec.get("queue_id"),
                "repo_id": spec.get("repo_id"),
                "source_bundle_id": spec.get("source_bundle_id"),
                "gold_answer_value": spec.get("gold_answer_value"),
                "selected_tests": spec.get("selected_tests"),
                "candidate_row_id": candidate.get("row_id"),
                "support_row_ids": [row.get("row_id") for row in queue_support_rows],
            }
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(bundle_rows),
        "decision": "rust_reviewed_evidence_bundle_ready",
        "claim_scope": [
            "Convert already reviewed Rust packets into support-only evidence rows plus explicit-ledger candidate rows.",
            "Strengthen multilingual evidence-role supervision while keeping the resulting rows outside the promotable strict path until a later review/probe stage.",
        ],
        "source_artifacts": {
            "source_row_files": [base_rel(path) for path in SOURCE_ROW_FILES],
            "review_packet_dirs": [rel(path) for path in RUST_PACKET_DIRS],
            "specs_jsonl": rel(SPECS_JSONL),
        },
        "metrics": {
            "bundle_rows": len(bundle_rows),
            "support_rows": len(support_rows),
            "candidate_rows": len(candidate_rows),
            "gold_values": {value: sum(1 for spec in specs if spec.get("gold_answer_value") == value) for value in sorted({str(spec.get("gold_answer_value") or "") for spec in specs})},
        },
        "bundle_index": bundle_index,
        "findings": [
            "Tokenizers and flash-attn contribute reviewed symptom_or_call_path_analogue positives with selected-test anchors.",
            "Candle-core contributes a reviewed candidate_change_surface control without selected tests.",
            "This bundle gives Rust real reviewed evidence-role supervision now, even before the newer linux/candle-datasets placeholder scaffolds are materialized.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "bundle_rows_jsonl": rel(COMBINED_ROWS),
            "support_rows_jsonl": rel(SUPPORT_ROWS),
            "candidate_rows_jsonl": rel(CANDIDATE_ROWS),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(SPECS_JSONL, specs)
    write_jsonl(COMBINED_ROWS, bundle_rows)
    write_jsonl(SUPPORT_ROWS, support_rows)
    write_jsonl(CANDIDATE_ROWS, candidate_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
