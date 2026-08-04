from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12658_structured_repo_state_sanitized_candidate_manifest_preflight_only.py"
import importlib.util
SPEC = importlib.util.spec_from_file_location("stage12658", SCRIPT)
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


def test_load_pinned_inputs_keeps_stage12657_boundary_closed() -> None:
    loaded = stage.load_pinned_inputs()
    assert loaded["stage12657_summary"]["next_required_action"] == stage.STAGE
    assert loaded["stage12657_summary"]["training_allowed"] is False
    assert len(loaded["roots"]) == 784
    assert len(loaded["states"]) == 784
    assert len(loaded["targets"]) == 2407


def test_manifest_sanitizes_only_stage10516_and_excludes_reference_sources() -> None:
    manifest, excluded = stage.build_manifest_rows(stage.load_pinned_inputs())
    assert len(manifest) == 3975
    assert sum(1 for row in manifest if row["source_row_family"] == "compiled_root_records") == 784
    assert sum(1 for row in manifest if row["source_row_family"] == "compiled_causal_states") == 784
    assert sum(1 for row in manifest if row["source_row_family"] == "compiled_multitarget_rows") == 2407
    assert sum(row["row_count"] for row in excluded) == 423
    assert {row["source_id"] for row in excluded} == {
        "stage9916_hardened_weighted_structured_state",
        "stage12266_episode_graph_review_results",
        "stage12213_strict_fail_current_state_records",
    }


def test_manifest_quarantines_terminal_later_layer_and_visible_target_rows() -> None:
    manifest, _ = stage.build_manifest_rows(stage.load_pinned_inputs())
    status_counts = {}
    for row in manifest:
        status_counts[row["candidate_status"]] = status_counts.get(row["candidate_status"], 0) + 1
    assert status_counts == {
        "candidate_for_independent_review": 2916,
        "quarantined_target_leak_or_later_layer": 949,
        "quarantined_terminal_or_action_policy_state": 110,
    }
    assert sum(1 for row in manifest if row["source_target_visible"]) == 750
    assert all(row["trainer_consumable"] is False for row in manifest)
    assert all(row["row_admitted"] is False for row in manifest)
    assert all(row["loss_weight"] == 0.0 for row in manifest)


def test_private_manifest_contains_no_raw_text_paths_or_lineage_fields() -> None:
    manifest, _ = stage.build_manifest_rows(stage.load_pinned_inputs())
    encoded = json.dumps(manifest, sort_keys=True)
    for needle in stage.PRIVATE_FORBIDDEN_SUBSTRINGS:
        assert needle not in encoded
    assert "srs_root_" in encoded
    assert "root_candidate_id" in encoded


def test_packet_counts_and_gates_remain_closed() -> None:
    summary, matrix, manifest, excluded = stage.build_packet()
    assert summary["decision"] == "STRUCTURED_REPO_STATE_SANITIZED_CANDIDATE_MANIFEST_MATERIALIZED_NO_ROW_ADMISSION"
    assert summary["sanitized_candidate_rows"] == 3975
    assert summary["eligible_for_stage12659_review"] == 2916
    assert summary["quarantined_candidate_rows"] == 1059
    assert summary["excluded_reference_source_rows"] == 423
    assert matrix["source_row_family_counts"] == {
        "compiled_causal_states": 784,
        "compiled_multitarget_rows": 2407,
        "compiled_root_records": 784,
    }
    assert matrix["blockers"] == list(stage.BLOCKERS)
    assert len(manifest) == 3975
    assert sum(row["row_count"] for row in excluded) == 423
    assert_false_boundaries(summary)
    assert_false_boundaries(matrix)


def test_public_records_are_sanitized() -> None:
    summary, matrix, _, _ = stage.build_packet()
    for label, record in (("summary", summary), ("matrix", matrix)):
        stage.assert_no_forbidden(record, label, stage.PUBLIC_FORBIDDEN_SUBSTRINGS)
        encoded = json.dumps(record, sort_keys=True)
        for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
            assert needle not in encoded


def test_build_writes_stage12658_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/excluded_reference_sources.jsonl",
        "private/sanitized_structured_repo_state_candidate_manifest.jsonl",
        "private/structured_repo_state_sanitized_manifest_packet.json",
        "sanitized_candidate_matrix.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert sum(1 for _ in (out / "private/sanitized_structured_repo_state_candidate_manifest.jsonl").open()) == 3975
    assert sum(1 for _ in (out / "private/excluded_reference_sources.jsonl").open()) == 3
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    matrix = read_json(out / "sanitized_candidate_matrix.json")
    private = read_json(out / "private/structured_repo_state_sanitized_manifest_packet.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["matrix_sha256"] == stable(matrix)
    assert pointer["private_packet_sha256"] == stable(private)


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    matrix = read_json(stage.OUT / "sanitized_candidate_matrix.json")
    assert summary == external
    assert summary["training_allowed"] is False
    assert summary["structured_repo_state_rows_admitted"] is False
    assert matrix["sanitized_candidate_rows"] == 3975
    assert_false_boundaries(summary)
    assert_false_boundaries(matrix)
