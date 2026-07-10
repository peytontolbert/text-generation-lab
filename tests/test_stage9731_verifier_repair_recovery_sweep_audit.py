from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9731_verifier_repair_recovery_sweep_audit.py"
    spec = importlib.util.spec_from_file_location("stage9731", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9731_records_baseline_and_sweep_exactness():
    mod = _load()
    audit = mod.build_audit()
    assert audit["failures"] == []
    assert audit["baseline"]["eval_exact"] == 0.25
    assert audit["baseline"]["strict_exact"] == 0.25
    assert audit["sweep"]["steps64_lr5e5"]["eval_exact"] == 0.25
    assert audit["sweep"]["steps64_lr5e5"]["strict_exact"] == 0.25
    assert audit["sweep"]["steps128_lr1e4"]["eval_exact"] == 0.1875
    assert audit["sweep"]["steps128_lr1e4"]["strict_exact"] == 0.1875


def test_stage9731_no_sweep_run_improves_baseline():
    mod = _load()
    audit = mod.build_audit()
    assert audit["improved_runs"] == []
    assert audit["best_run"] == "steps64_lr5e5"
    assert audit["regressed_runs"] == ["steps128_lr1e4"]
