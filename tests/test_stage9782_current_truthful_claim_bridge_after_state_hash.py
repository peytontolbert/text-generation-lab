from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9782_current_truthful_claim_bridge_after_state_hash.py"
    spec = importlib.util.spec_from_file_location("stage9782", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9782_reduces_winning_cells_to_review_only_missing_items():
    mod = _load()
    built = mod.build_bridge()
    assert built["passed"] is True
    assert built["metrics"]["refreshed_cells"] == 4
    assert built["metrics"]["winning_cells_missing_review_only"] == 4

    row = next(
        item for item in built["records"]
        if item["cell_key"] == "standalone_100m_weights::python::edit_localization"
    )
    assert row["missing_required_evidence"] == ["expert_maintainer_rubric_scores", "anti_cheat_cards"]
    assert "missing_required_evidence:frozen_export_or_checkpoint_hash" not in row["blockers"]
