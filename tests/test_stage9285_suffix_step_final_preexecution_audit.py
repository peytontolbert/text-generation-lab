from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9285_suffix_step_final_preexecution_audit.py"
    spec = importlib.util.spec_from_file_location("stage9285", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9285_final_preexecution_command_is_ready_but_not_run():
    mod = _load()
    audit = mod.audit_preexecution()
    assert audit["passed"] is True
    assert audit["command_ready"] is True
    assert audit["will_execute_now"] is False
    assert audit["authorized_next_stage"] == 9286
    assert audit["manifest_rows"] == 8
    assert audit["manifest_sha256"] == audit["review_manifest_sha256"]
    assert audit["authority"]["model_execution_authorized_next"] is True
    assert audit["authority"]["denoise_ce_training_authorized_next"] is True
    for key, value in audit["authority"].items():
        if key not in {"model_execution_authorized_next", "denoise_ce_training_authorized_next"}:
            assert value is False, key
    command = audit["command"]
    assert command[:5] == ["conda", "run", "-n", "trellis", "python"]
    assert "--execution-authorized-for-recovery-probe" in command
    assert "--require-loss-mask-enforcement-audit" in command
    assert "--no-final-checkpoint-export" in command
    assert "--cleanup-checkpoints-after-probe" in command
    assert mod.command_has_pair("--mode", "denoise_repair_probe")
    assert mod.command_has_pair("--decoder-ce-weight", "0.0")
    assert mod.command_has_pair("--denoise-weight", "1.0")
    assert mod.command_has_pair("--generation-prefix-field", "model_input.bridge_priming_span")
    assert mod.under(mod.OUTPUT_DIR, mod.ROOT / "runs/local/artifacts")
    assert "/arxiv" not in str(mod.OUTPUT_DIR)


def test_stage9285_command_pair_helper():
    mod = _load()
    assert mod.command_has_pair("--max-steps", "16") is True
    assert mod.command_has_pair("--max-steps", "999") is False


def test_stage9285_fails_if_review_not_authorized(monkeypatch):
    mod = _load()
    real_load = mod.load_json

    def fake_load(path):
        if path == mod.REVIEW:
            review = real_load(path)
            review["execution_authorized_next"] = False
            return review
        return real_load(path)

    monkeypatch.setattr(mod, "load_json", fake_load)
    audit = mod.audit_preexecution()
    assert audit["passed"] is False
    assert "review_did_not_authorize_execution_next" in audit["failures"]
