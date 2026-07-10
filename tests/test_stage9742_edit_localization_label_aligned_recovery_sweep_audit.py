from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9742_edit_localization_label_aligned_recovery_sweep_audit.py"
    spec = importlib.util.spec_from_file_location("stage9742", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9742_records_no_improvement_over_stage9733():
    mod = _load()
    audit = mod.build_audit()
    assert audit["failures"] == []
    assert audit["baseline"]["eval_exact"] == 1 / 7
    assert audit["baseline"]["strict_exact"] == 1 / 7
    assert audit["sweep"]["steps128_lr5e5"]["eval_exact"] == 1 / 7
    assert audit["sweep"]["steps128_lr1e4"]["eval_exact"] == 1 / 7
    assert audit["improved_runs"] == []
