from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9067_trainer_dry_run_controls_graph_attachment import NEW_EDGES, NEW_NODES, build_card  # noqa: E402


def test_stage9067_graph_attachment_passes() -> None:
    built = build_card()
    assert built["passed"] is True
    assert built["authority_rows"] == 0
    assert built["added_edges"] >= len(NEW_EDGES)


def test_stage9067_graph_contains_trainer_controls() -> None:
    graph = build_card()["graph"]
    nodes = {node["id"] for node in graph["nodes"]}
    edges = {(edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"] if "source" in edge and "relation" in edge and "target" in edge}
    assert {node["id"] for node in NEW_NODES}.issubset(nodes)
    assert set(NEW_EDGES).issubset(edges)
    assert ("gate:trainer_stops_before_model_forward", "blocks", "operation:model_forward") in edges
    assert ("audit:trainer_dry_run_input_negative_cases_v1", "rejects", "failure:authority_reopened") in edges
