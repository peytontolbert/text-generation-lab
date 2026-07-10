from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9736_multilingual_patch_operator_label_aligned_execution_audit.py"
    spec = importlib.util.spec_from_file_location("stage9736", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9736_reads_baseline_zero_exact():
    mod = _load()
    baseline = mod.load_json(mod.BASELINE)
    assert mod._exact(baseline, "eval") == 0.0
    assert mod._exact(baseline, "strict_eval") == 0.0
