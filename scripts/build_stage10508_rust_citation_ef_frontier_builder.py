from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage10508_rust_citation_ef_frontier_builder"

FRONTIER_REQUEST = ROOT / "runs/local/artifacts/stage10506_fresh_python_rust_frontier_request/fresh_python_rust_frontier_request.json"
SCALING_TARGETS = ROOT / "runs/local/artifacts/stage10505_multilingual_residual_root_scaling_queue/multilingual_residual_root_scaling_targets.jsonl"
RUST_ATLAS = ROOT / "runs/local/artifacts/stage10411_fresh_rust_disjoint_root_candidate_atlas/fresh_rust_disjoint_root_candidate_atlas.json"
RUST_ROWS = ROOT / "runs/local/artifacts/stage10411_fresh_rust_disjoint_root_candidate_atlas/fresh_rust_disjoint_root_candidate_rows.jsonl"
RUST_CITATION_ROWS = ROOT / "runs/local/artifacts/stage10452_rust_evidence_citation_candidate_atlas/rust_evidence_citation_candidate_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    frontier_request = load_json(FRONTIER_REQUEST)
    scaling_targets = [row for row in load_jsonl(SCALING_TARGETS) if row["language_family"] == "rust"]
    rust_atlas = load_json(RUST_ATLAS)
    rust_rows = load_jsonl(RUST_ROWS)
    rust_citation_rows = load_jsonl(RUST_CITATION_ROWS)

    builder_targets = [row for row in scaling_targets if row["status"] == "builder_target_not_yet_materialized"]
    diagnostic_targets = [row for row in scaling_targets if row["status"] != "builder_target_not_yet_materialized"]

    top_candidates = rust_atlas["top_fresh_candidates"][:6]
    seed_train_rows = [
        row for row in rust_citation_rows if row["source_bundle_id"] == "stage10126::candle::candle-core::rust"
    ]

    summary = {
        "stage": 10508,
        "stage_name": "stage10508_rust_citation_ef_frontier_builder",
        "frontier_contract": frontier_request["frontiers"]["rust_citation_ef_frontier_v1"],
        "seed_supply_summary": {
            "builder_target_count": len(builder_targets),
            "diagnostic_target_count": len(diagnostic_targets),
            "existing_candle_core_seed_rows": len(seed_train_rows),
            "existing_unique_perm_rows": len({row["row_id"] for row in seed_train_rows}),
        },
        "builder_plan": [
            "Use candle-core compact-bounded evidence_citation rows only as interim train-support seed; they do not satisfy the real E-vs-F disjoint-root requirement.",
            "Prioritize candle-flash-attn first because it is the only top fresh candidate with implementation-vs-test geometry and an actual test file.",
            "Then materialize linux::rust, candle-datasets, and candle-transformers as non-tokenizers fresh heldout roots, attaching verifier or trace anchors where recoverable.",
            "Keep tokenizers same-surface rows completely out of promotable support and use them only as residual canaries after fresh-root evaluation exists.",
        ],
        "required_row_contract": [
            "perspective == evidence_citation",
            "symptom_or_call_path_analogue and verifier_and_test_constraint both visible as options",
            "candidate_change_surface remains a tempting wrong answer",
            "gold support fact must not appear verbatim before options",
            "strict heldout rows must come from non-tokenizers roots",
        ],
        "fresh_root_priority_queue": [
            {
                "candidate_root_id": row["candidate_root_id"],
                "repo_id": row["repo_id"],
                "competition_geometries": row["competition_geometries"],
                "review_ready_for_bundle_construction": row["review_ready_for_bundle_construction"],
                "test_file_count": row["test_file_count"],
                "build_file_count": row["build_file_count"],
                "priority_score": row["priority_score"],
                "recommendation": row["recommendation"],
            }
            for row in top_candidates
        ],
        "diagnostic_support_only": diagnostic_targets,
        "materialized_seed_rows_source_manifests": sorted(
            {row["source_manifest_name"] for row in seed_train_rows}
        ),
        "row_budget_targets": frontier_request["frontiers"]["rust_citation_ef_frontier_v1"]["row_budget"],
    }

    (ARTIFACT_DIR / "rust_citation_ef_frontier_builder.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (ARTIFACT_DIR / "rust_citation_ef_seed_rows.jsonl").open("w", encoding="utf-8") as handle:
        for row in seed_train_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    with (ARTIFACT_DIR / "rust_citation_ef_fresh_root_priority_queue.jsonl").open("w", encoding="utf-8") as handle:
        for row in top_candidates:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
