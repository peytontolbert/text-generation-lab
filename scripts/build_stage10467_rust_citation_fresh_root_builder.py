#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10467
NAME = "stage10467_rust_citation_fresh_root_builder"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "rust_citation_fresh_root_builder.json"
TARGETS_JSONL = OUT_DIR / "rust_citation_fresh_root_targets.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

QUEUE_JSON = ROOT / "runs/local/artifacts/stage10444_repaired_v27_disjoint_residual_queue/repaired_v27_disjoint_residual_queue.json"
ATLAS_JSON = ROOT / "runs/local/artifacts/stage10411_fresh_rust_disjoint_root_candidate_atlas/fresh_rust_disjoint_root_candidate_atlas.json"
CITATION_ATLAS_JSON = ROOT / "runs/local/artifacts/stage10452_rust_evidence_citation_candidate_atlas/rust_evidence_citation_candidate_atlas.json"
CITATION_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10452_rust_evidence_citation_candidate_atlas/rust_evidence_citation_candidate_rows.jsonl"
SUPPLY_INVENTORY = ROOT / "runs/local/artifacts/stage10464_rust_citation_fresh_root_inventory/rust_citation_fresh_root_inventory.json"
PACKAGE_REQUEST = ROOT / "runs/local/artifacts/stage10465_fresh_residual_root_package_and_probe_request/fresh_residual_root_package_and_probe_request.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    queue = load_json(QUEUE_JSON)
    atlas = load_json(ATLAS_JSON)
    citation_atlas = load_json(CITATION_ATLAS_JSON)
    inventory = load_json(SUPPLY_INVENTORY)
    package_request = load_json(PACKAGE_REQUEST)
    citation_rows = load_jsonl(CITATION_ROWS_JSONL)

    target = next(row for row in queue["targets"] if row["language_family"] == "rust")
    top_candidates = [row for row in atlas.get("top_fresh_candidates") or [] if row.get("candidate_root_id") != "candle::candle-flash-attn"][:4]

    builder_targets: list[dict[str, Any]] = []
    for order, row in enumerate(top_candidates, start=1):
        builder_targets.append(
            {
                "priority_order": order,
                "candidate_root_id": row["candidate_root_id"],
                "repo_id": row["repo_id"],
                "package_root": row["package_root"],
                "review_ready_for_bundle_construction": row["review_ready_for_bundle_construction"],
                "competition_geometries": row["competition_geometries"],
                "test_file_count": row["test_file_count"],
                "implementation_file_count": row["implementation_file_count"],
                "support_role": "fresh_root_builder_target",
                "required_builder_delta": [
                    "materialize evidence-citation rows where symptom_or_call_path_analogue and verifier_and_test_constraint are both visible options",
                    "retain a tempting candidate_change_surface negative without making it the gold",
                    "attach selected-test or verifier anchors whenever recoverable",
                ],
                "claim_boundary": [
                    "These are builder targets, not current train rows.",
                    "Do not substitute candle-core support rows for a true fresh-root rebuild.",
                ],
            }
        )

    builder_targets.append(
        {
            "priority_order": len(builder_targets) + 1,
            "candidate_root_id": "stage10126::candle::candle-core::rust",
            "repo_id": "candle",
            "package_root": "candle-core",
            "review_ready_for_bundle_construction": True,
            "competition_geometries": ["existing_compact_bounded_perms"],
            "test_file_count": 0,
            "implementation_file_count": 6,
            "support_role": "diagnostic_train_support_only",
            "required_builder_delta": [
                "use only as interim train support while fresh non-tokenizers roots are being built",
                "do not count toward the minimum fresh-root requirement",
            ],
            "claim_boundary": [
                "Candle-core remains valid train support but does not solve the exact E-vs-F disjoint contrast gap.",
                "Tokenizers same-surface rows remain diagnostic-only and excluded from promotable support.",
            ],
        }
    )

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "rust_citation_fresh_root_builder_ready",
        "claim_scope": [
            "Materialize the next fresh Rust builder targets for the repaired-v2.7 evidence-citation residual.",
            "Separate true fresh-root construction from interim candle-core train support and forbid same-surface tokenizers promotion.",
        ],
        "source_artifacts": {
            "residual_queue": display(QUEUE_JSON),
            "fresh_rust_candidate_atlas": display(ATLAS_JSON),
            "rust_citation_atlas": display(CITATION_ATLAS_JSON),
            "rust_citation_candidate_rows": display(CITATION_ROWS_JSONL),
            "rust_supply_inventory": display(SUPPLY_INVENTORY),
            "fresh_residual_package_request": display(PACKAGE_REQUEST),
        },
        "current_residual_target": target,
        "interim_train_support": {
            "candidate_row_count": citation_atlas["unique_candidate_row_count"],
            "source_bundle": citation_atlas["source_bundle"],
            "required_honesty_gates": citation_atlas["required_honesty_gates"],
        },
        "builder_requirements": inventory["builder_requirements"],
        "target_package_contract": {
            "must_be_root_disjoint": True,
            "must_include_non_tokenizers_repo_family": True,
            "must_keep_tokenizers_same_surface_out_of_promotable_support": True,
            "must_record_selected_test_or_verifier_anchor_presence": True,
            "must_distinguish_fresh_builder_targets_from_interim_train_support": True,
        },
        "recommended_next_stage": "stage10468_fresh_residual_root_support_package",
        "targets_jsonl": display(TARGETS_JSONL),
    }

    write_jsonl(TARGETS_JSONL, builder_targets)
    write_json(REQUEST_JSON, request)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": request["decision"],
            "targets": display(TARGETS_JSONL),
        },
    )
    print(json.dumps(request, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
