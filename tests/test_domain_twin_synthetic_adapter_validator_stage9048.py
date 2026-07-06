from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage9048_domain_twin_synthetic_adapter_validator import build_card, validate_card  # noqa: E402
from scripts.domain_twin_adapter_validator import adapt_source_records, validate_source_record  # noqa: E402


def test_domain_twin_adapter_emits_compiler_shaped_closed_rows() -> None:
    card = build_card({"metrics": {"authority_counts": {}}})
    assert validate_card(card) == []
    adapter = card["adapter_card"]
    assert adapter["all_loss_masks_closed"] is True
    assert adapter["all_authority_closed"] is True
    assert adapter["all_gate_status_complete"] is True
    assert adapter["compiler_ready_for_training"] is False
    assert card["metrics"]["training_authorized"] is False


def test_domain_twin_adapter_blocks_forbidden_payload_fields() -> None:
    bad = {
        "manifest_family": "repo_twin_manifest",
        "repo_twin_id": "repo_bad",
        "raw_source_body": "def secret(): pass",
        "authority": {"model_execution_authorized_next": False},
        "provenance": {},
        "anti_cheat": {"id_is_opaque": True, "label_coded_id_absent": True, "raw_body_absent": False},
    }
    failures = validate_source_record(bad)
    assert "forbidden_payload_field:raw_source_body" in failures
    assert "anti_cheat_failed:raw_body_absent" in failures
    rows, card = adapt_source_records([bad])
    assert rows[0]["route"] == "NEEDS_HUMAN_REVIEW"
    assert card["compiler_ready_for_training"] is False
