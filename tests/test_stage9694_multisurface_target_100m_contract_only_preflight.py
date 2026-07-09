from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9694_multisurface_target_100m_contract_only_preflight.py"
    spec = importlib.util.spec_from_file_location("stage9694", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_enabled_loss_requires_exactly_one_enabled_loss():
    mod = _load()
    assert mod.enabled_loss({"loss_mask": {"symbol_binding_ce": True}}) == "symbol_binding_ce"
    assert mod.enabled_loss({"loss_mask": {"symbol_binding_ce": True, "edit_localization_ce": True}}) is None
    assert mod.enabled_loss({"loss_mask": {}}) is None


def test_trainer_command_uses_surface_mode_and_target100m_flags(tmp_path: Path):
    mod = _load()
    manifest = mod.ROOT / "runs/local/artifacts/stage9694_multisurface_target_100m_contract_only_preflight/manifests/symbol_binding.jsonl"
    rows = [{"split": "train"}, {"split": "eval"}, {"split": "strict_eval"}]
    cmd = mod.trainer_command("symbol_binding", manifest, rows)
    joined = " ".join(cmd)
    assert "--mode symbol_binding_probe" in joined
    assert "--probe-scale target_100m" in joined
    assert "--structured-aux-weight 1.0" in joined
    assert "--decoder-ce-weight 0.0" in joined
    assert "--contract-only" in cmd
    assert "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json" in cmd


def test_bounded_command_uses_decoder_ce_mode():
    mod = _load()
    manifest = mod.ROOT / "runs/local/artifacts/stage9694_multisurface_target_100m_contract_only_preflight/manifests/bounded_argument_rendering.jsonl"
    rows = [{"split": "train"}]
    cmd = mod.trainer_command("bounded_argument_rendering", manifest, rows)
    joined = " ".join(cmd)
    assert "--mode bounded_decoder_ce_probe" in joined
    assert "--decoder-ce-weight 1.0" in joined
    assert "--structured-aux-weight 0.0" in joined
    assert "--enable-generation-audit" in cmd
