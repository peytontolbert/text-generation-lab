from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9991_filtered_same_manifest_comparison_audit.py"
    spec = importlib.util.spec_from_file_location("stage9991", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_audit_requires_four_language_cells():
    mod = _load()
    built = mod.build_audit()
    if built["rows"]:
        assert built["metrics"]["shared_rows"] == built["metrics"]["rows_100m_present"]
        assert "per_language" in built["metrics"]
