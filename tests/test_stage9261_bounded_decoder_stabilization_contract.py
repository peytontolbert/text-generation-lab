from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9261_bounded_decoder_stabilization_contract.py"
    spec = importlib.util.spec_from_file_location("stage9261", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stabilization_contract_requires_eos_repetition_and_gradient_patches():
    mod = _load()
    source = {"passed": True, "metrics": {"execution_safety_passed": True, "decoder_quality_passed": False}}
    contract = mod.build_contract(source)
    audit = mod.audit_contract(contract, source)
    assert audit["passed"] is True
    patch_ids = {patch["patch_id"] for patch in contract["required_trainer_patches"]}
    assert "eos_weighted_token_loss" in patch_ids
    assert "post_clip_gradient_telemetry" in patch_ids
    assert "repetition_negative_replay" in patch_ids
    assert contract["next_probe_limits"]["learning_rate"] == 1e-5
    assert all(value is False for value in contract["authority"].values())


def test_contract_rejects_quality_success_or_open_authority():
    mod = _load()
    source = {"passed": True, "metrics": {"execution_safety_passed": True, "decoder_quality_passed": True}}
    contract = mod.build_contract(source)
    contract["authority"]["model_execution_authorized_next"] = True
    audit = mod.audit_contract(contract, source)
    assert audit["passed"] is False
    assert "source_decoder_quality_not_recorded_as_failure" in audit["failures"]
    assert "authority_open" in audit["failures"]


def test_contract_rejects_weak_generation_gates():
    mod = _load()
    source = {"passed": True, "metrics": {"execution_safety_passed": True, "decoder_quality_passed": False}}
    contract = mod.build_contract(source)
    contract["quality_gates_for_next_probe"]["unterminated_generation_rate_max"] = 0.9
    contract["quality_gates_for_next_probe"]["degenerate_repetition_rate_max"] = 0.5
    audit = mod.audit_contract(contract, source)
    assert audit["passed"] is False
    assert "unterminated_gate_too_weak" in audit["failures"]
    assert "repetition_gate_too_weak" in audit["failures"]
