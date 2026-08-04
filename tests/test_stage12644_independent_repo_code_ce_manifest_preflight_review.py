import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12644_independent_repo_code_ce_manifest_preflight_review.py"
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


ALLOWED_TRUE = {
    "repo_code_ce_candidate_manifest_materialized",
    "stage12643_repo_code_ce_manifest_preflight_performed",
    "stage12644_independent_repo_code_ce_manifest_preflight_review_performed",
    "repo_code_knowledge_substrate_recovered",
    "vm_branch_remains_paused",
}
EXPECTED_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/independent_repo_code_ce_manifest_preflight_review.json",
    "public_review_card.json",
    "summary.json",
]


def true_fields(record):
    return {key for key, value in record.items() if value is True}


def test_review_recomputes_stage12643_manifest_invariants():
    loaded = stage.load_stage12643()
    row_audit = stage.validate_stage12643(loaded)
    assert row_audit["candidate_rows"] == 200
    assert row_audit["unique_candidate_ids"] == 200
    assert row_audit["schema_complete_candidate_rows"] == 200
    assert row_audit["no_placeholder_candidate_rows"] == 200
    assert row_audit["no_raw_path_candidate_rows"] == 200
    assert row_audit["authority_blocked_candidate_rows"] == 200
    assert row_audit["source_lineage_hash_only_rows"] == 200
    assert row_audit["compact_target_text_rows"] == 200
    assert row_audit["split_counts"] == {"eval": 40, "strict_eval": 39, "train": 121}
    assert row_audit["heldout_preserved"] is True
    assert row_audit["cross_split_duplicate_opaque_repo_ids"] == 0
    assert row_audit["shortcut_audit"] == loaded["contract"]["shortcut_audit"]
    assert row_audit["shortcut_audit"]["local_manifest_shortcut_screen_passed"] is True
    assert row_audit["shortcut_audit"]["global_shortcut_preflight_passed"] is False
    assert row_audit["stage8675_blocker_rows_after_review"] == 200
    assert row_audit["admitted_candidate_rows"] == 0


def test_packet_keeps_stage8675_and_training_blockers():
    summary, contract, private, public_card = stage.build_packet(stage.load_stage12643())
    assert summary["decision"] == "REPO_CODE_CE_MANIFEST_PREFLIGHT_INDEPENDENT_REVIEW_PASSED_STAGE8675_STILL_BLOCKS_ADMISSION_NO_TRAINING"
    assert summary["candidate_rows_independently_reviewed"] == 200
    assert summary["repo_code_ce_candidate_manifest_materialized"] is True
    assert summary["repo_code_ce_manifest_materialized"] is False
    assert summary["repo_code_knowledge_stage_complete"] is False
    assert summary["training_allowed"] is False
    assert summary["dataset_rows_admitted"] is False
    assert summary["candidate_rows_admitted_after_review"] is False
    assert summary["global_shortcut_preflight_passed_after_review"] is False
    assert summary["stage8675_shortcut_issue_resolved_after_review"] is False
    assert summary["stage8675_shortcut_issue_quarantined_after_review"] is False
    assert "stage8675_symbol_binding_shortcut_issue_unresolved_or_unquarantined" in summary["downstream_blockers"]
    assert contract["claim_boundary"]["stage8675"] == "shortcut_issue_still_blocks_admission_until_repaired_or_quarantined"
    assert private["independent_review"]["review_check_count"] == 10
    assert public_card["training_allowed_after_review"] is False
    for record in (summary, contract, private):
        assert_false_boundaries(record)
    assert true_fields(summary) == ALLOWED_TRUE | {"heldout_preserved_after_review", "local_manifest_shortcut_screen_passed_after_review"}
    assert true_fields(contract) == ALLOWED_TRUE
    assert true_fields(private) == ALLOWED_TRUE


def test_build_writes_independent_review_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/independent_repo_code_ce_manifest_preflight_review.json")
    public_card = read_json(out / "public_review_card.json")
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_independent_review_packet_sha256"] == stable(private)
    assert pointer["independent_review_sha256"] == stable(private["independent_review"])
    assert pointer["public_review_card_sha256"] == stable(public_card)


def test_generated_artifacts_match_current_review():
    emitted = sorted(path.relative_to(stage.OUT).as_posix() for path in stage.OUT.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(stage.OUT / "contract.json")
    pointer = read_json(stage.OUT / "digest_pointer.json")
    private = read_json(stage.OUT / "private/independent_repo_code_ce_manifest_preflight_review.json")
    public_card = read_json(stage.OUT / "public_review_card.json")
    assert summary == external
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_independent_review_packet_sha256"] == stable(private)
    assert pointer["independent_review_sha256"] == stable(private["independent_review"])
    assert pointer["public_review_card_sha256"] == stable(public_card)
    assert summary["independent_review_sha256"] == stable(private["independent_review"])
    assert summary["public_review_card_sha256"] == stable(public_card)
    assert summary["private_independent_review_packet_sha256"] == stable(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_or_authority():
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


def test_recomputed_audit_rejects_heldout_repo_overlap_and_admission():
    rows = copy.deepcopy(stage.load_stage12643()["rows"])
    split_a = rows[0]["split"]
    other_index = next(i for i, row in enumerate(rows) if row["split"] != split_a)
    rows[other_index]["input"]["opaque_repo_id"] = rows[0]["input"]["opaque_repo_id"]
    audit = stage.audit_rows(rows)
    assert audit["heldout_preserved"] is False
    assert audit["cross_split_duplicate_opaque_repo_ids"] == 1

    rows = copy.deepcopy(stage.load_stage12643()["rows"])
    rows[0]["admission"]["admitted"] = True
    audit = stage.audit_rows(rows)
    assert audit["admitted_candidate_rows"] == 1


def test_shortcut_recomputation_detects_candidate_content_leakage():
    rows = copy.deepcopy(stage.load_stage12643()["rows"])
    rows[0]["row_id"] += "_" + rows[0]["target"]["curriculum_uses"][0]
    rows[1]["input"]["repo_path"] = "/arxiv/repositories/leaky"
    audit = stage.recompute_shortcut_audit(rows)
    assert audit["target_label_in_id_rows"] == 1
    assert audit["repo_path_in_model_input_rows"] == 1
    assert audit["raw_source_included_rows"] == 1
    assert audit["local_manifest_shortcut_screen_passed"] is False


def test_validate_rejects_public_private_hash_inconsistency_and_gate_drift():
    loaded = stage.load_stage12643()
    broken = copy.deepcopy(loaded)
    broken["summary"]["training_allowed"] = True
    try:
        stage.validate_stage12643(broken)
    except stage.Stage12644ReviewError as exc:
        assert "summary_gate_drift:training_allowed" in str(exc)
    else:
        raise AssertionError("expected training gate drift rejection")

    broken = copy.deepcopy(loaded)
    broken["pointer"]["candidate_manifest_sha256"] = "0" * 64
    try:
        stage.validate_stage12643(broken)
    except stage.Stage12644ReviewError as exc:
        assert "pointer_candidate_hash_mismatch" in str(exc)
    else:
        raise AssertionError("expected pointer hash mismatch rejection")
