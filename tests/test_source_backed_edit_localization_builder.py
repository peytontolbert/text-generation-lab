from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from curriculum_compiler import REQUIRED_RECOVERED_GATE_REFERENCES
from source_backed_edit_localization_builder import build_card, build_source_backed_rows


def test_source_backed_edit_localization_builder_hides_target_ids(tmp_path: Path) -> None:
    lineage = {
        "records": [
            {"path": "/arxiv/TOLBERT_BRAIN/data/repos/nodes_repos.jsonl", "source_id": "n", "lineage_hash": "hn"},
            {"path": "/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl", "source_id": "s", "lineage_hash": "hs"},
            {"path": "/arxiv/TOLBERT_BRAIN/data/repos/level_sizes_repos.json", "source_id": "l", "lineage_hash": "hl"},
        ]
    }
    lineage_path = tmp_path / "lineage.json"
    lineage_path.write_text(json.dumps(lineage), encoding="utf-8")
    neutral = [{
        "row_id": "old_TARGET_FILE_row",
        "split": "train",
        "source_stage": "stage8636",
        "corrupted_state": {
            "language": "python",
            "file_extension": "py",
            "task_observation": "failure points near behavior",
            "visible_locality_evidence": "file responsibility is visible",
            "locality_signal": "file_responsibility_visible",
            "neutral_context_bits": {"tests_visible": True},
            "budget": {"decoder_budget_ok": False},
            "graph_packet": {"opaque_graph_id": "g0", "query_node_type": "failure_log", "edge_family_count": 2, "candidate_node_count": 3},
        },
        "clean_state": {"edit_localization_target": "TARGET_FILE", "action_sequence": ["READ_FILE"], "file_plan": "localize target_file"},
    }]
    rows = build_source_backed_rows(neutral, lineage_path)
    assert len(rows) == 1
    row = rows[0]
    assert "TARGET_FILE" not in row["row_id"]
    assert "TARGET_FILE" not in row["semantic_key"]
    assert set(row["gate_status"]) == set(REQUIRED_RECOVERED_GATE_REFERENCES)
    assert row["gate_status"]["source_inventory_lineage"] is True
    assert row["gate_status"]["contamination_leakage_detector"] is False
    assert not any(row["loss_mask"].values())
    card = build_card(rows)
    assert card["rows"] == 1
    assert card["training_loss_rows"] == 0
