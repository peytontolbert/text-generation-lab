from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9904_current_margin_locality_signal_neutral_label_target_100m_probe.py"
    spec = importlib.util.spec_from_file_location("stage9904", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9904_runner_targets_neutral_manifest_and_probe_dir():
    mod = _load()
    runner = mod.build_runner_text()
    assert "stage9903_current_margin_locality_signal_neutral_label_manifest" in runner
    assert "stage9904_current_margin_locality_signal_neutral_label_target_100m_probe/edit_localization_probe" in runner
    assert "mode='edit_localization_probe'" in runner
    assert "max_train_rows=16" in runner
    assert "max_eval_rows=16" in runner
    assert "max_strict_rows=16" in runner
    assert "max_steps=32" in runner
    assert "restore_best_structured_state=True" in runner
