from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9302_causal_mask_boundary_probe_preexecution.py"
    spec = importlib.util.spec_from_file_location("stage9302", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9302_prepares_causal_mask_boundary_probe_command_with_data_tmp():
    mod = _load()
    card = mod.audit()
    assert card["passed"] is True
    assert card["command_ready"] is True
    assert card["will_execute_now"] is False
    assert card["authorized_next_stage"] == 9303
    assert card["manifest_rows"] == 6
    assert card["tmpdir"] == "/data/tmp"
    assert card["command"][:4] == ["env", "TMPDIR=/data/tmp", "TEMP=/data/tmp", "TMP=/data/tmp"]
    assert card["required_postrun_artifact"] == "boundary_next_token_logits.jsonl"
    assert card["authority"]["model_execution_authorized_next"] is True
    assert card["authority"]["denoise_ce_training_authorized_next"] is True
    assert card["authority"]["decoder_ce_training_authorized_next"] is False
    assert mod.has_pair("--generation-audit-splits", "train,eval,strict_eval")
    assert mod.has_pair("--max-generation-rows", "6")
    assert mod.has_pair("--max-decoder-tokens", "96")
