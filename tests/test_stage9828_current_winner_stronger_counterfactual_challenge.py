from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9828_current_winner_stronger_counterfactual_challenge.py"
    spec = importlib.util.spec_from_file_location("stage9828", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9828_builds_complete_stronger_counterfactual_challenge_bank():
    mod = _load()
    rows = mod.build_rows()
    audit = mod.build_audit(rows)
    assert audit["passed"] is True
    assert audit["rows"] == 80
    assert audit["groups"] == 20
    assert audit["obligation_counts"]["POSITIVE_ORIGINAL"] == 20
    assert audit["obligation_counts"]["EVIDENCE_REMOVED"] == 20
    assert audit["obligation_counts"]["CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN"] == 20
    assert audit["obligation_counts"]["MIXED_REPLAY"] == 20
    assert audit["counterfactual_obligation_card"]["counterfactual_obligations_complete"] is True
    assert audit["visible_target_literal_rows"] == []


def test_stage9828_python_group_contains_four_distinct_roles_and_changes():
    mod = _load()
    rows = mod.build_rows()
    python_rows = [row for row in rows if row["language_family"] == "python"]
    group = [row for row in python_rows if row["counterfactual_root_row_id"] == 'stage9693_edit_localization_stage8765_row_4b8da5e64dd1c9b0']
    roles = {row["obligation_type"] for row in group}
    assert roles == {
        "POSITIVE_ORIGINAL",
        "EVIDENCE_REMOVED",
        "CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN",
        "MIXED_REPLAY",
    }
    removed = next(row for row in group if row["obligation_type"] == "EVIDENCE_REMOVED")
    contradictory = next(row for row in group if row["obligation_type"] == "CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN")
    mixed = next(row for row in group if row["obligation_type"] == "MIXED_REPLAY")
    assert removed["input_state"]["visible_locality_evidence"] == ""
    assert contradictory["target"]["decoder_text"] != next(row for row in group if row["obligation_type"] == "POSITIVE_ORIGINAL")["target"]["decoder_text"]
    assert "ignore irrelevant references" in mixed["input_state"]["task_observation"]
