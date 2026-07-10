from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9796_opaque_choice_review_packets.py"
    spec = importlib.util.spec_from_file_location("stage9796", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9796_builds_corrected_review_packets_and_workbook():
    mod = _load()
    built = mod.build_packets()
    assert built["passed"] is True
    assert built["metrics"]["winning_cells"] == 4
    assert built["metrics"]["workbook_tasks"] == 8
    assert built["metrics"]["rubric_tasks"] == 4
    assert built["metrics"]["anti_cheat_tasks"] == 4
    assert built["metrics"]["top_queue_entry"] == "opaque_choice_win::python::edit_localization::expert_maintainer_rubric_review"

    python_packet = next(row for row in built["packet_rows"] if row["language_family"] == "python")
    assert python_packet["same_surface_strict_exact_100m"] == 0.4
    assert python_packet["same_surface_strict_exact_gemma12b"] == 0.2
    assert python_packet["same_surface_verdict"] == "100m_better"


def test_stage9796_writes_reviewer_stub_payloads():
    mod = _load()
    built = mod.build_packets()
    python_packet = next(row for row in built["packet_rows"] if row["language_family"] == "python")
    rubric = json.loads((mod.ROOT / python_packet["review_packet_paths"]["expert_maintainer_rubric_scores"]).read_text(encoding="utf-8"))
    anti = json.loads((mod.ROOT / python_packet["review_packet_paths"]["anti_cheat_cards"]).read_text(encoding="utf-8"))
    assert rubric["status"] == "pending_human_review"
    assert rubric["same_surface_verdict"] == "100m_better"
    assert anti["status"] == "pending_cell_specific_review"
    assert anti["mapping_stable_across_splits"] is True
