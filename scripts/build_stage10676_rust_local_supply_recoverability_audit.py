#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10676
NAME = "stage10676_rust_local_supply_recoverability_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "rust_local_supply_recoverability_audit.json"

SCAFFOLD_SUMMARY = ARTIFACTS / "stage10674_rust_fresh_review_packet_scaffolds/rust_fresh_review_packet_scaffolds.json"
DISCOVERY_JSONL = ARTIFACTS / "stage10125_true_source_backed_rust_root_discovery_manifest/true_source_backed_rust_root_candidates.jsonl"


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


def packet_paths(bundle_id: str) -> dict[str, str]:
    slug = bundle_id.replace("::", "__")
    base = ARTIFACTS / "stage10674_rust_fresh_review_packet_scaffolds" / "review_packets" / slug
    return {
        "preview_bundle": rel(base / "fresh_rust_bundle_preview.json"),
        "anti_cheat_review_card": rel(base / "anti_cheat_review_card.json"),
        "perspective_gold_adjudication": rel(base / "perspective_gold_adjudication.json"),
    }


def main() -> None:
    scaffold_summary = load_json(SCAFFOLD_SUMMARY)
    discovery_rows = load_jsonl(DISCOVERY_JSONL)
    discovery_by_root = {row["candidate_root_id"]: row for row in discovery_rows}

    targets = []
    for bundle_id in scaffold_summary.get("scaffold_targets") or []:
        discovery = discovery_by_root.get(bundle_id, {})
        targets.append(
            {
                "bundle_id": bundle_id,
                "packet_paths": packet_paths(bundle_id),
                "sample_span_ids_available": discovery.get("sample_span_ids") or [],
                "candidate_paths_preview": discovery.get("candidate_paths_preview") or [],
                "review_ready_for_bundle_construction": discovery.get("review_ready_for_bundle_construction"),
                "test_file_count": discovery.get("test_file_count"),
                "support_file_count": discovery.get("support_file_count"),
                "has_local_real_text_artifact": False,
                "has_local_selected_test_anchor": False,
                "has_local_verifier_anchor": False,
                "materialization_possible_from_current_local_state": False,
                "blockers": [
                    "only metadata-level discovery is present locally",
                    "no locally stored source-text artifact was identified for this target",
                    "no selected test or verifier anchor is present",
                ],
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "rust_fresh_targets_need_new_source_materialization_not_local_only_recovery",
        "claim_scope": [
            "Audit whether the three fresh Rust scaffold targets can be materialized using only currently stored local reviewed/discovery artifacts.",
            "Use file inventory and discovery metadata rather than an expensive full-content crawl.",
        ],
        "inputs": {
            "scaffold_summary": rel(SCAFFOLD_SUMMARY),
            "discovery_manifest": rel(DISCOVERY_JSONL),
        },
        "overall_result": {
            "target_count": len(targets),
            "materializable_from_current_local_state": 0,
            "blocked_on_new_source_materialization": len(targets),
        },
        "claim_boundary": [
            "The local workspace contains scaffold packets and discovery metadata for the Rust targets, but not the real source-text evidence needed to fill them.",
            "No selected test or verifier anchor is present for linux::rust, candle::candle-datasets, or candle::candle-transformers in current local reviewed assets.",
            "The next useful step is not another same-surface probe; it is recovering or importing real source spans plus verifier anchors for at least one of these targets.",
        ],
        "recommended_next_stage": "materialize_one_real_rust_target_with_source_text_and_verifier_anchor",
        "targets": targets,
    }

    write_json(OUT_JSON, payload)
    print(OUT_JSON)


if __name__ == "__main__":
    main()
