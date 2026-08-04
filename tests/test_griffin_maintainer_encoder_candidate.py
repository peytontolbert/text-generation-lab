from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/audit_griffin_maintainer_encoder_candidate.py"
CONFIG = ROOT / "configs/model/agentkernel_100m_griffin_encoder_candidate.json"
CURRENT = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
ARTIFACT = ROOT / "runs/local/artifacts/griffin_maintainer_encoder_candidate_audit/summary.json"


def load_module():
    spec = importlib.util.spec_from_file_location("griffin_candidate_audit", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exact_parameter_budget_and_selected_width() -> None:
    module = load_module()
    summary = module.audit(module.read_json(CONFIG), module.read_json(CURRENT))

    assert summary["current_model"]["total"] == 102_717_225
    assert summary["current_model"]["encoder"] == 34_403_840
    assert summary["current_model"]["claim_minus_local_estimator"] == -62_863
    assert summary["alternatives"]["740"]["complete_model_parameters"] == 99_989_705
    assert summary["alternatives"]["740"]["margin_below_reference_limit"] == 10_295
    assert summary["alternatives"]["800"]["complete_model_parameters"] == 100_600_745
    assert summary["alternatives"]["960"]["complete_model_parameters"] == 102_286_505
    assert summary["selected_lru_width"] == 960
    assert summary["selected_complete_model_parameters"] == 102_286_505
    assert summary["alternatives"]["740"]["strict_sub_reference_limit"] is True
    assert summary["alternatives"]["800"]["strict_sub_reference_limit"] is False


def test_contract_encodes_true_three_x_mlp_and_hf_halving() -> None:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    architecture = payload["architecture"]

    assert architecture["effective_mlp_width"] == 3 * architecture["d_model"]
    assert architecture["hf_intermediate_size"] // 2 == architecture["effective_mlp_width"]
    assert architecture["schedule"] == ["recurrent", "recurrent", "attention"] * 2


def test_all_authority_stays_closed_and_runtime_blockers_are_explicit() -> None:
    module = load_module()
    summary = module.audit(module.read_json(CONFIG), module.read_json(CURRENT))

    assert summary["decision"].endswith("RUNTIME_INTEGRATION_BLOCKED")
    assert summary["authority"]
    assert all(value is False for value in summary["authority"].values())
    assert "installed_reset_cache_is_an_empty_stub" in summary["runtime_blockers"]
    assert "packed_segment_isolation_not_proven_for_attention_and_convolution_state" in summary["runtime_blockers"]


def test_invalid_schedule_and_open_authority_fail_closed() -> None:
    module = load_module()
    candidate = module.read_json(CONFIG)
    current = module.read_json(CURRENT)
    candidate["architecture"]["schedule"] = ["attention"] * 6
    with pytest.raises(module.GriffinCandidateAuditError, match="schedule"):
        module.audit(candidate, current)

    candidate = module.read_json(CONFIG)
    candidate["authority"]["training_admitted"] = True
    with pytest.raises(module.GriffinCandidateAuditError, match="authority"):
        module.audit(candidate, current)

    candidate = module.read_json(CONFIG)
    candidate["authority"]["training_admitted"] = 0
    with pytest.raises(module.GriffinCandidateAuditError, match="authority"):
        module.audit(candidate, current)

    candidate = module.read_json(CONFIG)
    candidate["authority"].pop("training_admitted")
    with pytest.raises(module.GriffinCandidateAuditError, match="authority schema"):
        module.audit(candidate, current)


def test_invalid_width_or_hf_mlp_encoding_fails_closed() -> None:
    module = load_module()
    current = module.read_json(CURRENT)
    candidate = module.read_json(CONFIG)
    candidate["architecture"]["lru_width"] = 745
    with pytest.raises(module.GriffinCandidateAuditError, match="audited option"):
        module.audit(candidate, current)

    candidate = module.read_json(CONFIG)
    candidate["architecture"]["hf_intermediate_size"] = 1920
    with pytest.raises(module.GriffinCandidateAuditError, match="intermediate_size"):
        module.audit(candidate, current)

    candidate = module.read_json(CONFIG)
    candidate["architecture"]["d_model"] = 645
    candidate["architecture"]["head_dim"] = 129
    with pytest.raises(module.GriffinCandidateAuditError, match="retained decoder"):
        module.audit(candidate, current)


def test_live_head_defaults_checkpoint_and_candidate_hash_are_bound() -> None:
    module = load_module()
    candidate = module.read_json(CONFIG)
    current = module.read_json(CURRENT)
    summary = module.audit(candidate, current)

    assert len(module.current_structured_dims()) == 22
    assert sum(module.current_structured_dims().values()) == 272
    assert summary["checkpoint"]["available"] is True
    assert len(summary["checkpoint"]["weight_shards"]) == 2
    assert summary["checkpoint"]["weight_shard_content_identity_bound"] is False
    assert summary["candidate_config_sha256"] == module.sha256_json(candidate)
    assert summary["current_config_sha256"] == module.sha256_json(current)
    candidate["architecture"]["attention_chunk"] = 64
    assert module.audit(candidate, current)["candidate_config_sha256"] != summary["candidate_config_sha256"]


def test_materialized_summary_matches_current_inputs() -> None:
    module = load_module()
    expected = module.audit(module.read_json(CONFIG), module.read_json(CURRENT))
    assert module.read_json(ARTIFACT) == expected


def test_parameter_function_rejects_incompatible_geometry() -> None:
    module = load_module()
    with pytest.raises(module.GriffinCandidateAuditError, match="divisible"):
        module.griffin_encoder_count(
            d_model=640, mlp_width=1920, lru_width=741, heads=5,
            head_dim=128, kv_heads=1, conv_width=4,
            recurrent_layers=4, attention_layers=2, vocab_size=1506,
        )
