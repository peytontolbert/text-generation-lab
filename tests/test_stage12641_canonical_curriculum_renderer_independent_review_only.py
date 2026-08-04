import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12641_canonical_curriculum_renderer_independent_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12641", SCRIPT)
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
    "authoritative_ledger_update_allowed",
    "authoritative_ledger_updated",
    "ledger_update_materialized",
    "stage12638_authoritative_ledger_update_materialization_only_allowed",
    "stage12639_curriculum_coverage_preflight_allowed",
    "stage12639_curriculum_coverage_preflight_performed",
    "stage12640_canonical_curriculum_renderer_preflight_allowed",
    "stage12640_canonical_curriculum_renderer_preflight_only",
    "stage12640_canonical_curriculum_renderer_preflight_performed",
    "stage12641_canonical_curriculum_renderer_independent_review_allowed",
    "stage12641_canonical_curriculum_renderer_independent_review_only",
    "stage12641_canonical_curriculum_renderer_independent_review_performed",
    "stage12642_causal_transition_atom_preflight_allowed",
    "vm_branch_remains_paused",
}
EXPECTED_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/canonical_curriculum_renderer_independent_review_only.json",
    "public_review_card.json",
    "summary.json",
]


def test_load_stage12640_pins_hashes_and_exact_artifact_manifest():
    loaded = stage.load_stage12640()
    assert loaded["summary"] == read_json(stage.S12640_SUMMARY)
    assert loaded["summary"]["rendered_candidate_rows"] == 99
    assert loaded["summary"]["decoder_ce_rows"] == 0
    assert len(loaded["rows"]) == 99


def test_validate_stage12640_independently_reviews_private_candidates():
    loaded = stage.load_stage12640()
    audit = stage.validate_stage12640(loaded)
    assert audit["candidate_count"] == 99
    assert audit["unique_candidate_ids"] == 99
    assert audit["schema_complete_rows"] == 99
    assert audit["loss_key_counts"] == {"suffix_choice_ce": 99}
    assert audit["task_family_counts"] == stage.EXPECTED_TASK_COUNTS
    assert audit["language_counts"] == stage.EXPECTED_LANGUAGE_COUNTS
    assert audit["unsafe_authority_rows"] == 0
    assert audit["truthful_anti_cheat_contract_rows"] == 99
    assert audit["answer_placeholder_rows"] == 0
    assert audit["label_correctness_proof_rows"] == 99


def test_review_passes_but_does_not_admit_or_train():
    loaded = stage.load_stage12640()
    review, card = stage.build_review(loaded)
    assert review["review_scope"] == "canonical_curriculum_renderer_independent_review_only"
    assert review["review_status"] == "independent_review_passed_candidate_rows_remain_private_no_admission"
    assert review["candidate_rows_independently_reviewed"] == 99
    assert review["schema_complete_rows_after_review"] == 99
    assert review["decoder_ce_rows_after_review"] == 0
    assert review["answer_placeholder_rows_after_review"] == 0
    assert review["label_correctness_proof_rows_after_review"] == 99
    assert review["candidate_rows_admitted_after_review"] is False
    assert review["training_allowed_after_review"] is False
    assert review["level_3_materialized_after_review"] is False
    assert card["loss_key_counts"] == {"suffix_choice_ce": 99}
    assert card["candidate_rows_admitted_after_review"] is False


def test_public_private_contract_only_sets_scoped_true_gates():
    loaded = stage.load_stage12640()
    summary, contract, private, card = stage.build_packet(loaded)
    assert summary["decision"] == "CANONICAL_CURRICULUM_RENDERER_INDEPENDENT_REVIEW_PASSED_NO_ADMISSION_OR_TRAINING"
    assert summary["candidate_rows_independently_reviewed"] == 99
    assert summary["dataset_rows_admitted"] is False
    assert summary["training_allowed"] is False
    assert summary["level_3_materialized"] is False
    assert true_fields(summary) == ALLOWED_TRUE
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
    assert summary["next_required_action"] == "stage12642_causal_transition_atom_preflight_only"


def test_generated_artifacts_match_current_independent_review():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/canonical_curriculum_renderer_independent_review_only.json")
    card = read_json(out / "public_review_card.json")
    assert summary == external
    assert summary["candidate_rows_independently_reviewed"] == 99
    assert summary["schema_complete_rows_after_review"] == 99
    assert summary["answer_placeholder_rows_after_review"] == 0
    assert summary["label_correctness_proof_rows_after_review"] == 99
    assert summary["training_allowed"] is False
    assert summary["next_required_action"] == "stage12642_causal_transition_atom_preflight_only"
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_canonical_renderer_independent_review_sha256"] == stable(private)
    assert pointer["public_review_card_sha256"] == stable(card)
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
        assert record.get("level_3_materialized") is not True
