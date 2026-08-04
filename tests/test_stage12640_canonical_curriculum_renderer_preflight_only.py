import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12640_canonical_curriculum_renderer_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12640", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)

def read_json(path: Path):
    return json.loads(path.read_text())

def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]

def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()

def assert_false_boundaries(record):
    for field in stage.FALSE_FIELDS:
        assert field in record
        assert record[field] is False

def true_fields(record):
    return {key for key, value in record.items() if value is True}

ALLOWED_TRUE = {
    "authoritative_ledger_update_allowed", "authoritative_ledger_updated", "ledger_update_materialized",
    "stage12638_authoritative_ledger_update_materialization_only_allowed",
    "stage12639_curriculum_coverage_preflight_allowed", "stage12639_curriculum_coverage_preflight_performed",
    "stage12640_canonical_curriculum_renderer_preflight_allowed", "stage12640_canonical_curriculum_renderer_preflight_only",
    "stage12640_canonical_curriculum_renderer_preflight_performed",
    "stage12641_canonical_curriculum_renderer_independent_review_allowed", "vm_branch_remains_paused",
}
EXPECTED_ARTIFACTS = [
    "canonical_renderer_card.json",
    "contract.json",
    "digest_pointer.json",
    "private/canonical_candidate_curriculum_rows_preflight.jsonl",
    "private/canonical_curriculum_renderer_preflight_only.json",
    "summary.json",
]

def test_load_stage12639_pins_preflight_and_source_rows():
    loaded = stage.load_stage12639()
    assert loaded["summary"]["canonical_trainer_ready_rows"] == 0
    assert loaded["summary"]["stage12640_canonical_curriculum_renderer_preflight_allowed"] is True
    assert loaded["summary"]["training_allowed"] is False
    assert len(loaded["rows"]) == 99

def test_render_rows_make_schema_complete_suffix_choice_candidates():
    loaded = stage.load_stage12639()
    rendered, card = stage.render_rows(loaded["rows"], stage.load_schema())
    assert len(rendered) == 99
    assert card["rendered_row_count"] == 99
    assert card["schema_complete_rows"] == 99
    assert card["schema_blocked_rows"] == 0
    assert card["loss_key_counts"] == {"suffix_choice_ce": 99}
    assert card["split_counts"] == {"train": 99}
    assert card["unsupported_loss_rows"] == 0
    assert card["unsafe_authority_rows"] == 0
    assert card["answer_placeholder_rows"] == 0
    assert card["label_correctness_unproved_rows"] == 0
    assert sum(card["label_correctness_proof_counts"].values()) == 99
    for row in rendered:
        assert set(stage.CANONICAL_REQUIRED_FIELDS) <= set(row)
        assert row["split"] == "train"
        assert row["loss_mask"] == {"suffix_choice_ce": True}
        assert all(value is False for value in row["authority"].values())
        assert row["training_allowed"] is False
        assert row["dataset_rows_admitted"] is False
        assert row["candidate_only_no_admission"] is True
        assert row["target"]["decoder_text"] == row["target"]["suffix_choice"]
        assert row["target"]["suffix_choice"] in [option["label"] for option in row["input_state"]["opaque_options"]]
        assert "Answer:" not in row["input_state"]["rendered_input_text"]
        assert row["target"]["label_correctness_proof"]["answer_placeholder_removed"] is True
        assert row["target"]["label_correctness_proof"]["proof_mode"] in {
            "chosen_option_has_unique_evidence_ids",
            "chosen_option_value_is_unique_selected_test_backed",
            "target_semantic_matches_chosen_option",
        }
        assert row["anti_cheat_contract"]["option_labels_may_appear_in_input_state"] is True
        assert row["anti_cheat_contract"]["answer_label_not_marked_as_correct_in_input_state"] is True
        assert "target_label_not_visible_in_input_state" not in row["anti_cheat_contract"]

def test_preflight_keeps_rendered_rows_private_and_not_admitted():
    loaded = stage.load_stage12639()
    rendered, card = stage.render_rows(loaded["rows"], stage.load_schema())
    data = b"".join(json.dumps(row, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n" for row in rendered)
    preflight = stage.build_preflight(card, hashlib.sha256(data).hexdigest())
    assert preflight["preflight_scope"] == "canonical_curriculum_renderer_preflight_only"
    assert preflight["rendered_candidate_rows"] == 99
    assert preflight["schema_complete_rows"] == 99
    assert preflight["answer_placeholder_rows"] == 0
    assert preflight["label_correctness_unproved_rows"] == 0
    assert sum(preflight["label_correctness_proof_counts"].values()) == 99
    assert preflight["dataset_rows_admitted_after_preflight"] is False
    assert preflight["training_rows_admitted_after_preflight"] is False
    assert preflight["recommended_next_stage"] == "stage12641_canonical_curriculum_renderer_independent_review_only"

def test_public_private_contract_only_sets_scoped_true_gates():
    loaded = stage.load_stage12639()
    rendered, card = stage.render_rows(loaded["rows"], stage.load_schema())
    data = b"".join(json.dumps(row, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n" for row in rendered)
    summary, contract, private = stage.build_packet(loaded, rendered, card, hashlib.sha256(data).hexdigest())
    assert summary["decision"] == "CANONICAL_CURRICULUM_ROWS_RENDERED_NO_ADMISSION_OR_TRAINING"
    assert summary["rendered_candidate_rows"] == 99
    assert summary["schema_complete_rows"] == 99
    assert summary["training_allowed"] is False
    assert summary["dataset_rows_admitted"] is False
    assert summary["level_3_materialized"] is False
    assert true_fields(summary) == ALLOWED_TRUE
    assert true_fields(contract) == ALLOWED_TRUE
    assert true_fields(private) == ALLOWED_TRUE
    for record in (summary, contract, private):
        assert_false_boundaries(record)
    assert contract["canonical_renderer_card_sha256"] == stable(card)

def test_build_writes_renderer_preflight_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    assert len(read_jsonl(out / "private/canonical_candidate_curriculum_rows_preflight.jsonl")) == 99

def test_generated_artifacts_match_current_renderer_preflight():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/canonical_curriculum_renderer_preflight_only.json")
    card = read_json(out / "canonical_renderer_card.json")
    rows = read_jsonl(out / "private/canonical_candidate_curriculum_rows_preflight.jsonl")
    assert summary == external
    assert summary["rendered_candidate_rows"] == 99
    assert summary["schema_complete_rows"] == 99
    assert summary["answer_placeholder_rows_after_renderer"] == 0
    assert summary["label_correctness_unproved_rows"] == 0
    assert sum(summary["label_correctness_proof_counts"].values()) == 99
    assert summary["next_required_action"] == "stage12641_canonical_curriculum_renderer_independent_review_only"
    assert summary["training_allowed"] is False
    assert len(rows) == 99
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_canonical_curriculum_renderer_preflight_sha256"] == stable(private)
    assert pointer["canonical_renderer_card_sha256"] == stable(card)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)

def test_public_artifacts_have_no_private_leaks_and_no_training_authority():
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json", stage.OUT / "canonical_renderer_card.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert record.get("training_allowed") is not True
        assert record.get("dataset_rows_admitted") is not True
        assert record.get("level_3_materialized") is not True
