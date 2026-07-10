from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9854_multisurface_abstention_honesty_manifests.py"
    spec = importlib.util.spec_from_file_location("stage9854", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9854_rewrite_patch_row_sets_abstain():
    mod = _load()
    row = {
        "clean_state": {
            "patch_operator": "ADD_IMPORT",
            "action_sequence": ["CHECK_IMPORT_POLICY", "PLAN_IMPORT_ADD"],
            "file_plan": "apply add_import",
        }
    }
    rewritten = mod._rewrite_patch_row(row)
    assert rewritten["clean_state"]["patch_operator"] == mod.ABSTAIN_LABEL
    assert rewritten["clean_state"]["action_sequence"] == [mod.ABSTAIN_LABEL]
    assert "insufficient" in rewritten["clean_state"]["file_plan"]


def test_stage9854_rewrite_verifier_row_sets_abstain():
    mod = _load()
    row = {
        "clean_state": {
            "verifier_repair_action": "REPAIR_IMPORT",
            "action_sequence": ["READ_IMPORT_ERROR", "PLAN_IMPORT_REPAIR"],
            "file_plan": "handle repair_import",
        }
    }
    rewritten = mod._rewrite_verifier_row(row)
    assert rewritten["clean_state"]["verifier_repair_action"] == mod.ABSTAIN_LABEL
    assert rewritten["clean_state"]["action_sequence"] == [mod.ABSTAIN_LABEL]
    assert "insufficient" in rewritten["clean_state"]["file_plan"]
