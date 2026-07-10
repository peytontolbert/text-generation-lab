from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9908_direct_geometry_aware_opaque_choice_exec.py"
    spec = importlib.util.spec_from_file_location("stage9908", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9908_runner_targets_stage9907_manifest():
    mod = _load()
    runner = mod.build_runner_text()
    assert "stage9907_geometry_aware_opaque_choice_manifest" in runner
    assert "stage9908_direct_geometry_aware_opaque_choice_exec" in runner
    assert "max_train_rows=16" in runner
    assert "restore_best_structured_state=True" in runner

