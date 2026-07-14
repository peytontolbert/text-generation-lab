#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10476
NAME = "stage10476_rust_citation_materialized_root_bundle_builder"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "rust_citation_materialized_root_bundle_builder.json"
ROOTS_JSONL = OUT_DIR / "rust_citation_materialized_root_manifest.jsonl"
ROWS_JSONL = OUT_DIR / "rust_citation_materialized_bounded_rows.jsonl"
QUEUE_JSONL = OUT_DIR / "rust_citation_pending_materialization_queue.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

MATERIALIZATION_REQUEST = ROOT / "runs/local/artifacts/stage10473_rust_citation_fresh_root_materialization_request/rust_citation_fresh_root_materialization_request.json"
SUPPORT_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10468_fresh_residual_root_support_package/fresh_residual_root_support_rows.jsonl"
FLASH_ATTN_SUMMARY = ROOT / "runs/local/artifacts/stage10416_ai_adjudicate_rust_flash_attn_bundle/rust_flash_attn_ai_adjudication_summary.json"
FRESH_ATLAS_JSON = ROOT / "runs/local/artifacts/stage10411_fresh_rust_disjoint_root_candidate_atlas/fresh_rust_disjoint_root_candidate_atlas.json"

EXECUTABLE_ROOTS = {"stage10126::candle::candle-core::rust"}
REVIEWED_PENDING_ROOTS = {"stage10413::candle::candle-flash-attn::rust"}


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
    request = load_json(MATERIALIZATION_REQUEST)
    flash = load_json(FLASH_ATTN_SUMMARY)
    atlas = load_json(FRESH_ATLAS_JSON)
    rows = [row for row in load_jsonl(SUPPORT_ROWS_JSONL) if str(row.get("language_family")) == "rust"]

    rows_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        root_id = str(row.get("source_bundle_id") or row.get("source_root_id") or "")
        rows_by_root[root_id].append(row)

    root_manifest: list[dict[str, Any]] = []
    for root_id, root_rows in sorted(rows_by_root.items()):
        first = root_rows[0]
        task_counts = Counter(str(row.get("task_type") or "unknown") for row in root_rows)
        root_manifest.append(
            {
                "root_id": root_id,
                "repo_id": str(first.get("repo_id") or "unknown"),
                "repo_family": str(first.get("repo_family") or first.get("repo_id") or "unknown"),
                "language_family": "rust",
                "support_role": "diagnostic_train_support_only",
                "materialization_status": "executable_rows_available",
                "row_count": len(root_rows),
                "task_type_counts": dict(sorted(task_counts.items())),
                "evidence_citation_rows": int(task_counts.get("evidence_citation", 0)),
                "selected_test_anchor": bool(first.get("selected_test_anchor")),
                "verifier_anchor": bool(first.get("verifier_anchor")),
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "claim_boundary": [
                    "Candle-core rows are executable disjoint rust support, but they do not prove the exact tokenizers E-vs-F contrast.",
                    "Keep these rows diagnostic or auxiliary until a non-tokenizers fresh root reproduces the same contrast honestly.",
                ],
            }
        )

    pending_queue: list[dict[str, Any]] = [
        {
            "root_id": "stage10413::candle::candle-flash-attn::rust",
            "repo_id": flash["repo_id"],
            "repo_family": flash["repo_id"],
            "language_family": flash["language_family"],
            "materialization_status": "reviewed_pending_executable_gold_rows",
            "selected_tests": flash.get("selected_tests") or [],
            "candidate_paths": flash.get("candidate_paths") or [],
            "claim_boundary": flash.get("claim_boundary") or [],
            "next_action": "materialize executable bounded rows from the reviewed flash-attn packet or attach full gold adjudication artifact",
        }
    ]

    for candidate in atlas.get("top_fresh_candidates") or []:
        if not isinstance(candidate, dict):
            continue
        candidate_root_id = str(candidate.get("candidate_root_id") or "")
        if candidate_root_id in {"candle::candle-flash-attn", "tokenizers::bindings/node", "tokenizers::bindings/python"}:
            continue
        pending_queue.append(
            {
                "root_id": candidate_root_id,
                "repo_id": str(candidate.get("repo_id") or "unknown"),
                "repo_family": str(candidate.get("repo_id") or "unknown"),
                "language_family": "rust",
                "materialization_status": "fresh_source_root_needs_bundle_construction",
                "test_file_count": int(candidate.get("test_file_count") or 0),
                "build_file_count": int(candidate.get("build_file_count") or 0),
                "implementation_file_count": int(candidate.get("implementation_file_count") or 0),
                "competition_geometries": candidate.get("competition_geometries") or [],
                "candidate_paths_preview": candidate.get("candidate_paths_preview") or [],
                "next_action": "recover or synthesize verifier/test anchors and build a reviewed maintainer packet with explicit evidence-citation contrast",
            }
        )

    requested_roots = int(request["materialization_requirements"]["minimum_new_roots"])
    fresh_ready_roots = sum(1 for row in pending_queue if row["materialization_status"] == "fresh_source_root_needs_bundle_construction")

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "rust_citation_materialized_root_inventory_built",
        "claim_scope": [
            "Materialize the currently executable Rust citation support roots and separate them from the reviewed and fresh roots that still need conversion.",
            "Make the Rust supply gap explicit so later support packaging cannot overstate what is already executable.",
        ],
        "source_artifacts": {
            "materialization_request": display(MATERIALIZATION_REQUEST),
            "support_rows": display(SUPPORT_ROWS_JSONL),
            "flash_attn_adjudication": display(FLASH_ATTN_SUMMARY),
            "fresh_rust_atlas": display(FRESH_ATLAS_JSON),
        },
        "metrics": {
            "materialized_rust_rows": len(rows),
            "executable_root_count": len(root_manifest),
            "reviewed_pending_root_count": 1,
            "fresh_pending_queue_count": fresh_ready_roots,
            "requested_fresh_root_count": requested_roots,
            "task_type_counts": dict(sorted(Counter(str(row.get("task_type") or "unknown") for row in rows).items())),
        },
        "gap_statement": [
            "Executable Rust support exists today only for candle-core permutations.",
            "The strongest reviewed fresh root is flash-attn, but it still needs executable bounded-row materialization or a persisted full gold adjudication artifact.",
            "No non-tokenizers fresh root currently reproduces the exact tokenizers E-vs-F evidence-citation contrast as executable train/eval rows.",
        ],
        "next_best_step": [
            "Use candle-core executable rows only as auxiliary Rust support in the next combined package.",
            "Promote flash-attn into executable bounded rows if its gold adjudication can be persisted in-row.",
            "Construct at least four more non-tokenizers Rust roots with explicit verifier/test anchors before expecting a promotable Rust residual fix claim.",
        ],
        "outputs": {
            "root_manifest": display(ROOTS_JSONL),
            "bounded_rows": display(ROWS_JSONL),
            "pending_queue": display(QUEUE_JSONL),
        },
    }

    write_jsonl(ROOTS_JSONL, root_manifest)
    write_jsonl(ROWS_JSONL, rows)
    write_jsonl(QUEUE_JSONL, pending_queue)
    write_json(REQUEST_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "request": display(REQUEST_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
