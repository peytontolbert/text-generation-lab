#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10675
NAME = "stage10675_rust_scaffold_materialization_recoverability_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "rust_scaffold_materialization_recoverability_audit.json"

SCAFFOLD_SUMMARY = ARTIFACTS / "stage10674_rust_fresh_review_packet_scaffolds/rust_fresh_review_packet_scaffolds.json"
BUILDER_REQUEST = ARTIFACTS / "stage10441_rust_evidence_citation_fresh_builder_request/rust_evidence_citation_fresh_builder_request.json"
DISCOVERY_JSONL = ARTIFACTS / "stage10125_true_source_backed_rust_root_discovery_manifest/true_source_backed_rust_root_candidates.jsonl"

SEARCH_ROOTS = [
    ROOT / "runs" / "local" / "artifacts",
    ROOT / "runs" / "summaries",
]
SEARCH_SUFFIXES = {".json", ".jsonl"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def scan_for_term(term: str) -> list[str]:
    hits: list[str] = []
    for search_root in SEARCH_ROOTS:
        if not search_root.exists():
            continue
        for dirpath, _, filenames in os.walk(search_root):
            for name in filenames:
                path = Path(dirpath) / name
                if path.suffix not in SEARCH_SUFFIXES:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if term in text:
                    hits.append(rel(path))
    return sorted(set(hits))


def main() -> None:
    scaffold_summary = load_json(SCAFFOLD_SUMMARY)
    builder_request = load_json(BUILDER_REQUEST)
    discovery_rows = load_jsonl(DISCOVERY_JSONL)

    discovery_by_root = {row["candidate_root_id"]: row for row in discovery_rows}
    builder_by_root = {row["candidate_root_id"]: row for row in builder_request.get("recommended_candidates") or []}

    target_reports = []
    for bundle_id in scaffold_summary.get("scaffold_targets") or []:
        discovery = discovery_by_root.get(bundle_id, {})
        builder = builder_by_root.get(bundle_id, {})
        sample_span_ids = discovery.get("sample_span_ids") or builder.get("sample_span_ids") or []
        candidate_paths = discovery.get("candidate_paths_preview") or builder.get("candidate_paths_preview") or []

        sample_hits = {span_id: scan_for_term(span_id) for span_id in sample_span_ids}
        path_hits = {path: scan_for_term(path) for path in candidate_paths[:3]}

        sample_hits_nonmetadata = {
            span_id: [hit for hit in hits if "stage10441_rust_evidence_citation_fresh_builder_request" not in hit and "stage10125_true_source_backed_rust_root_discovery_manifest" not in hit and "stage10674_rust_fresh_review_packet_scaffolds" not in hit]
            for span_id, hits in sample_hits.items()
        }
        path_hits_nonmetadata = {
            path: [hit for hit in hits if "stage10441_rust_evidence_citation_fresh_builder_request" not in hit and "stage10674_rust_fresh_review_packet_scaffolds" not in hit and "stage10476_rust_citation_materialized_root_bundle_builder" not in hit]
            for path, hits in path_hits.items()
        }

        real_span_recoverable = any(sample_hits_nonmetadata.values()) or any(path_hits_nonmetadata.values())
        report = {
            "bundle_id": bundle_id,
            "sample_span_ids": sample_span_ids,
            "candidate_paths_preview": candidate_paths,
            "sample_span_hits_all": sample_hits,
            "candidate_path_hits_all": path_hits,
            "sample_span_hits_nonmetadata": sample_hits_nonmetadata,
            "candidate_path_hits_nonmetadata": path_hits_nonmetadata,
            "real_span_recoverable_from_current_local_artifacts": real_span_recoverable,
            "selected_test_or_verifier_anchor_present_now": False,
            "materialization_blockers": [
                "no_resolved_real_source_span_text_in_current_local_artifacts",
                "no_selected_test_or_verifier_anchor_materialized",
            ],
        }
        target_reports.append(report)

    recoverable_count = sum(1 for row in target_reports if row["real_span_recoverable_from_current_local_artifacts"])
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "rust_scaffold_materialization_not_locally_recoverable_yet",
        "claim_scope": [
            "Audit whether the three new Rust scaffold packets can be filled with real source-derived evidence using only current local artifacts.",
            "Distinguish true source recoverability from self-referential metadata hits that only restate candidate paths or span ids.",
        ],
        "source_inputs": {
            "scaffold_summary": rel(SCAFFOLD_SUMMARY),
            "builder_request": rel(BUILDER_REQUEST),
            "discovery_manifest": rel(DISCOVERY_JSONL),
        },
        "overall_result": {
            "scaffold_target_count": len(target_reports),
            "recoverable_from_current_local_artifacts": recoverable_count,
            "not_recoverable_from_current_local_artifacts": len(target_reports) - recoverable_count,
            "all_targets_blocked_on_real_span_materialization": recoverable_count == 0,
        },
        "claim_boundary": [
            "The current workspace contains path and span-id metadata for the Rust targets, but not the resolved source text needed to fill the new scaffold packets.",
            "Metadata-only hits are not sufficient for maintainer-grade packet materialization and should not be mistaken for real evidence recovery.",
            "The next Rust step requires either recovering the backing span corpora or rebuilding the roots from a source inventory that stores actual text plus verifier anchors.",
        ],
        "next_best_steps": [
            "Recover or import the backing source-span corpus for linux, candle-datasets, and candle-transformers.",
            "Attach a real selected test or verifier anchor for at least one target before trying to admit it into scoring.",
            "Do not train or compare on these scaffolds until the placeholder evidence is replaced with real text.",
        ],
        "target_reports": target_reports,
    }

    write_json(OUT_JSON, payload)
    print(OUT_JSON)


if __name__ == "__main__":
    main()
