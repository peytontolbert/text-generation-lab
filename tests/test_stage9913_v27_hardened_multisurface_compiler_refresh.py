from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9913_v27_hardened_multisurface_compiler_refresh.py"
    spec = importlib.util.spec_from_file_location("stage9913", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9913_uses_hardened_edit_localization_source():
    mod = _load()
    assert mod.SOURCES["edit_localization"]["path"].name == "geometry_aware_opaque_choice_manifest.jsonl"
    assert mod.SOURCES["edit_localization"]["source_audit"].name == "stage9910_geometry_aware_opaque_choice_shortcut_audit.json"
    assert mod.SOURCES["patch_operator_selection"]["path"].name == "multilingual_patch_operator_abstention_honesty.jsonl"

