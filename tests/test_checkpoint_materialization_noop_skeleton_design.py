from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8920_checkpoint_materialization_noop_skeleton_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_skeleton,
    validate_skeleton,
)


def test_skeleton_records_required_preconditions_and_steps() -> None:
    skeleton = build_skeleton()
    assert skeleton["checks"]["preconditions_recorded"] is True
    assert skeleton["checks"]["noop_steps_recorded"] is True
    assert "tokenizer_hash_lock" in skeleton["materialization_preconditions"]
    assert "bitnet_layout_decoder_contract" in skeleton["materialization_preconditions"]


def test_skeleton_blocks_all_materialization_actions() -> None:
    skeleton = build_skeleton()
    checks = skeleton["checks"]
    assert checks["no_checkpoint_write_authorized"] is True
    assert checks["no_state_dict_load_authorized"] is True
    assert checks["no_tensor_value_read_authorized"] is True
    assert checks["no_packed_decode_authorized"] is True
    assert checks["no_embedding_resize_authorized"] is True
    assert checks["no_control_head_init_authorized"] is True
    assert checks["no_model_forward_authorized"] is True
    assert checks["no_training_authorized"] is True
    assert all(value is False for value in skeleton["authority"].values())


def test_noop_steps_keep_dangerous_work_blocked() -> None:
    skeleton = build_skeleton()
    step_status = {step["step"]: step["status"] for step in skeleton["noop_steps"]}
    assert step_status["read_contract_metadata"] == "allowed_metadata_only"
    assert step_status["load_source_weights"] == "blocked"
    assert step_status["decode_packed_bitnet"] == "blocked"
    assert step_status["write_checkpoint"] == "blocked"


def test_validation_rejects_authority_or_materialization_drift() -> None:
    registry = {"metrics": {"latest_stage": 8919, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    assert validate_skeleton(build_skeleton(), registry) == []
    skeleton = build_skeleton()
    skeleton["checks"]["no_checkpoint_write_authorized"] = False
    assert "no_checkpoint_write_authorized" in validate_skeleton(skeleton, registry)
    registry["metrics"]["authority_counts"]["model_execution_authorized_next"] = 1
    assert "registry_authority_counts_nonzero" in validate_skeleton(build_skeleton(), registry)
