#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10677
NAME = "stage10677_rust_external_source_materialization_request"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "rust_external_source_materialization_request.json"
OUT_TARGETS = OUT_DIR / "rust_external_source_materialization_targets.jsonl"

SCAFFOLD_SUMMARY = ARTIFACTS / "stage10674_rust_fresh_review_packet_scaffolds/rust_fresh_review_packet_scaffolds.json"
LOCAL_AUDIT = ARTIFACTS / "stage10676_rust_local_supply_recoverability_audit/rust_local_supply_recoverability_audit.json"
BUILDER_PACKET = ARTIFACTS / "stage10673_multilingual_residual_builder_packet/multilingual_residual_builder_packet.json"

KNOWN_CORPUS_CANDIDATES = [
    "/arxiv/TOLBERT_BRAIN/data/repos/nodes_repos.jsonl",
    "/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def main() -> None:
    scaffold_summary = load_json(SCAFFOLD_SUMMARY)
    local_audit = load_json(LOCAL_AUDIT)
    builder_packet = load_json(BUILDER_PACKET)

    strict_state = (builder_packet.get("current_frontier_state") or {})
    rust_targets = local_audit.get("targets") or []

    target_rows = []
    for row in rust_targets:
        target_rows.append(
            {
                "bundle_id": row["bundle_id"],
                "language_family": "rust",
                "candidate_paths_preview": row.get("candidate_paths_preview"),
                "sample_span_ids": row.get("sample_span_ids_available"),
                "required_recovered_fields": [
                    "candidate_change_surface real source spans",
                    "symptom_or_call_path_analogue real support fact",
                    "verifier_and_test_constraint selected test or trace anchor",
                ],
                "packet_paths": row.get("packet_paths"),
                "current_local_status": "not_materializable_from_current_local_state",
                "recovery_route": "external_repo_span_corpus_or_new_source_materialization",
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "rust_external_source_materialization_request_ready",
        "claim_scope": [
            "Convert the Rust scaffold and local recoverability audits into a concrete external-source recovery request.",
            "Specify the exact target bundles, missing fields, and likely backing corpora needed to turn one Rust residual scaffold into a scoreable reviewed packet.",
        ],
        "frontier_context": {
            "strict_constrained_accuracy": strict_state.get("strict_constrained_accuracy"),
            "strict_rust_accuracy": ((strict_state.get("strict_language_breakdown") or {}).get("rust") or {}).get("accuracy"),
            "strict_rust_miss_family": "tokenizers_evidence_citation_e_vs_f",
            "strict_miss_row_ids": strict_state.get("strict_miss_row_ids"),
        },
        "known_corpus_candidates": KNOWN_CORPUS_CANDIDATES,
        "required_recovery_contract": [
            "Resolve sample_span_ids into real source text spans.",
            "Attach at least one selected test or verifier anchor for a target bundle.",
            "Fill the stage10674 scaffold packet files with the recovered text.",
            "Re-run anti-cheat review after replacement of placeholders.",
            "Only then allow gold adjudication and any support/eval admission.",
        ],
        "target_bundle_count": len(target_rows),
        "target_bundles": [row["bundle_id"] for row in target_rows],
        "claim_boundary": [
            "This request does not prove the external corpora currently exist at those paths; it packages the most likely recovery route from prior audits and user-referenced lineage.",
            "No new training or comparison should use the stage10674 Rust packets until this request is satisfied and the placeholders are replaced with real evidence.",
            "The Rust residual remains blocked on source evidence availability, not on packet structure or bounded-decoder runtime code.",
        ],
        "next_best_steps": [
            "Check the known corpus candidates first for linux and candle repo spans matching the listed sample_span_ids.",
            "If absent, rebuild one Rust target from a fresh external repo/session source that stores real text plus verifier anchors explicitly.",
            "After one target is materialized, admit it into the next multilingual support/eval package before any new promotion attempt.",
        ],
        "sources": {
            "stage10673_builder_packet": rel(BUILDER_PACKET),
            "stage10674_scaffold_summary": rel(SCAFFOLD_SUMMARY),
            "stage10676_local_recoverability_audit": rel(LOCAL_AUDIT),
        },
    }

    write_json(OUT_JSON, payload)
    write_jsonl(OUT_TARGETS, target_rows)
    print(OUT_JSON)


if __name__ == "__main__":
    main()
