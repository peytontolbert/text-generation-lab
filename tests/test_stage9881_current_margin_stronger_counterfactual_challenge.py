from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9881_current_margin_stronger_counterfactual_challenge.py"
    spec = importlib.util.spec_from_file_location("stage9881", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9881_builds_complete_current_margin_counterfactual_bank():
    mod = _load()
    rows = mod.build_rows()
    audit = mod.build_audit(rows)
    assert audit["passed"] is True
    assert audit["rows"] == 64
    assert audit["groups"] == 16
    assert audit["obligation_counts"]["POSITIVE_ORIGINAL"] == 16
    assert audit["obligation_counts"]["EVIDENCE_REMOVED"] == 16
    assert audit["obligation_counts"]["CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN"] == 16
    assert audit["obligation_counts"]["MIXED_REPLAY"] == 16
    assert audit["counterfactual_obligation_card"]["counterfactual_obligations_complete"] is True
    assert audit["visible_target_literal_rows"] == []


def test_stage9881_python_group_contains_four_distinct_roles_and_changes():
    mod = _load()
    rows = mod.build_rows()
    python_rows = [row for row in rows if row["language_family"] == "python"]
    group = [row for row in python_rows if row["counterfactual_root_row_id"] == 'stage9857_edit_localization_stage9693_edit_localization_stage8765_row_4b8da5e64dd1c9b0']
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
    original = next(row for row in group if row["obligation_type"] == "POSITIVE_ORIGINAL")
    assert removed["input_state"]["visible_locality_evidence"] == ""
    assert contradictory["target"]["decoder_text"] != original["target"]["decoder_text"]
    assert "ignore irrelevant references" in mixed["input_state"]["task_observation"]
