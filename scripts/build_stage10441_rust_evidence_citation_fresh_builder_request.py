#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10441
NAME = "stage10441_rust_evidence_citation_fresh_builder_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "rust_evidence_citation_fresh_builder_request.json"
TARGETS_JSONL = OUT_DIR / "rust_evidence_citation_fresh_builder_targets.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

RUST_ATLAS_JSON = ROOT / "runs/local/artifacts/stage10411_fresh_rust_disjoint_root_candidate_atlas/fresh_rust_disjoint_root_candidate_atlas.json"
FLASH_JSON = ROOT / "runs/local/artifacts/stage10413_fresh_rust_flash_attn_preview/fresh_rust_flash_attn_preview_bundle.json"
RESIDUAL_QUEUE_JSON = ROOT / "runs/local/artifacts/stage10433_reviewed_v28_residual_expansion_queue/reviewed_v28_residual_expansion_queue.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
    atlas = load_json(RUST_ATLAS_JSON)
    flash = load_json(FLASH_JSON)
    residual_queue = load_json(RESIDUAL_QUEUE_JSON)

    candidates = []
    for row in atlas.get("top_fresh_candidates") or []:
        if row.get("candidate_root_id") == "candle::candle-flash-attn":
            continue
        candidates.append(
            {
                "candidate_root_id": row.get("candidate_root_id"),
                "repo_id": row.get("repo_id"),
                "package_root": row.get("package_root"),
                "recommendation": row.get("recommendation"),
                "review_ready_for_bundle_construction": row.get("review_ready_for_bundle_construction"),
                "test_file_count": row.get("test_file_count"),
                "implementation_file_count": row.get("implementation_file_count"),
                "competition_geometries": row.get("competition_geometries"),
                "sample_span_ids": row.get("sample_span_ids"),
                "candidate_paths_preview": row.get("candidate_paths_preview"),
                "priority_score": row.get("priority_score"),
                "required_builder_delta": [
                    "add a concrete verifier/test anchor or selected test when absent",
                    "construct evidence-citation rows where candidate_change_surface is a tempting negative",
                    "keep the target support fact distinct from verifier_and_test_constraint",
                ],
            }
        )

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Fresh Rust builder request for the remaining evidence-citation residual after the hardened v2.7 overlay.",
            "This is a source-building request, not a training execution request, because reviewed fresh Rust supply is still constrained.",
            "The goal is to produce at least one disjoint reviewed Rust root with a stronger evidence-citation contrast than the current tokenizers row.",
        ],
        "source_artifacts": {
            "rust_candidate_atlas": display(RUST_ATLAS_JSON),
            "flash_attn_preview": display(FLASH_JSON),
            "residual_expansion_queue": display(RESIDUAL_QUEUE_JSON),
        },
        "current_residual_target": next(
            (row for row in residual_queue.get("targets") or [] if row.get("language_family") == "rust"),
            None,
        ),
        "flash_attn_boundary": flash.get("claim_boundary"),
        "builder_requirements": [
            "Root must be disjoint from the current strict tokenizers root.",
            "Visible evidence must support a real evidence-citation contrast, not just abstention-heavy localization.",
            "Target support fact must not appear verbatim before options.",
            "Selected-test or verifier anchor should be present when possible.",
        ],
        "recommended_candidates": candidates[:5],
        "success_condition": {
            "new_rust_review_ready_bundle_count": 1,
            "new_rust_bundle_has_selected_test_or_verifier_anchor": True,
            "new_rust_bundle_supports_evidence_citation_contrast": True,
        },
        "outputs": {
            "request_json": display(REQUEST_JSON),
            "target_rows": display(TARGETS_JSONL),
        },
    }
    write_json(REQUEST_JSON, request)
    write_jsonl(TARGETS_JSONL, candidates[:5])
    write_json(SUMMARY, request)
    print(json.dumps(request, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
