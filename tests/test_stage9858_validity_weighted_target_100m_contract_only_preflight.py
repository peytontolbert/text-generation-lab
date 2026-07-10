from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9858_validity_weighted_target_100m_contract_only_preflight.py"
    spec = importlib.util.spec_from_file_location("stage9858", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_enabled_loss_requires_exactly_one_enabled_loss():
    mod = _load()
    assert mod.enabled_loss({"loss_mask": {"symbol_binding_ce": True}}) == "symbol_binding_ce"
    assert mod.enabled_loss({"loss_mask": {"symbol_binding_ce": True, "edit_localization_ce": True}}) is None
    assert mod.enabled_loss({"loss_mask": {}}) is None


def test_trainer_command_uses_surface_mode_and_target100m_flags():
    mod = _load()
    manifest = mod.ROOT / "runs/local/artifacts/stage9858_validity_weighted_target_100m_contract_only_preflight/manifests/symbol_binding.jsonl"
    rows = [{"split": "train"}, {"split": "eval"}, {"split": "strict_eval"}]
    cmd = mod.trainer_command("symbol_binding", manifest, rows)
    joined = " ".join(cmd)
    assert "--mode symbol_binding_probe" in joined
    assert "--probe-scale target_100m" in joined
    assert "--structured-aux-weight 1.0" in joined
    assert "--decoder-ce-weight 0.0" in joined
    assert "--contract-only" in cmd


def test_bounded_command_uses_decoder_ce_mode():
    mod = _load()
    manifest = mod.ROOT / "runs/local/artifacts/stage9858_validity_weighted_target_100m_contract_only_preflight/manifests/bounded_argument_rendering.jsonl"
    rows = [{"split": "train"}]
    cmd = mod.trainer_command("bounded_argument_rendering", manifest, rows)
    joined = " ".join(cmd)
    assert "--mode bounded_decoder_ce_probe" in joined
    assert "--decoder-ce-weight 1.0" in joined
    assert "--structured-aux-weight 0.0" in joined
    assert "--enable-generation-audit" in cmd


def test_required_artifacts_contract_only_is_preflight_only():
    mod = _load()
    structured = mod.required_artifacts(decoder=False, contract_only=True)
    decoder = mod.required_artifacts(decoder=True, contract_only=True)
    assert structured == ["probe_contract_audit.json", "cleanup_proof.json"]
    assert decoder == ["probe_contract_audit.json", "cleanup_proof.json"]


def test_trainer_command_prefers_working_ai_python_when_present():
    mod = _load()
    manifest = mod.ROOT / "runs/local/artifacts/stage9858_validity_weighted_target_100m_contract_only_preflight/manifests/symbol_binding.jsonl"
    cmd = mod.trainer_command("symbol_binding", manifest, [{"split": "train"}])
    assert cmd[0].endswith("/miniconda3/envs/ai/bin/python") or cmd[0].endswith("python")
