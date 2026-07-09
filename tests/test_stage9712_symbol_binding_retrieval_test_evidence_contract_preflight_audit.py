from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9712_symbol_binding_retrieval_test_evidence_contract_preflight_audit.py"
    spec = importlib.util.spec_from_file_location("stage9712", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9712_contract_only_command_is_closed():
    mod = _load()
    cmd = mod.contract_only_command()
    joined = " ".join(cmd)
    assert "--contract-only" in cmd
    assert "--execution-authorized-for-recovery-probe" not in cmd
    assert "--probe-scale target_100m" in joined
    assert "--mode symbol_binding_probe" in joined
    assert "--require-native-feature-ablation-audit" in cmd
    assert "--decoder-ce-weight 0.0" in joined
    assert "--denoise-weight 0.0" in joined
    assert "stage9711_symbol_binding_retrieval_test_evidence_repair/symbol_binding_retrieval_test_evidence.jsonl" in joined


def test_stage9712_execution_candidate_requires_explicit_authorization():
    mod = _load()
    cmd = mod.execution_candidate_command()
    joined = " ".join(cmd)
    assert "--contract-only" not in cmd
    assert "--execution-authorized-for-recovery-probe" in cmd
    assert "--no-final-checkpoint-export" in cmd
    assert "stage9713_symbol_binding_retrieval_test_evidence_target100m_execution" in joined


def test_stage9712_source_audit_passed_shortcut_contract():
    mod = _load()
    audit = mod.load_json(mod.SOURCE_AUDIT)
    assert audit["passed"] is True
    assert audit["query_kind_action_baseline_exact"] < audit["query_kind_action_baseline_ceiling"]
    assert audit["strongest_single_feature_baseline_exact"] < audit["single_feature_baseline_ceiling"]
