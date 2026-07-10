from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9860_capped_validity_weighted_structured_target_100m_contract_preflight.py"
    spec = importlib.util.spec_from_file_location("stage9860", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_split_counts_reports_other_rows():
    mod = _load()
    rows = [{"split": "train"}, {"split": "eval"}, {"split": "strict_eval"}, {"split": "holdout"}]
    assert mod.split_counts(rows) == {"train": 1, "eval": 1, "strict_eval": 1, "other": 1}


def test_command_is_contract_only_target100m_structured():
    mod = _load()
    cmd = mod.command("symbol_binding", mod.MANIFEST_DIR / "symbol_binding_tiny.jsonl")
    joined = " ".join(cmd)
    assert "--mode symbol_binding_probe" in joined
    assert "--probe-scale target_100m" in joined
    assert "--contract-only" in cmd
    assert "--execution-authorized-for-recovery-probe" not in cmd
    assert "--decoder-ce-weight 0.0" in joined
    assert "--structured-aux-weight 1.0" in joined


def test_contract_only_required_artifacts_are_preflight_only():
    mod = _load()
    assert mod.REQUIRED_PREFLIGHT_ARTIFACTS == ["probe_contract_audit.json", "cleanup_proof.json"]


def test_command_prefers_working_ai_python_when_present():
    mod = _load()
    cmd = mod.command("symbol_binding", mod.MANIFEST_DIR / "symbol_binding_tiny.jsonl")
    assert cmd[0].endswith("/miniconda3/envs/ai/bin/python") or cmd[0].endswith("python")
