from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9293_one_next_token_final_preexecution_audit.py"
    spec = importlib.util.spec_from_file_location("stage9293", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9293_command_is_ready_but_not_run():
    mod = _load()
    audit = mod.audit_preexecution()
    assert audit["passed"] is True
    assert audit["command_ready"] is True
    assert audit["will_execute_now"] is False
    assert audit["authorized_next_stage"] == 9294
    assert audit["manifest_rows"] == 6
    assert audit["authority"]["model_execution_authorized_next"] is True
    assert audit["authority"]["denoise_ce_training_authorized_next"] is True
    assert audit["authority"]["decoder_ce_training_authorized_next"] is False
    assert audit["authority"]["runtime_authorized"] is False
    assert mod.command_has_pair("--mode", "denoise_repair_probe")
    assert mod.command_has_pair("--probe-scale", "target_100m")
    assert mod.command_has_pair("--max-train-rows", "4")
    assert mod.command_has_pair("--max-eval-rows", "1")
    assert mod.command_has_pair("--max-strict-rows", "1")
    assert mod.command_has_pair("--max-decoder-tokens", "96")
    assert mod.command_has_pair("--decoder-ce-weight", "0.0")
    assert mod.command_has_pair("--denoise-weight", "1.0")
    assert mod.command_has_pair("--generation-audit-splits", "train,eval,strict_eval")
    assert "--execution-authorized-for-recovery-probe" in mod.COMMAND
    assert "--cleanup-checkpoints-after-probe" in mod.COMMAND


def test_stage9293_command_pair_helper():
    mod = _load()
    assert mod.command_has_pair("--mode", "denoise_repair_probe") is True
    assert mod.command_has_pair("--mode", "bounded_decoder_ce_probe") is False
