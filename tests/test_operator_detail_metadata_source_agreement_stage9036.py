from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9036_operator_detail_metadata_source_agreement import (  # noqa: E402
    APPROVED_METADATA_SOURCE_CLASSES,
    AUTHORITY_CLOSED,
    FORBIDDEN_SOURCE_CLASSES,
    build_agreement,
    validate_agreement,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9036_approves_only_metadata_source_classes() -> None:
    card = build_agreement(registry())
    assert card["metrics"]["approved_metadata_source_classes"] == len(APPROVED_METADATA_SOURCE_CLASSES)
    assert card["metrics"]["approved_metadata_source_classes"] >= 4
    names = {row["source_class"] for row in card["approved_metadata_source_classes"]}
    assert "recovered_stage_summaries" in names
    assert "recovered_artifact_summaries" in names
    assert "human_authored_metadata_patch" in names
    assert "existing_docs_metadata_only" in names
    assert all("raw" not in name for name in names)


def test_stage9036_forbids_raw_payload_source_classes() -> None:
    card = build_agreement(registry())
    for forbidden in [
        "raw_codex_session_text",
        "raw_repository_source_body",
        "raw_row_body_text",
        "hidden_or_locked_eval_payload",
        "model_generated_operator_detail_without_audit",
    ]:
        assert forbidden in FORBIDDEN_SOURCE_CLASSES
        assert forbidden in card["forbidden_source_classes"]
    assert validate_agreement(card) == []


def test_stage9036_requires_future_proofs_before_recovery() -> None:
    card = build_agreement(registry())
    assert "source_class_recorded_per_detail_field" in card["future_required_proofs"]
    assert "source_path_or_stage_ref_recorded_per_detail_field" in card["future_required_proofs"]
    assert "raw_payload_absence_scan_passed" in card["future_required_proofs"]
    assert "detail_hash_present_for_recovered_rows" in card["future_required_proofs"]
    assert "training_ready_status_stays_false_until_full_audit" in card["future_required_proofs"]


def test_stage9036_does_not_instantiate_ticket_or_open_training() -> None:
    card = build_agreement(registry())
    assert card["metrics"]["metadata_source_agreement_only"] is True
    assert card["metrics"]["operator_detail_ticket_instantiated_now"] is False
    assert card["metrics"]["operator_details_recovered_now"] is False
    assert card["metrics"]["raw_session_text_read_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["data_mining_authorized"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert card["metrics"]["denoise_ce_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9036_validation_rejects_open_authority_or_ticket_instantiation() -> None:
    opened = build_agreement(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_agreement(opened)
    unsafe = build_agreement(registry())
    unsafe["metrics"]["operator_detail_ticket_instantiated_now"] = True
    assert "operator_detail_ticket_instantiated_now" in validate_agreement(unsafe)
