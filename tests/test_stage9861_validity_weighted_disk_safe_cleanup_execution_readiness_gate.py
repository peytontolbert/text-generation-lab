from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9861_validity_weighted_disk_safe_cleanup_execution_readiness_gate.py"
    spec = importlib.util.spec_from_file_location("stage9697", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_future_command_uses_stage9862_and_no_decoder():
    mod = _load()
    cmd = mod.future_command()
    joined = " ".join(cmd)
    assert "stage9862_symbol_binding_target_100m_structured_tiny_probe" in joined
    assert cmd[0].endswith("/miniconda3/envs/ai/bin/python") or cmd[0] == "python"
    assert "stage9860_" not in joined
    assert "--mode symbol_binding_probe" in joined
    assert "--decoder-ce-weight 0.0" in joined
    assert "--execution-authorized-for-recovery-probe" in cmd
    checks, failures = mod.future_command_checks(cmd)
    assert failures == []
    assert checks["future_command_uses_fresh_stage9862_namespace"] is True


def test_negative_safety_checks_reject_roots_and_destructive_tokens():
    mod = _load()
    checks, failures = mod.negative_safety_checks()
    assert failures == []
    assert checks["reject_arxiv_output"] is True
    assert checks["reject_data_output"] is True
    assert checks["reject_root_output"] is True
    assert checks["reject_rm_rf_arxiv_token"] is True
    assert checks["reject_rm_rf_data_token"] is True
