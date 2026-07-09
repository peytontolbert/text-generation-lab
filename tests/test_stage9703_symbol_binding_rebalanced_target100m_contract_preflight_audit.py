from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9703_symbol_binding_rebalanced_target100m_contract_preflight_audit.py"
    spec = importlib.util.spec_from_file_location("stage9703", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9703_contract_card_is_target100m_native_ablation_preflight():
    mod = _load()
    card = mod.load_json(mod.CONTRACT_CARD)
    assert card["passed"] is True
    assert card["mode"] == "symbol_binding_probe"
    assert card["probe_scale"] == "target_100m"
    assert card["native_feature_ablation_audit_required"] is True
    assert card["model_execution_attempted"] is False
    assert card["loss_counts"]["symbol_binding_ce"] == 64
    assert card["split_counts"] == {"train": 32, "eval": 16, "strict_eval": 16, "other": 0}
    assert card["tokenizer_contract"]["byte_fallback_used_when_unset"] is False


def test_stage9703_candidate_command_keeps_closed_boundaries():
    mod = _load()
    cmd = mod.execution_candidate_command()
    joined = " ".join(cmd)
    assert cmd[:5] == ["conda", "run", "-n", "trellis", "python"]
    assert "--probe-scale target_100m" in joined
    assert "--require-native-feature-ablation-audit" in cmd
    assert "--decoder-ce-weight 0.0" in joined
    assert "--denoise-weight 0.0" in joined
    assert "--no-final-checkpoint-export" in cmd
    assert "--execution-authorized-for-recovery-probe" in cmd
    assert "stage9704_symbol_binding_rebalanced_target100m_execution" in joined
