from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12684_precise_link_semantic_repair_independent_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12684", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def test_review_recomputes_structural_and_pair_metrics() -> None:
    _summary, _audit, _contract, rows = M.load_inputs()
    review = M.review_rows(rows)
    assert review["rows_reviewed"] == 117892
    assert review["contrast_pair_groups"] == 58946
    assert review["candidate_only_valid_contrast_pairs"] == 58946
    assert review["malformed_contrast_pairs"] == 0
    assert review["semantic_duplicate_excess_rows"] == 0
    assert review["identical_input_multiple_target_groups"] == 0
    assert review["target_leak_rows"] == 0


def test_review_identifies_precise_bounded_blockers() -> None:
    summary, audit, checks = M.build_packet()
    assert summary["decision"] == "BLOCKED_PRECISE_LINK_TARGET_DERIVED_METADATA_PROVENANCE_IMPORT_AND_SHORTCUT_CONTEXT"
    assert summary["structural_review_passed"] is True
    assert summary["pair_validity_review_passed"] is True
    assert summary["scoped_claim_review_passed"] is True
    assert summary["source_provenance_review_passed"] is False
    assert summary["split_isolation_independently_auditable"] is False
    assert summary["absolute_import_resolution_review_passed"] is False
    assert summary["source_untraceable_rows"] == 117892
    assert summary["import_positive_rows_requiring_repair"] == 2057
    assert summary["split_endpoint_untraceable_rows"] == 117892
    assert summary["target_derived_metadata_review_passed"] is False
    assert summary["target_derived_occurrence_proof_rows"] == 117892
    assert summary["trainer_row_id_shortcut_review_passed"] is False
    assert summary["objective_aware_row_id_parity_accuracy"] == 1.0
    assert summary["candidate_context_shortcut_review_passed"] is False
    assert summary["candidate_context_majority_accuracy"] == 0.738405
    assert summary["symbol_context_majority_accuracy"] == 0.5
    assert audit["review"]["definition_rows_missing_declaration_shape"] == 0
    assert audit["review"]["lexical_scope_errors"] == 0
    assert {item["status"] for item in checks} == {"passed", "blocked"}


def test_mutated_pair_is_rejected() -> None:
    _summary, _audit, _contract, rows = M.load_inputs()
    pair = [dict(rows[0]), dict(rows[1])]
    changed_input = dict(pair[1]["input_state"])
    changed_input["symbol_name_style"] = "invalid_for_pair"
    pair[1] = {**pair[1], "input_state": changed_input}
    review = M.review_rows(rows[2:] + pair)
    assert review["malformed_contrast_pairs"] >= 1


def test_build_writes_digest_bound_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifact"
    summary_path = tmp_path / "summary.json"
    summary = M.build(out, summary_path)
    contract = M.read_json(out / "contract.json")
    pointer = M.read_json(out / "digest_pointer.json")
    assert summary_path.exists()
    assert contract["decision"] == summary["decision"]
    assert pointer["summary_sha256"] == M.stable_hash(summary)


def test_all_authority_gates_remain_closed() -> None:
    summary, audit, _checks = M.build_packet()
    for record in (summary, audit):
        assert all(record[field] is False for field in M.FALSE_FIELDS)
    assert summary["training_source_rows_admitted"] == 0
    assert summary["recommended_next_stage"] == "stage12685_precise_link_provenance_import_and_adapter_repair_preflight_only"


def test_review_checklist_covers_every_independent_blocker() -> None:
    _summary, _audit, checks = M.build_packet()
    blocked = {item["check_id"] for item in checks if item["status"] == "blocked"}
    assert blocked == {
        "per_row_source_provenance",
        "independent_content_split_recomputation",
        "absolute_import_package_resolution",
        "target_derived_occurrence_metadata",
        "trainer_row_id_stripping",
        "candidate_context_shortcut_repair",
        "training_authority",
    }
