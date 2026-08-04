import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12646_independent_stage12645_shortcut_quarantine_reselect_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12646", SCRIPT)
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


EXPECTED_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/independent_stage12645_shortcut_quarantine_review_only.json",
    "public_review_card.json",
    "summary.json",
]


def test_load_stage12645_pins_hashes_and_artifact_manifest():
    loaded = stage.load_stage12645()
    assert loaded["summary"] == read_json(stage.S12645_SUMMARY)
    assert len(loaded["original"]) == 125
    assert len(loaded["repaired"]) == 80
    assert len(loaded["quarantine"]) == 45
    assert loaded["summary"]["next_required_action"] == stage.STAGE
    assert stage.sha256_bytes(stage.S12645_SCRIPT.read_bytes()) == stage.EXPECTED_HASHES["stage12645_script_bytes"]
    assert stage.sha256_bytes(stage.S12645_TESTS.read_bytes()) == stage.EXPECTED_HASHES["stage12645_tests_bytes"]


def test_validate_stage12645_recomputes_partition_and_shortcut_rule():
    loaded = stage.load_stage12645()
    audit = stage.validate_stage12645(loaded)
    assert audit["original_rows_reviewed"] == 125
    assert audit["repaired_rows_reviewed"] == 80
    assert audit["quarantined_rows_reviewed"] == 45
    assert audit["repaired_action_counts"] == stage.EXPECTED_ACTION_COUNTS
    assert audit["repaired_split_counts"] == {"eval": 24, "strict_eval": 24, "train": 32}
    assert audit["original_shortcut_feature_cells"] == 1
    assert audit["repaired_shortcut_feature_cells"] == 0
    assert audit["partition_complete"] is True
    assert audit["repaired_rows_are_stage8674_subset"] is True
    assert audit["quarantine_rows_are_stage8674_subset"] is True
    assert audit["repaired_and_quarantine_disjoint"] is True


def test_review_passes_but_does_not_admit_or_train():
    review, card = stage.build_review(stage.load_stage12645())
    assert review["review_status"] == "independent_review_passed_successor_shortcut_quarantine_reselect_no_admission"
    assert review["repaired_rows_reviewed"] == 80
    assert review["quarantined_rows_reviewed"] == 45
    assert review["repaired_shortcut_feature_cells"] == 0
    assert review["candidate_rows_admitted_after_review"] is False
    assert review["training_allowed_after_review"] is False
    assert review["required_next_gate"] == "stage12647_repo_code_knowledge_completion_admission_preflight_only"
    assert card["training_allowed_after_review"] is False


def test_public_private_contract_only_sets_scoped_true_gates():
    summary, contract, private, card = stage.build_packet(stage.load_stage12645())
    assert summary["decision"] == "STAGE12645_SHORTCUT_QUARANTINE_RESELECT_INDEPENDENT_REVIEW_PASSED_NO_ADMISSION_OR_TRAINING"
    assert summary["repaired_rows_reviewed"] == 80
    assert summary["quarantined_rows_reviewed"] == 45
    assert summary["training_allowed"] is False
    assert summary["dataset_rows_admitted"] is False
    assert summary["global_shortcut_preflight_passed"] is False
    assert summary["stage8675_successor_manifest_stage8675_rule_passed_after_review"] is True
    assert summary["partition_complete"] is True
    assert summary["repaired_rows_are_stage8674_subset"] is True
    assert summary["quarantine_rows_are_stage8674_subset"] is True
    assert summary["repaired_and_quarantine_disjoint"] is True
    assert contract["private_review_packet_sha256"] == stable(private)
    assert contract["public_review_card_sha256"] == stable(card)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_independent_review_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    assert summary["next_required_action"] == "stage12647_repo_code_knowledge_completion_admission_preflight_only"


def test_generated_artifacts_match_current_independent_review():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/independent_stage12645_shortcut_quarantine_review_only.json")
    card = read_json(out / "public_review_card.json")
    assert summary == external
    assert summary["training_allowed"] is False
    assert summary["dataset_rows_admitted"] is False
    assert summary["repaired_shortcut_feature_cells"] == 0
    assert summary["next_required_action"] == "stage12647_repo_code_knowledge_completion_admission_preflight_only"
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_review_packet_sha256"] == stable(private)
    assert pointer["public_review_card_sha256"] == stable(card)
    assert pointer["review_sha256"] == stable(private["review"])
    assert summary["partition_complete"] is True
    assert summary["repaired_rows_are_stage8674_subset"] is True
    assert summary["quarantine_rows_are_stage8674_subset"] is True
    assert summary["repaired_and_quarantine_disjoint"] is True
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_or_training_authority():
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
        assert record.get("global_shortcut_preflight_passed") is not True


def test_review_rejects_partition_and_shortcut_regressions():
    loaded = stage.load_stage12645()
    overlap = copy.deepcopy(loaded)
    overlap["quarantine"][0]["row_sha256"] = stage.stable_hash(overlap["repaired"][0])
    try:
        stage.validate_stage12645(overlap)
    except stage.Stage12646ReviewError as exc:
        assert "row_hash_uniqueness_drift" in str(exc) or "repaired_quarantine_overlap" in str(exc)
    else:
        raise AssertionError("expected overlap rejection")

    shortcut = copy.deepcopy(loaded)
    extra = next(row for row in shortcut["original"] if row["clean_state"]["binding_action"] == "BIND_TEST_TO_SYMBOL" and stage.stable_hash(row) not in {stage.stable_hash(r) for r in shortcut["repaired"]})
    shortcut["repaired"].append(extra)
    try:
        stage.validate_stage12645(shortcut)
    except stage.Stage12646ReviewError as exc:
        assert "row_count_drift" in str(exc) or "repaired_audit_recompute_failed" in str(exc)
    else:
        raise AssertionError("expected shortcut/count rejection")
