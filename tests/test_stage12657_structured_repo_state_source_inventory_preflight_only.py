from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12657_structured_repo_state_source_inventory_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12657", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def assert_false_boundaries(record):
    for field in stage.FALSE_FIELDS:
        assert record[field] is False


def test_load_stage12656_pins_completed_repo_code_boundary() -> None:
    summary = stage.load_stage12656()
    assert summary["repo_code_curriculum_layer_complete"] is True
    assert summary["shortcut_resilience_overlay_materialized"] is True
    assert summary["training_allowed"] is False


def test_source_audit_classifies_stage10516_as_candidate_requiring_sanitization() -> None:
    audits = {audit["source_id"]: audit for audit in (stage.source_audit(meta) for meta in stage.CANDIDATE_SOURCES)}
    roots = audits["stage10516_root_state_compiler_roots"]
    targets = audits["stage10516_root_state_compiler_multitarget_rows"]
    states = audits["stage10516_root_state_compiler_causal_states"]
    assert roots["row_count"] == 784
    assert targets["row_count"] == 2407
    assert states["row_count"] == 784
    assert roots["readiness"] == "candidate_requires_schema_review"
    assert targets["readiness"] == "candidate_requires_sanitization"
    assert states["readiness"] == "candidate_requires_sanitization"
    assert targets["state_packet_field_rows"] == 2407
    assert states["state_packet_field_rows"] == 784
    assert targets["state_label_field_rows"] == 2407
    assert states["state_label_field_rows"] == 784


def test_later_layer_sources_are_not_promoted_as_structured_repo_state() -> None:
    audits = {audit["source_id"]: audit for audit in (stage.source_audit(meta) for meta in stage.CANDIDATE_SOURCES)}
    structured = audits["stage9916_hardened_weighted_structured_state"]
    level3 = audits["stage12213_strict_fail_current_state_records"]
    assert structured["row_count"] == 396
    assert structured["readiness"] == "candidate_requires_sanitization"
    assert structured["layer_role"] == "mixed_later_layer_reference_only"
    assert structured["lane_counts"]["edit_localization"] == 64
    assert structured["lane_counts"]["patch_operator_selection"] == 144
    assert level3["row_count"] == 2
    assert level3["readiness"] == "candidate_requires_sanitization"
    assert level3["layer_role"] == "later_transition_reference_only"


def test_packet_blocks_admission_and_names_next_sanitized_manifest_stage() -> None:
    summary, matrix, audits = stage.build_packet()
    assert summary["decision"] == "STRUCTURED_REPO_STATE_SOURCE_INVENTORY_RECORDED_NO_ROW_ADMISSION"
    assert summary["structured_repo_state_source_inventory_materialized"] is True
    assert summary["candidate_source_count"] == 6
    assert summary["total_inventory_rows"] == 4398
    assert summary["candidate_rows_before_sanitization"] == 4398
    assert summary["structured_repo_state_layer_admission_ready"] is False
    assert summary["next_required_action"] == "stage12658_structured_repo_state_sanitized_candidate_manifest_preflight_only"
    assert matrix["blockers"] == list(stage.BLOCKERS)
    assert len(audits) == 6
    assert_false_boundaries(summary)
    assert_false_boundaries(matrix)


def test_public_records_do_not_expose_private_paths_or_row_text() -> None:
    summary, matrix, _ = stage.build_packet()
    for label, record in (("summary", summary), ("matrix", matrix)):
        stage.assert_public_sanitized(record, label)
        encoded = json.dumps(record, sort_keys=True)
        for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
            assert needle not in encoded


def test_build_writes_inventory_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/candidate_source_audit.jsonl",
        "private/structured_repo_state_source_inventory_packet.json",
        "source_inventory_matrix.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/structured_repo_state_source_inventory_packet.json")
    matrix = read_json(out / "source_inventory_matrix.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["source_inventory_matrix_sha256"] == stable(matrix)
    assert sum(1 for _ in (out / "private/candidate_source_audit.jsonl").open()) == 6


def test_generated_artifacts_match_current_inventory() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    matrix = read_json(stage.OUT / "source_inventory_matrix.json")
    pointer = read_json(stage.OUT / "digest_pointer.json")
    assert summary == external
    assert summary["training_allowed"] is False
    assert matrix["structured_repo_state_layer_admission_ready"] is False
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["source_inventory_matrix_sha256"] == stable(matrix)
    assert_false_boundaries(summary)
    assert_false_boundaries(matrix)
