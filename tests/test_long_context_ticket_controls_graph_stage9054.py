from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9054_long_context_ticket_controls_graph_attachment import (  # noqa: E402
    NEW_EDGES,
    NEW_NODES,
    build_graph_card,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def test_stage9054_graph_card_attaches_ticket_controls() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_stage9053_long_context_source_output_ticket_audit.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    built = build_graph_card()
    assert built["passed"] is True
    graph = built["graph"]
    ids = {node["id"] for node in graph["nodes"]}
    assert {node["id"] for node in NEW_NODES}.issubset(ids)
    edges = {(edge.get("source"), edge.get("relation"), edge.get("target")) for edge in graph["edges"]}
    assert set(NEW_EDGES).issubset(edges)
    attached = [node for node in graph["nodes"] if node["id"] in {item["id"] for item in NEW_NODES}]
    assert all(node.get("authority") == AUTHORITY_CLOSED for node in attached)


def test_stage9054_builder_materializes_closed_summary() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_stage9054_long_context_ticket_controls_graph_attachment.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    summary = json.loads(result.stdout)
    assert summary["passed"] is True
    assert summary["metrics"]["source_reads_authorized_now"] is False
    assert summary["metrics"]["candidate_mining_authorized_now"] is False
    assert summary["metrics"]["training_authorized"] is False
