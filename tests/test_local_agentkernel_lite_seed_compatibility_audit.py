from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8905_local_agentkernel_lite_seed_compatibility_audit import (
    AUTHORITY_CLOSED,
    build_audit,
    validate_audit,
)


def test_local_export_is_dimensionally_relevant_but_not_direct_seed() -> None:
    audit = build_audit()
    checks = audit["checks"]
    assert checks["local_export_present"] is True
    assert checks["same_d_model"] is True
    assert checks["same_d_ff"] is True
    assert checks["same_layer_count"] is True
    assert checks["same_attention_heads"] is True
    assert checks["same_rope_theta"] is True
    assert checks["safe_to_directly_initialize_training"] is False


def test_audit_records_direct_seed_blockers() -> None:
    audit = build_audit()
    blockers = set(audit["blockers"])
    assert "tokenizer_vocab_mismatch_requires_explicit_vocab_resize_or_matching_tokenizer" in blockers
    assert "browser_bitnet_runtime_export_not_direct_pytorch_training_checkpoint" in blockers
    assert "no_verified_pytorch_state_dict_for_trainer_loading" in blockers


def test_validation_keeps_authority_closed() -> None:
    registry = {"metrics": {"latest_stage": 8904, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    assert validate_audit(build_audit(), registry) == []
    registry["metrics"]["authority_counts"]["model_execution_authorized_next"] = 1
    assert "registry_authority_counts_nonzero" in validate_audit(build_audit(), registry)


def test_direct_seed_cannot_be_accidentally_allowed() -> None:
    audit = build_audit()
    audit["checks"]["safe_to_directly_initialize_training"] = True
    registry = {"metrics": {"latest_stage": 8904, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    assert "direct_training_seed_was_incorrectly_allowed" in validate_audit(audit, registry)
