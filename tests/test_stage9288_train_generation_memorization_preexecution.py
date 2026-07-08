from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9288_train_generation_memorization_preexecution.py"
    spec = importlib.util.spec_from_file_location("stage9288", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9288_prepares_train_generation_memorization_command():
    mod = _load()
    card = mod.audit()
    assert card["passed"] is True
    assert card["command_ready"] is True
    assert card["will_execute_now"] is False
    assert card["authorized_next_stage"] == 9289
    assert card["generation_audit_splits"] == "train,eval,strict_eval"
    assert card["authority"]["model_execution_authorized_next"] is True
    assert card["authority"]["denoise_ce_training_authorized_next"] is True
    assert mod.has_pair("--generation-audit-splits", "train,eval,strict_eval")
    assert mod.has_pair("--generation-prefix-field", "model_input.bridge_priming_span")
    assert mod.has_pair("--decoder-ce-weight", "0.0")
    assert mod.has_pair("--denoise-weight", "1.0")
