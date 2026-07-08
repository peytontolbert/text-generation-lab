from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9255_precomputed_repo_state_transformation_spine.py"
    spec = importlib.util.spec_from_file_location("stage9255", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9255_card_captures_precomputed_repo_state_spine():
    mod = _load()
    card = mod.build_card()
    assert card["passed"] is True
    assert card["state_equations"]["maintenance_state"] == "S_t = Contract(Psi_R, O_q, h_t)"
    assert "ast_cst_structure" in card["precomputable_layers"]
    assert "patch_affordance_index" in card["precomputable_layers"]
    assert "task_intent_observable" in card["online_components"]
    assert "repo_state_compiler_cache_manifest" in card["next_objectives"]
    assert all(value is False for value in card["authority"].values())
