from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9901_geometry_aware_edit_localization_gemma_comparison.py"
    spec = importlib.util.spec_from_file_location("stage9901_cmp", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9901_cmp"] = module
    spec.loader.exec_module(module)
    return module


def test_stage9901_build_audit_dry_run_shapes_results():
    mod = _load()
    audit, rows = mod.build_audit(execute_gemma=False)
    assert audit["passed"] is True
    assert audit["gemma_executed"] is False
    assert set(audit["splits"]) == {"eval", "strict_eval"}
    assert len(audit["comparisons"]) == 8
    assert len(rows) == 32
    assert rows[0]["raw_output"] == "[dry-run]"


def test_stage9901_uses_geometry_aware_paths():
    mod = _load()
    assert "stage9899_geometry_aware_structured_tiny_execution_review" in str(mod.MODEL_ROWS)
    assert "stage9893_current_margin_locality_signal_label_remap_manifest" in str(mod.MANIFEST)
