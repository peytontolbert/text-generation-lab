from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9874_v27_margin_objective_multisurface_compiler_refresh.py"
    spec = importlib.util.spec_from_file_location("stage9874_mod", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9874_mod"] = module
    spec.loader.exec_module(module)
    return module


def test_stage9874_edit_localization_source_is_stage9867_manifest():
    mod = _load()
    spec = mod.SOURCES["edit_localization"]
    assert "stage9867_edit_localization_label_identity_probe" in str(spec["path"])
    assert "stage9873_edit_localization_field_attention_margin_gemma_comparison" in str(spec["source_audit"])
