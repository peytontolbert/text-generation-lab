from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9709_symbol_binding_visible_evidence_target100m_contract_preflight_audit.py"
    spec = importlib.util.spec_from_file_location("stage9709", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9709_contract_only_command_targets_visible_evidence_manifest():
    mod = _load()
    cmd = mod.contract_only_command()
    joined = " ".join(cmd)
    assert cmd[:5] == ["conda", "run", "-n", "trellis", "python"]
    assert "--contract-only" in cmd
    assert "--execution-authorized-for-recovery-probe" not in cmd
    assert "--probe-scale target_100m" in joined
    assert "--mode symbol_binding_probe" in joined
    assert "--require-native-feature-ablation-audit" in cmd
    assert "--decoder-ce-weight 0.0" in joined
    assert "--denoise-weight 0.0" in joined
    assert "--structured-aux-weight 1.0" in joined
    assert "stage9708_symbol_binding_visible_evidence_manifest/symbol_binding_visible_evidence.jsonl" in joined
    assert "--max-train-rows 48" in joined
    assert "--max-eval-rows 22" in joined
    assert "--max-strict-rows 22" in joined


def test_stage9709_execution_candidate_keeps_boundaries_but_requires_explicit_flag():
    mod = _load()
    cmd = mod.execution_candidate_command()
    joined = " ".join(cmd)
    assert "--contract-only" not in cmd
    assert "--execution-authorized-for-recovery-probe" in cmd
    assert "--no-final-checkpoint-export" in cmd
    assert "--cleanup-checkpoints-after-probe" in cmd
    assert "stage9710_symbol_binding_visible_evidence_target100m_execution" in joined


def test_stage9709_source_visible_evidence_audit_is_below_shortcut_ceilings():
    mod = _load()
    audit = mod.load_json(mod.SOURCE_AUDIT)
    assert audit["passed"] is True
    assert audit["query_kind_action_baseline_exact"] < audit["query_kind_action_baseline_ceiling"]
    assert audit["strongest_single_feature_baseline_exact"] < audit["single_feature_baseline_ceiling"]
