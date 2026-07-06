from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9063_long_context_compiler_loss_mask_graph_attachment import (  # noqa: E402
    NEW_EDGES,
    NEW_NODES,
    build_card,
)


def test_stage9063_graph_attachment_passes() -> None:
    built = build_card()
    assert built["passed"] is True
    assert built["authority_rows"] == 0
    assert built["added_edges"] >= len(NEW_EDGES)


def test_stage9063_graph_contains_compiler_and_loss_mask_controls() -> None:
    graph = build_card()["graph"]
    nodes = {node["id"] for node in graph["nodes"]}
    edges = {(edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"] if "source" in edge and "relation" in edge and "target" in edge}
    assert {node["id"] for node in NEW_NODES}.issubset(nodes)
    assert set(NEW_EDGES).issubset(edges)
    assert ("preflight:long_context_loss_mask_compiler_v1", "blocks", "objective:bounded_decoder_ce") in edges
    assert ("gate:long_context_compiler_handoff_blocker_v1", "guards", "compiler_stage:curriculum_compiler") in edges
