from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12661_structured_repo_state_training_eligibility_independent_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12661", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def assert_execution_gates_closed(record):
    for field in stage.FALSE_FIELDS:
        assert record[field] is False


def test_load_inputs_pins_stage12660_candidates() -> None:
    loaded = stage.load_inputs()
    assert loaded["summary"]["next_required_action"] == stage.STAGE
    assert loaded["summary"]["training_allowed"] is False
    assert len(loaded["candidates"]) == 2187


def test_review_candidates_admits_only_clean_training_eligible_rows() -> None:
    audit = stage.review_candidates(stage.load_inputs()["candidates"])
    assert audit["review_decision"] == "ADMIT_STRUCTURED_REPO_STATE_ROWS_FOR_TRAINER_CONSUMPTION_NO_TRAINING_RUN"
    assert audit["candidate_rows_reviewed"] == 2187
    assert audit["admitted_rows"] == 2187
    assert audit["split_counts"] == stage.EXPECTED_SPLITS
    assert audit["objective_counts"] == stage.EXPECTED_OBJECTIVES
    assert audit["root_split_overlap_counts"] == {"eval_strict_eval": 0, "train_eval": 0, "train_strict_eval": 0}
    assert audit["empty_template_marker_scan_passed"] is True
    assert audit["private_path_scan_passed"] is True
    assert audit["raw_text_scan_passed"] is True
    assert audit["trainer_consumable_before_admission"] == 0
    assert_execution_gates_closed(audit)


def test_admitted_rows_are_trainer_consumable_without_training_authority() -> None:
    rows = [stage.admitted_row(row) for row in stage.load_inputs()["candidates"]]
    assert len(rows) == 2187
    assert all(row["trainer_consumable"] is True for row in rows)
    assert all(row["row_admitted"] is True for row in rows)
    assert all(row["loss_weight"] == 1.0 for row in rows)
    assert all("loss_weight_after_admission" not in row for row in rows)
    assert all("training_candidate_id" not in row for row in rows)
    assert all("root_candidate_id" not in row for row in rows)
    encoded = json.dumps(rows, sort_keys=True)
    for needle in stage.PRIVATE_FORBIDDEN_SUBSTRINGS:
        assert needle not in encoded


def test_build_packet_sets_dataset_admission_but_not_training_run() -> None:
    summary, audit, admitted = stage.build_packet()
    assert summary["dataset_rows_admitted"] is True
    assert summary["structured_repo_state_rows_admitted"] is True
    assert summary["structured_repo_state_admission_ready"] is True
    assert summary["training_admission_allowed"] is True
    assert summary["strict_eval_admitted"] is True
    assert summary["strict_eval_eligible"] is True
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["training_admitted"] is False
    assert len(admitted) == 2187
    assert audit["admitted_rows"] == 2187
    assert_execution_gates_closed(summary)


def test_public_records_are_sanitized() -> None:
    summary, audit, _ = stage.build_packet()
    for label, record in (("summary", summary), ("audit", audit)):
        stage.assert_no_forbidden(record, label, stage.PUBLIC_FORBIDDEN_SUBSTRINGS)
        encoded = json.dumps(record, sort_keys=True)
        for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
            assert needle not in encoded


def test_build_writes_admission_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "admission_matrix.json",
        "contract.json",
        "digest_pointer.json",
        "private/admitted_structured_repo_state_rows.jsonl",
        "private/structured_repo_state_admission_packet.json",
        "review_audit.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert sum(1 for _ in (out / "private/admitted_structured_repo_state_rows.jsonl").open()) == 2187
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/structured_repo_state_admission_packet.json")
    audit = read_json(out / "review_audit.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["review_audit_sha256"] == stable(audit)


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "review_audit.json")
    assert summary == external
    assert summary["trainer_consumable_rows"] == 2187
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert audit["review_decision"] == summary["decision"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
