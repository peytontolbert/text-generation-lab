from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9269_target_100m_denoise_probe_diagnostic_audit.py"
    spec = importlib.util.spec_from_file_location("stage9269", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9269_audits_safe_target_100m_denoise_probe():
    mod = _load()
    audit = mod.audit_run()
    assert audit["passed"] is True
    assert audit["rows"] == 21
    assert audit["train_rows"] == 8
    assert audit["eval_rows"] == 7
    assert audit["strict_rows"] == 6
    assert audit["estimated_parameter_count"] == 102668531
    assert audit["decoder_ce_rows"] == 0
    assert audit["train_loss_decreased"] is True
    assert audit["train_loss_end"] < audit["train_loss_start"]
    assert audit["post_clip_grad_norm_max"] <= 1.01
    assert audit["structured_head_delta_norm"] == 0.0
    assert audit["runtime_executed"] is False
    assert audit["gemma_executed"] is False
    assert audit["harness_executed"] is False
    assert audit["final_checkpoint_exported"] is False
    assert audit["required_artifacts_written"] is True
