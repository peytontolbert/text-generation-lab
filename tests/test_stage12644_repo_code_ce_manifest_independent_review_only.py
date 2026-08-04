import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12644_repo_code_ce_manifest_independent_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12644", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def assert_false_boundaries(record):
    for field in stage.FALSE_FIELDS:
        assert field in record
        assert record[field] is False


def true_fields(record):
    return {key for key, value in record.items() if value is True}


ALLOWED_TRUE = {
    "stage12644_repo_code_ce_manifest_independent_review_only",
    "stage12644_repo_code_ce_manifest_independent_review_performed",
    "repo_code_ce_candidate_manifest_reviewed",
    "repo_code_knowledge_substrate_recovered",
    "independent_review_passed",
}
EXPECTED_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/repo_code_ce_manifest_independent_review_only.json",
    "public_review_card.json",
    "summary.json",
]


def test_load_stage12643_pins_hashes_and_exact_artifact_manifest():
    loaded = stage.load_stage12643()
    assert loaded["summary"] == read_json(stage.S12643_SUMMARY)
    assert loaded["summary"]["candidate_rows"] == 200
    assert len(loaded["rows"]) == 200
    assert loaded["contract"]["shortcut_audit"]["global_shortcut_preflight_passed"] is False


def test_validate_stage12643_independently_reviews_private_candidates():
    loaded = stage.load_stage12643()
    audit = stage.validate_stage12643(loaded)
    assert audit["candidate_rows"] == 200
    assert audit["unique_candidate_ids"] == 200
    assert audit["schema_complete_rows"] == 200
    assert audit["placeholder_rows"] == 0
    assert audit["raw_path_rows"] == 0
    assert audit["authority_blocked_rows"] == 200
    assert audit["split_counts"] == {"eval": 40, "strict_eval": 39, "train": 121}
    assert audit["cross_split_duplicate_opaque_repo_ids"] == 0
    assert audit["shortcut_audit"]["local_manifest_shortcut_screen_passed"] is True
    assert audit["shortcut_audit"]["global_shortcut_preflight_passed"] is False
    assert audit["stale_shortcut_field_rows"] == 0
    assert audit["compact_text_rows"] == 200
    assert audit["source_lineage_hash_rows"] == 200


def test_review_passes_but_keeps_stage8675_and_training_blocked():
    loaded = stage.load_stage12643()
    review, card = stage.build_review(loaded)
    assert review["review_scope"] == "repo_code_ce_manifest_independent_review_only"
    assert review["review_status"] == "independent_review_passed_candidate_manifest_remains_private_no_admission"
    assert review["candidate_rows_independently_reviewed"] == 200
    assert review["schema_complete_rows_after_review"] == 200
    assert review["placeholder_rows_after_review"] == 0
    assert review["raw_path_rows_after_review"] == 0
    assert review["cross_split_duplicate_opaque_repo_ids_after_review"] == 0
    assert review["shortcut_audit_after_review"]["local_manifest_shortcut_screen_passed"] is True
    assert review["shortcut_audit_after_review"]["global_shortcut_preflight_passed"] is False
    assert review["stage8675_shortcut_issue_resolved_after_review"] is False
    assert review["stage8675_shortcut_issue_quarantined_after_review"] is False
    assert review["candidate_rows_admitted_after_review"] is False
    assert review["training_allowed_after_review"] is False
    assert card["candidate_rows_admitted_after_review"] is False
    assert card["training_allowed_after_review"] is False


def test_public_private_contract_only_sets_scoped_true_gates():
    loaded = stage.load_stage12643()
    summary, contract, private, card = stage.build_packet(loaded)
    assert summary["decision"] == "REPO_CODE_CE_MANIFEST_INDEPENDENT_REVIEW_PASSED_NO_ADMISSION_OR_TRAINING"
    assert summary["candidate_rows_independently_reviewed"] == 200
    assert summary["schema_complete_rows_after_review"] == 200
    assert summary["training_allowed"] is False
    assert summary["dataset_rows_admitted"] is False
    assert summary["repo_code_ce_manifest_materialized"] is False
    assert summary["repo_code_knowledge_stage_complete"] is False
    assert summary["stage8675_shortcut_issue_resolved_after_review"] is False
    assert summary["stage8675_shortcut_issue_quarantined_after_review"] is False
    assert true_fields(summary) == ALLOWED_TRUE | {"local_manifest_shortcut_screen_passed_after_review"}
    assert true_fields(contract) == ALLOWED_TRUE
    assert true_fields(private) == ALLOWED_TRUE
    assert true_fields(card) == set()
    for record in (summary, contract, private):
        assert_false_boundaries(record)
    assert contract["public_review_card_sha256"] == stable(card)


def test_build_writes_independent_review_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    assert summary["next_required_action"] == "stage12645_stage8675_symbol_binding_shortcut_quarantine_or_reselect"


def test_generated_artifacts_match_current_independent_review():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/repo_code_ce_manifest_independent_review_only.json")
    card = read_json(out / "public_review_card.json")
    assert summary == external
    assert summary["candidate_rows_independently_reviewed"] == 200
    assert summary["schema_complete_rows_after_review"] == 200
    assert summary["placeholder_rows_after_review"] == 0
    assert summary["raw_path_rows_after_review"] == 0
    assert summary["training_allowed"] is False
    assert summary["dataset_rows_admitted"] is False
    assert summary["global_shortcut_preflight_passed_after_review"] is False
    assert summary["next_required_action"] == "stage12645_stage8675_symbol_binding_shortcut_quarantine_or_reselect"
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_review_packet_sha256"] == stable(private)
    assert pointer["public_review_card_sha256"] == stable(card)
    assert pointer["review_sha256"] == stable(private["review"])
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_no_training_authority():
    public_paths = [
        stage.OUT / "summary.json",
        stage.SUMMARY,
        stage.OUT / "contract.json",
        stage.OUT / "digest_pointer.json",
        stage.OUT / "public_review_card.json",
    ]
    for path in public_paths:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert record.get("training_allowed") is not True
        assert record.get("dataset_rows_admitted") is not True
        assert record.get("repo_code_ce_manifest_materialized") is not True


def test_independent_review_rejects_shortcut_and_heldout_regressions():
    loaded = stage.load_stage12643()
    shortcut_regression = copy.deepcopy(loaded)
    shortcut_regression["rows"][0]["row_id"] += "_" + shortcut_regression["rows"][0]["target"]["curriculum_uses"][0]
    try:
        stage.validate_stage12643(shortcut_regression)
    except stage.RepoCodeCeManifestIndependentReviewError as exc:
        assert "shortcut_audit_mismatch" in str(exc)
    else:
        raise AssertionError("expected shortcut audit mismatch")

    overlap_regression = copy.deepcopy(loaded)
    split_a = overlap_regression["rows"][0]["split"]
    other_index = next(i for i, row in enumerate(overlap_regression["rows"]) if row["split"] != split_a)
    overlap_regression["rows"][other_index]["input"]["opaque_repo_id"] = overlap_regression["rows"][0]["input"]["opaque_repo_id"]
    try:
        stage.validate_stage12643(overlap_regression)
    except stage.RepoCodeCeManifestIndependentReviewError as exc:
        assert "candidate_cross_split_overlap" in str(exc)
    else:
        raise AssertionError("expected heldout overlap rejection")
