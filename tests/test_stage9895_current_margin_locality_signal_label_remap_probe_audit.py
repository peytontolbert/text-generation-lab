from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9895_current_margin_locality_signal_label_remap_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9895", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9895_audit_captures_removed_single_label_collapse():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    assert audit["metrics"]["eval_exact"] == 0.4375
    assert audit["metrics"]["strict_exact"] == 0.5
    assert audit["metrics"]["removed_single_label_collapse"] is True
    assert audit["metrics"]["pred_counts"] == {"R": 12, "T": 8, "Z": 12}
