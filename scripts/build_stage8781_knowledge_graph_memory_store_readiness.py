#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from knowledge_graph_memory_store import build_store_card

STAGE = 8781
NAME = "stage8781_knowledge_graph_memory_store_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "KNOWLEDGE_GRAPH_MEMORY_STORE_READINESS_STAGE8781.md"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}
ROWS = [
    {"node_type": "skill", "memory_key": "unsafe import repair", "tags": ["repair", "import"]},
    {"node_type": "source_fact", "memory_key": "hidden answer", "locked_eval_source": True},
    {"node_type": "bad_type", "memory_key": "schema review"},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_knowledge_graph_memory_store.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    sample = build_store_card(ROWS)
    sample_path = OUT_DIR / "knowledge_graph_memory_store_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures = []
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["node_count"] != 1:
        failures.append("sample_node_count_wrong")
    if sample["metrics"]["blocked_rows"] != 1:
        failures.append("sample_block_count_wrong")
    if sample["metrics"]["review_rows"] != 1:
        failures.append("sample_review_count_wrong")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "sample_rows": len(ROWS),
            "sample_nodes": sample["metrics"]["node_count"],
            "sample_edges": sample["metrics"]["edge_count"],
            "blocked_rows": sample["metrics"]["blocked_rows"],
            "review_rows": sample["metrics"]["review_rows"],
            "authority_rows": sample["metrics"]["authority_rows"],
            "failures": failures,
        },
        "artifacts": {
            "sample_card": str(sample_path.relative_to(ROOT)),
            "module": "scripts/knowledge_graph_memory_store.py",
            "tests": "tests/test_knowledge_graph_memory_store.py",
        },
        "decision": (
            "Knowledge graph memory store is ready as a no-authority typed node/edge memory scaffold with durable keys and contamination blocking."
            if not failures
            else "Knowledge graph memory store readiness failed."
        ),
        "next_best_step": "Recover latency_resource_observability, then repository_universe_builder.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage8781 Knowledge Graph Memory Store Readiness",
                "",
                f"Passed: `{card['passed']}`",
                "",
                "Recovered a typed graph-memory scaffold for skills, source facts, tool outcomes, repo entities, dataset patches, eval traces, and concepts.",
                "",
                "It provides durable memory keys, typed edges, tag/text retrieval, retrieval paths, schema review routes, and contamination/locked-eval blocking.",
                "",
                "Authority remains closed. This does not mine, train, execute tools, emit source/body, or promote trace-mined skills.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
