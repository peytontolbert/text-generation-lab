from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8909_state_dict_shape_migration_design import (
    AUTHORITY_CLOSED,
    build_design,
    validate_design,
)


def test_export_inventory_is_present_but_direct_load_is_blocked() -> None:
    design = build_design()
    checks = design["checks"]
    assert checks["export_inventory_present"] is True
    assert checks["has_quant_runtime_modules"] is True
    assert checks["has_dense_runtime_files"] is True
    assert checks["has_pytorch_state_dict"] is False
    assert checks["direct_state_dict_load_safe"] is False


def test_migration_requirements_are_explicit() -> None:
    design = build_design()
    assert design["checks"]["requires_conversion_map"] is True
    assert design["checks"]["requires_tokenizer_migration"] is True
    assert design["checks"]["requires_new_head_policy"] is True
    blockers = set(design["blockers"])
    assert "browser_bitnet_export_has_packed_runtime_files_not_verified_pytorch_state_dict" in blockers
    assert "embedding_shapes_differ_due_to_vocab_8207_vs_target_1506" in blockers
    assert "current_recovered_control_heads_missing_from_export" in blockers


def test_expected_key_families_include_recovered_control_heads() -> None:
    design = build_design()
    extra_heads = design["expected_recovered_key_families"]["extra_heads"]
    assert "retrieval_query_head.weight" in extra_heads
    assert "structured_heads.*.weight/bias" in extra_heads
    assert "agent_policy_heads.*.weight/bias" in extra_heads


def test_validation_rejects_accidental_direct_load_allow() -> None:
    registry = {"metrics": {"latest_stage": 8908, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    assert validate_design(build_design(), registry) == []
    design = build_design()
    design["checks"]["direct_state_dict_load_safe"] = True
    assert "direct_state_dict_load_was_incorrectly_allowed" in validate_design(design, registry)
