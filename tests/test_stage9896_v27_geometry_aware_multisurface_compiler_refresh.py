from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9896_v27_geometry_aware_multisurface_compiler_refresh.py"
    spec = importlib.util.spec_from_file_location("stage9896", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9896_uses_geometry_aware_edit_localization_source():
    mod = _load()
    assert mod.SOURCES["edit_localization"]["path"].name == "current_margin_locality_signal_label_remap_manifest.jsonl"
    assert mod.SOURCES["edit_localization"]["source_audit"].name == "stage9895_current_margin_locality_signal_label_remap_probe_audit.json"
    assert mod.SOURCES["patch_operator_selection"]["path"].name == "multilingual_patch_operator_abstention_honesty.jsonl"


def test_stage9896_normalize_ready_row_marks_geometry_refresh():
    mod = _load()
    row = {"row_id": "r1", "source_row_id": "src1", "anti_cheat": {}, "language_family": "python", "split": "eval"}
    out = mod._normalize_ready_row(row, "edit_localization", "edit_localization_ce", Path("runs/summaries/stage9895_current_margin_locality_signal_label_remap_probe_audit.json"))
    assert out["expected_enabled_loss"] == "edit_localization_ce"
    assert out["source_skill_area"] == "edit_localization"
    assert out["locked_guard_refresh_stage"] == mod.NAME
    assert out["anti_cheat"]["stage9896_geometry_aware_refresh"] is True
