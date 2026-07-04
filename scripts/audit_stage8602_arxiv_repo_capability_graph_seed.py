#!/usr/bin/env python3
"""Audit Stage8601 repo capability and graph seed artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


FORBIDDEN_ID_TERMS = {
    "symbol_binding",
    "edit_localization",
    "patch_operator",
    "verifier_repair",
    "bounded_decoder",
    "repo_capability_catalog",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default="runs/local/artifacts/stage8601_arxiv_repo_capability_and_graph_seed")
    args = parser.parse_args()
    artifact_dir = Path(args.artifact_dir)
    catalog = load_jsonl(artifact_dir / "repo_capability_catalog.jsonl")
    graphs = load_jsonl(artifact_dir / "repo_state_graph_seed.jsonl")

    authority_rows = 0
    decoder_rows = 0
    raw_source_rows = 0
    endpoint_failures = 0
    label_id_leaks = 0
    split_counts = Counter()
    language_counts = Counter()
    build_counts = Counter()
    objective_rows = Counter()

    for row in catalog:
        split_counts[row["split"]] += 1
        language_counts.update(row["model_input"].get("language_families", []))
        build_counts.update(row["model_input"].get("build_system_families", []))
        objective_rows[row["objective_family"]] += 1
        auth = row.get("authority", {})
        if any(auth.values()):
            authority_rows += 1
        loss = row.get("loss_mask", {})
        if loss.get("decoder_ce"):
            decoder_rows += 1
        if row.get("source_ref", {}).get("source_in_model_input"):
            raw_source_rows += 1
        row_id = row.get("row_id", "").lower()
        if any(term in row_id for term in FORBIDDEN_ID_TERMS):
            label_id_leaks += 1

    for row in graphs:
        objective_rows[row["objective_family"]] += 1
        graph = row["graph_input"]
        ids = {node["node_id"] for node in graph["nodes"]}
        for edge in graph["edges"]:
            if edge["src"] not in ids or edge["dst"] not in ids:
                endpoint_failures += 1
        all_ids = [graph["graph_id"]] + list(ids)
        if any(any(term in value.lower() for term in FORBIDDEN_ID_TERMS) for value in all_ids):
            label_id_leaks += 1
        auth = row.get("authority", {})
        if any(auth.values()):
            authority_rows += 1
        loss = row.get("loss_mask", {})
        if loss.get("decoder_ce"):
            decoder_rows += 1
        if row.get("source_ref", {}).get("source_in_model_input"):
            raw_source_rows += 1

    enough_split_coverage = all(split_counts.get(split, 0) > 0 for split in ["train", "eval", "strict_eval"])
    enough_language_coverage = len([lang for lang, count in language_counts.items() if count > 0]) >= 4
    enough_build_coverage = len([name for name, count in build_counts.items() if count > 0]) >= 4

    metrics = {
        "catalog_rows": len(catalog),
        "graph_seed_rows": len(graphs),
        "split_counts": dict(split_counts),
        "language_counts": dict(language_counts),
        "build_system_counts": dict(build_counts),
        "objective_rows": dict(objective_rows),
        "authority_rows": authority_rows,
        "decoder_ce_rows": decoder_rows,
        "raw_source_rows": raw_source_rows,
        "endpoint_failures": endpoint_failures,
        "label_id_leak_rows": label_id_leaks,
        "enough_split_coverage": enough_split_coverage,
        "enough_language_coverage": enough_language_coverage,
        "enough_build_coverage": enough_build_coverage,
        "model_ready_training_rows": 0,
        "seed_rows_only": True
    }
    passed = (
        len(catalog) > 0
        and len(graphs) > 0
        and authority_rows == 0
        and decoder_rows == 0
        and raw_source_rows == 0
        and endpoint_failures == 0
        and label_id_leaks == 0
        and enough_split_coverage
        and enough_language_coverage
        and enough_build_coverage
    )
    summary = {
        "stage": 8602,
        "name": "stage8602_reconstructed_arxiv_repo_capability_graph_seed_audit",
        "passed": passed,
        "summary": "Audited Stage8601 repo capability catalog and repo-state graph seeds. Rows are suitable as closed-authority compiler seed/catalog inputs, not as training rows.",
        "metrics": metrics,
        "gates": {
            "authority_rows": authority_rows,
            "decoder_ce_rows": decoder_rows,
            "raw_source_rows": raw_source_rows,
            "endpoint_failures": endpoint_failures,
            "label_id_leak_rows": label_id_leaks,
            "body_emission_authorized": False,
            "source_emission_authorized": False,
            "runtime_authorized": False,
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "transition_head_training_authorized_next": False,
            "gemma_execution_authorized_next": False,
            "harness_execution_authorized_next": False,
            "scoring_authorized_next": False,
            "controller_complete_merge_authorized_next": False,
            "promotion_ready": False
        },
        "next_best_step": "Extract symbol/import/test binding candidates from selected /arxiv repositories with opaque IDs and shortcut baselines."
    }
    write_json(artifact_dir / "audit_card.json", metrics)
    write_json(Path("runs/summaries/stage8602_reconstructed_arxiv_repo_capability_graph_seed_audit.json"), summary)
    print(json.dumps({"passed": passed, "metrics": metrics}, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
