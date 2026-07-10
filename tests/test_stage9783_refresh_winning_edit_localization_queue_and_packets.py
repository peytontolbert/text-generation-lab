from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9783_refresh_winning_edit_localization_queue_and_packets.py"
    spec = importlib.util.spec_from_file_location("stage9783", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9783_refreshes_queue_and_packet_metadata_to_visible_evidence_winner():
    mod = _load()
    built = mod.build_refresh()
    assert built["passed"] is True
    assert built["metrics"]["refreshed_cells"] == 4
    assert built["metrics"]["winning_cells_now_point_to_stage9773"] == 4

    root = Path(__file__).resolve().parents[1]
    queue = json.loads((root / "runs/local/artifacts/stage9748_supported_standalone_gemma_queue/supported_standalone_gemma_queue.json").read_text(encoding="utf-8"))
    packets = [json.loads(line) for line in (root / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    queue_row = next(row for row in queue["queue_entries"] if row["cell_key"] == "standalone_100m_weights::python::edit_localization")
    packet_row = next(row for row in packets if row["cell_key"] == "standalone_100m_weights::python::edit_localization")

    assert queue_row["priority_score"] == 1.0
    assert queue_row["same_surface_packet"]["source_stage"] == 9773
    assert queue_row["same_surface_packet"]["source_manifest"].endswith("stage9771_edit_localization_visible_evidence_lift_package/edit_localization_visible_evidence_lift.jsonl")
    assert queue_row["same_surface_packet"]["strict_exact"] == 1.0
    assert queue_row["same_surface_packet"]["eval_exact"] == 1.0
    assert queue_row["same_surface_packet"]["split_counts"] == {"train": 5, "eval": 5, "strict_eval": 5}

    comparison = packet_row["merge_ready_bundle_template"]["same_surface_comparison"]
    assert comparison["score_100m"] == 1.0
    assert comparison["score_gemma12b"] == 0.2
    assert comparison["hundred_m_beats_gemma12b"] is True
    assert comparison["same_surface_verified"] is True
    assert packet_row["same_surface_packet"]["source_stage"] == 9773
    assert packet_row["same_surface_packet"]["row_count"] == 15
    assert packet_row["supporting_evidence_refs"][0]["stage"] == 9775
