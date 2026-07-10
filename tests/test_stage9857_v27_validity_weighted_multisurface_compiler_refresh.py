from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9857_v27_validity_weighted_multisurface_compiler_refresh.py"
    spec = importlib.util.spec_from_file_location("stage9857", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9857_uses_validity_weighted_sources():
    mod = _load()
    assert mod.SOURCES["edit_localization"]["path"].name == "permuted_choice_execution_manifest.jsonl"
    assert mod.SOURCES["patch_operator_selection"]["path"].name == "multilingual_patch_operator_abstention_honesty.jsonl"
    assert mod.SOURCES["verifier_failure_repair_or_abstain"]["path"].name == "multilingual_verifier_repair_abstention_honesty.jsonl"


def test_stage9857_normalize_ready_row_preserves_expected_loss():
    mod = _load()
    row = {"row_id": "r1", "source_row_id": "src1", "anti_cheat": {}, "language_family": "python", "split": "eval"}
    out = mod._normalize_ready_row(row, "patch_operator_selection", "patch_operator_ce", Path("runs/summaries/stage9854_multisurface_abstention_honesty_manifests.json"))
    assert out["expected_enabled_loss"] == "patch_operator_ce"
    assert out["source_skill_area"] == "patch_operator_selection"
    assert out["locked_guard_refresh_stage"] == mod.NAME
    assert out["anti_cheat"]["stage9857_validity_weighted_refresh"] is True
