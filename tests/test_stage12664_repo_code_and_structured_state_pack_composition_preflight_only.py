from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12664_repo_code_and_structured_state_pack_composition_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12664", SCRIPT)
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


def test_load_inputs_pins_stage12663_and_source_manifests() -> None:
    loaded = stage.load_inputs()
    assert loaded["summary"]["next_required_action"] == stage.STAGE
    assert loaded["summary"]["training_allowed"] is False
    assert len(loaded["srs_rows"]) == 2187
    assert len(loaded["repo_rows"]) == 280
    assert len(loaded["repo_examples"]) == 280


def test_repo_rows_include_only_trainer_consumable_sidecar_rows() -> None:
    loaded = stage.load_inputs()
    repo_rows, quarantined = stage.repo_composition_rows(loaded["repo_rows"], loaded["repo_examples"])
    assert len(repo_rows) == 258
    assert len(quarantined) == 22
    assert stage.count(repo_rows, "split") == stage.EXPECTED_REPO_SPLITS
    assert all(row["curriculum_layer"] == "repo_code_knowledge" for row in repo_rows)
    assert all(row["trainer_consumable"] is True for row in repo_rows)
    assert all(row["row_admitted"] is True for row in repo_rows)


def test_structured_state_rows_preserve_downweight_policy() -> None:
    srs_rows = stage.srs_composition_rows(stage.load_inputs()["srs_rows"])
    assert len(srs_rows) == 2187
    assert stage.count(srs_rows, "split") == stage.EXPECTED_SRS_SPLITS
    assert sum(1 for row in srs_rows if row["compact_signature_cross_split_duplicate"]) == 1686
    assert sum(1 for row in srs_rows if row["loss_weight"] == 0.25) == 1686
    assert sum(1 for row in srs_rows if row["loss_weight"] == 1.0) == 501


def test_combined_composition_counts_and_sanitization() -> None:
    combined, quarantined, matrix = stage.build_composition(stage.load_inputs())
    assert len(combined) == 2445
    assert len(quarantined) == 22
    assert matrix["layer_counts"] == {"repo_code_knowledge": 258, "structured_repo_state": 2187}
    assert matrix["split_counts"] == {"eval": 374, "strict_eval": 370, "train": 1701}
    assert matrix["repo_code_quarantined_rows_preserved"] == 22
    assert matrix["structured_state_duplicate_downweighted_rows"] == 1686
    encoded = json.dumps(combined, sort_keys=True)
    for needle in stage.PRIVATE_FORBIDDEN_SUBSTRINGS:
        assert needle not in encoded
    assert_execution_gates_closed(matrix)


def test_build_packet_keeps_training_execution_closed() -> None:
    summary, matrix, combined, quarantined = stage.build_packet()
    assert summary["decision"] == "REPO_CODE_AND_STRUCTURED_STATE_PACK_COMPOSITION_PREFLIGHT_PASSED_NO_TRAINING_RUN"
    assert summary["combined_trainer_rows"] == 2445
    assert summary["repo_code_rows"] == 258
    assert summary["structured_repo_state_rows"] == 2187
    assert summary["combined_curriculum_pack_materialized"] is True
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert matrix["training_pack_composition_preflight_passed"] is True
    assert len(combined) == 2445
    assert len(quarantined) == 22
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(matrix)


def test_public_records_are_sanitized() -> None:
    summary, matrix, _, _ = stage.build_packet()
    for label, record in (("summary", summary), ("matrix", matrix)):
        stage.assert_no_forbidden(record, label, stage.PUBLIC_FORBIDDEN_SUBSTRINGS)
        encoded = json.dumps(record, sort_keys=True)
        for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
            assert needle not in encoded


def test_build_writes_pack_composition_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "pack_composition_matrix.json",
        "private/combined_curriculum_trainer_manifest.jsonl",
        "private/preserved_quarantined_repo_code_rows.jsonl",
        "private/repo_code_structured_state_pack_composition_packet.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert sum(1 for _ in (out / "private/combined_curriculum_trainer_manifest.jsonl").open()) == 2445
    assert sum(1 for _ in (out / "private/preserved_quarantined_repo_code_rows.jsonl").open()) == 22
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/repo_code_structured_state_pack_composition_packet.json")
    matrix = read_json(out / "pack_composition_matrix.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["matrix_sha256"] == stable(matrix)


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    matrix = read_json(stage.OUT / "pack_composition_matrix.json")
    assert summary == external
    assert summary["combined_trainer_rows"] == 2445
    assert summary["training_allowed"] is False
    assert matrix["training_pack_composition_preflight_passed"] is True
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(matrix)
