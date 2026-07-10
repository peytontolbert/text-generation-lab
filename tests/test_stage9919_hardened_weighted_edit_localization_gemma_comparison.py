from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9919_hardened_weighted_edit_localization_gemma_comparison.py"
    spec = importlib.util.spec_from_file_location("stage9919", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9919_uses_weighted_integrated_manifest_and_logits():
    mod = _load()
    assert mod.MANIFEST.name == "edit_localization_tiny.jsonl"
    assert "stage9917_hardened_weighted_structured_execution_review" in str(mod.MANIFEST)
    assert mod.ROWS_100M.name == "row_field_logits.jsonl"
    assert "surface_runs/edit_localization" in str(mod.ROWS_100M)
