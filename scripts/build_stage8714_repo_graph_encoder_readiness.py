#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from repo_graph_encoder import encode_repo_graph

STAGE = 8714
NAME = "stage8714_repo_graph_encoder_readiness"
OUT_DIR = ROOT / f"runs/local/artifacts/{NAME}"
SUMMARY = ROOT / "runs/summaries/stage8714_repo_graph_encoder_readiness.json"
DOC = ROOT / "docs/REPO_GRAPH_ENCODER_READINESS_STAGE8714.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def run(cmd: list[str]) -> dict[str, Any]:
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {"cmd": cmd, "returncode": result.returncode, "passed": result.returncode == 0, "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:]}


def sample_graph() -> dict[str, Any]:
    return {
        "graph_id": "graph_opaque_stage8714",
        "nodes": [
            {"node_id": "n_repo", "node_type": "repo", "features": {"language": "python"}},
            {"node_id": "n_file", "node_type": "file", "features": {"suffix": ".py"}},
            {"node_id": "n_symbol", "node_type": "symbol", "features": {"kind": "function"}},
            {"node_id": "n_test", "node_type": "test", "features": {"kind": "unit"}},
        ],
        "edges": [
            {"src": "n_repo", "dst": "n_file", "edge_type": "contains"},
            {"src": "n_file", "dst": "n_symbol", "edge_type": "defines"},
            {"src": "n_test", "dst": "n_symbol", "edge_type": "test_covers"},
        ],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    compile_result = run([sys.executable, "-m", "py_compile", "scripts/repo_graph_encoder.py"])
    tests = run([sys.executable, "-m", "pytest", "-q", "tests/test_repo_graph_encoder.py"])
    sample = encode_repo_graph(sample_graph(), dim=32, rounds=2)
    passed = compile_result["passed"] and tests["passed"] and sample["passed"] and len(sample["node_embeddings"]) == 4
    metrics = {
        "authority_rows": 0,
        "sample_nodes": sample["audit"]["node_count"],
        "sample_edges": sample["audit"]["edge_count"],
        "endpoint_failures": sample["audit"]["endpoint_failure_count"],
        "label_leak_count": sample["audit"]["label_leak_count"],
        "embedding_dim": sample["dim"],
        "message_passing_rounds": sample["rounds"],
        **AUTHORITY_CLOSED,
    }
    card = {
        "stage": STAGE,
        "name": NAME,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "checks": {"compile": compile_result, "tests": tests},
        "sample_encoding": sample,
        "decision": "Recovered deterministic repo graph encoder/message-passing scaffold; learned GNN training remains closed.",
        "next_best_step": "Attach repo graph encoder to central graph, then recover rubric judge calibration or operator inventory/codelength interfaces.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "repo_graph_encoder_readiness_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "sample_repo_graph_encoding.json").write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        f"# Stage {STAGE}: Repo Graph Encoder Readiness",
        "",
        f"Passed: `{passed}`",
        "",
        "Recovered deterministic message-passing scaffold:",
        "",
        "- endpoint and label-coded ID audit",
        "- node-type and relation feature hashing",
        "- in/out degree features",
        "- fixed-round neighbor message passing",
        "- graph embedding and node embedding hashes",
        "",
        "This is not learned GNN training. It only defines the graph encoding interface for future structured probes.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
