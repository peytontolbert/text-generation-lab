from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12660_structured_repo_state_reviewed_candidate_enrichment_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12660", SCRIPT)
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


def test_load_inputs_pins_stage12659_review_boundary() -> None:
    loaded = stage.load_inputs()
    assert loaded["summary"]["next_required_action"] == stage.STAGE
    assert loaded["summary"]["training_allowed"] is False
    assert loaded["audit"]["review_decision"] == "PASS_AS_SANITIZED_REVIEW_CANDIDATE_MANIFEST_NOT_ADMISSION"
    assert len(loaded["manifest"]) == 3975


def test_root_metadata_enriches_all_loss_bearing_rows() -> None:
    loaded = stage.load_inputs()
    training_rows, support_rows = stage.build_training_candidates(loaded["manifest"])
    assert len(training_rows) == 2187
    assert len(support_rows) == 729
    assert all(row["input_state"]["repo_family_bucket"] != "unknown" for row in training_rows)
    assert all(row["input_state"]["language_family"] != "unknown" for row in training_rows)
    assert all(row["target_label"] in stage.LOSS_FAMILY_BY_LABEL for row in training_rows)
    assert {row["target_label"] for row in training_rows} == {"teacher_supported", "decisive_evidence", "retrieve_answer_abstain"}


def test_no_placeholder_or_raw_source_text_in_training_candidates() -> None:
    training_rows, support_rows = stage.build_training_candidates(stage.load_inputs()["manifest"])
    encoded = json.dumps({"training": training_rows, "support": support_rows}, sort_keys=True)
    for needle in stage.PRIVATE_FORBIDDEN_SUBSTRINGS:
        assert needle not in encoded
    assert "target_label" in encoded
    assert "input_state" in encoded


def test_training_eligible_candidates_have_splits_but_are_not_admitted() -> None:
    training_rows, _ = stage.build_training_candidates(stage.load_inputs()["manifest"])
    split_counts = {}
    objective_counts = {}
    for row in training_rows:
        split_counts[row["split"]] = split_counts.get(row["split"], 0) + 1
        objective_counts[row["training_objective"]] = objective_counts.get(row["training_objective"], 0) + 1
    assert split_counts == {"train": 1557, "eval": 315, "strict_eval": 315}
    assert objective_counts == {
        "structured_repo_state.evidence_role": 729,
        "structured_repo_state.evidence_route": 729,
        "structured_repo_state.hypothesis_status": 729,
    }
    assert all(row["training_eligible_candidate"] is True for row in training_rows)
    assert all(row["trainer_consumable"] is False for row in training_rows)
    assert all(row["row_admitted"] is False for row in training_rows)
    assert all(row["admission_required_before_training"] is True for row in training_rows)


def test_build_packet_keeps_training_authority_closed() -> None:
    summary, matrix, training_rows, support_rows = stage.build_packet()
    assert summary["decision"] == "STRUCTURED_REPO_STATE_TRAINING_ELIGIBLE_CANDIDATES_MATERIALIZED_NO_TRAINING_ADMISSION"
    assert summary["training_eligibility_materialized"] is True
    assert summary["training_eligible_candidate_rows"] == 2187
    assert summary["trainer_consumable_rows"] == 0
    assert summary["row_admitted_count"] == 0
    assert matrix["split_counts"] == {"eval": 315, "strict_eval": 315, "train": 1557}
    assert len(training_rows) == 2187
    assert len(support_rows) == 729
    assert_false_boundaries(summary)
    assert_false_boundaries(matrix)


def test_public_records_are_sanitized() -> None:
    summary, matrix, _, _ = stage.build_packet()
    for label, record in (("summary", summary), ("matrix", matrix)):
        stage.assert_no_forbidden(record, label, stage.PUBLIC_FORBIDDEN_SUBSTRINGS)
        encoded = json.dumps(record, sort_keys=True)
        for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
            assert needle not in encoded


def test_build_writes_training_eligible_candidate_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/root_metadata_support_rows.jsonl",
        "private/structured_repo_state_training_eligible_candidate_packet.json",
        "private/training_eligible_structured_repo_state_candidates.jsonl",
        "summary.json",
        "training_eligible_candidate_matrix.json",
    ]
    assert summary == read_json(summary_path)
    assert sum(1 for _ in (out / "private/training_eligible_structured_repo_state_candidates.jsonl").open()) == 2187
    assert sum(1 for _ in (out / "private/root_metadata_support_rows.jsonl").open()) == 729
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/structured_repo_state_training_eligible_candidate_packet.json")
    matrix = read_json(out / "training_eligible_candidate_matrix.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["matrix_sha256"] == stable(matrix)


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    matrix = read_json(stage.OUT / "training_eligible_candidate_matrix.json")
    assert summary == external
    assert summary["training_allowed"] is False
    assert summary["training_eligible_candidate_rows"] == 2187
    assert matrix["trainer_consumable_rows"] == 0
    assert_false_boundaries(summary)
    assert_false_boundaries(matrix)
