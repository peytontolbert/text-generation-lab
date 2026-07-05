from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from curriculum_compiler import REQUIRED_RECOVERED_GATE_REFERENCES
from source_backed_patch_operator_builder import build_card, build_source_backed_rows


def test_source_backed_patch_operator_builder_hides_operator_ids(tmp_path: Path) -> None:
    lineage_path = tmp_path / "lineage.json"
    lineage_path.write_text(json.dumps({"records": [
        {"path": "/arxiv/TOLBERT_BRAIN/data/repos/nodes_repos.jsonl", "source_id": "n", "lineage_hash": "hn"},
        {"path": "/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl", "source_id": "s", "lineage_hash": "hs"},
        {"path": "/arxiv/TOLBERT_BRAIN/data/repos/level_sizes_repos.json", "source_id": "l", "lineage_hash": "hl"},
    ]}), encoding="utf-8")
    neutral = [{
        "row_id": "old_ADD_IMPORT_row", "split": "train", "source_stage": "stage8638",
        "corrupted_state": {"language": "python", "file_extension": "py", "localized_edit_need": "approved dependency absent", "operator_signal": "approved_import_missing_visible", "target_scope_features": {"target_kind_hint": "file"}, "budget": {"decoder_budget_ok": False}},
        "clean_state": {"patch_operator": "ADD_IMPORT", "action_sequence": ["CHECK_IMPORT_POLICY"], "file_plan": "apply add_import"},
    }]
    rows = build_source_backed_rows(neutral, lineage_path)
    assert len(rows) == 1
    row = rows[0]
    assert "ADD_IMPORT" not in row["row_id"]
    assert "ADD_IMPORT" not in row["semantic_key"]
    assert set(row["gate_status"]) == set(REQUIRED_RECOVERED_GATE_REFERENCES)
    assert row["gate_status"]["source_inventory_lineage"] is True
    assert row["gate_status"]["contamination_leakage_detector"] is False
    assert not any(row["loss_mask"].values())
    assert build_card(rows)["training_loss_rows"] == 0
