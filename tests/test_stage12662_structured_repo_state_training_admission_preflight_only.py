from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12662_structured_repo_state_training_admission_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12662", SCRIPT)
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


def test_load_inputs_pins_stage12661_admission() -> None:
    loaded = stage.load_inputs()
    assert loaded["summary"]["next_required_action"] == stage.STAGE
    assert loaded["summary"]["dataset_rows_admitted"] is True
    assert loaded["summary"]["training_allowed"] is False
    assert len(loaded["admitted"]) == 2187


def test_validate_admitted_rows_for_training_preflight() -> None:
    rows = stage.load_inputs()["admitted"]
    validation = stage.validate_admitted_rows(rows)
    assert validation["split_counts"] == stage.EXPECTED_SPLITS
    assert validation["objective_counts"] == stage.EXPECTED_OBJECTIVES
    assert validation["target_label_counts"] == {
        "teacher_supported": 729,
        "decisive_evidence": 729,
        "retrieve_answer_abstain": 729,
    }


def test_trainer_manifest_has_no_placeholders_or_stable_candidate_ids() -> None:
    rows = stage.build_trainer_manifest(stage.load_inputs()["admitted"])
    assert len(rows) == 2187
    assert all(row["trainer_consumable"] is True for row in rows)
    assert all(row["row_admitted"] is True for row in rows)
    assert sum(1 for row in rows if row["compact_signature_cross_split_duplicate"]) == 1686
    assert sum(1 for row in rows if row["loss_weight"] == 0.25) == 1686
    assert sum(1 for row in rows if row["loss_weight"] == 1.0) == 501
    encoded = json.dumps(rows, sort_keys=True)
    for needle in stage.PRIVATE_FORBIDDEN_SUBSTRINGS:
        assert needle not in encoded
    assert "manifest_row_id" in rows[0]
    assert "root_candidate_id" not in rows[0]
    assert "training_candidate_id" not in rows[0]


def test_repo_code_sidecar_is_reported_but_not_merged() -> None:
    sidecar = stage.repo_code_sidecar_status()
    assert sidecar["repo_code_sidecar_present"] is True
    assert sidecar["repo_code_trainer_consumable_rows"] == 258
    assert sidecar["repo_code_manifest_rows"] == 280
    assert sidecar["repo_code_contract_merge_required"] is True


def test_build_packet_passes_preflight_without_authorizing_training_run() -> None:
    summary, matrix, trainer_rows = stage.build_packet()
    assert summary["decision"] == "STRUCTURED_REPO_STATE_TRAINING_ADMISSION_PREFLIGHT_PASSED_NO_TRAINING_RUN"
    assert summary["structured_repo_state_training_pack_ready"] is True
    assert summary["structured_repo_state_trainer_rows"] == 2187
    assert summary["trainer_manifest_rows"] == 2187
    assert summary["cross_split_duplicate_compact_signature_groups"] == 254
    assert summary["cross_split_duplicate_compact_signature_rows"] == 1686
    assert summary["cross_split_duplicate_loss_weight"] == 0.25
    assert summary["dataset_rows_admitted"] is True
    assert summary["structured_repo_state_rows_admitted"] is True
    assert summary["training_admission_preflight_passed"] is True
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert matrix["repo_code_sidecar_status"]["repo_code_trainer_consumable_rows"] == 258
    assert matrix["cross_split_duplicate_compact_signature_groups"] == 254
    assert len(trainer_rows) == 2187
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(matrix)


def test_public_records_are_sanitized() -> None:
    summary, matrix, _ = stage.build_packet()
    for label, record in (("summary", summary), ("matrix", matrix)):
        stage.assert_no_forbidden(record, label, stage.PUBLIC_FORBIDDEN_SUBSTRINGS)
        encoded = json.dumps(record, sort_keys=True)
        for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
            assert needle not in encoded


def test_build_writes_training_admission_preflight_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/structured_repo_state_trainer_manifest.jsonl",
        "private/structured_repo_state_training_admission_packet.json",
        "summary.json",
        "training_admission_matrix.json",
    ]
    assert summary == read_json(summary_path)
    assert sum(1 for _ in (out / "private/structured_repo_state_trainer_manifest.jsonl").open()) == 2187
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/structured_repo_state_training_admission_packet.json")
    matrix = read_json(out / "training_admission_matrix.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["matrix_sha256"] == stable(matrix)


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    matrix = read_json(stage.OUT / "training_admission_matrix.json")
    assert summary == external
    assert summary["trainer_manifest_rows"] == 2187
    assert summary["training_allowed"] is False
    assert matrix["training_admission_preflight_passed"] is True
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(matrix)
