from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12666_combined_curriculum_training_authorization_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12666", SCRIPT)
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


def test_load_inputs_pins_reviewed_combined_pack() -> None:
    loaded = stage.load_inputs()
    assert loaded["summary"]["next_required_action"] == stage.STAGE
    assert loaded["summary"]["training_allowed"] is False
    assert len(loaded["rows"]) == 2445


def test_audit_rows_preserves_admitted_pack_counts() -> None:
    loaded = stage.load_inputs()
    audit = stage.audit_rows(loaded["rows"])
    assert audit["combined_rows_checked"] == 2445
    assert audit["split_counts"] == stage.EXPECTED_SPLITS
    assert audit["layer_counts"] == stage.EXPECTED_LAYERS
    assert audit["objective_counts"] == stage.EXPECTED_OBJECTIVES
    assert audit["structured_duplicate_downweighted_rows"] == 1686


def test_schema_fingerprint_detects_mixed_noncanonical_rows() -> None:
    loaded = stage.load_inputs()
    report = stage.row_schema_fingerprint(loaded["rows"])
    assert report["distinct_schema_count"] == 2
    assert report["all_rows_match_canonical_manifest_schema"] is False
    missing_sets = [set(item["canonical_required_missing"]) for item in report["schemas"]]
    assert any({"row_id", "language_family", "input_state", "target", "authority", "source_provenance", "anti_cheat_contract"}.issubset(missing) for missing in missing_sets)
    assert any({"row_id", "language_family", "target", "authority", "source_provenance", "anti_cheat_contract"}.issubset(missing) for missing in missing_sets)


def test_trainer_contract_support_blocks_unbound_objectives() -> None:
    support = stage.objective_support_report()
    assert support["canonical_schema_required_fields_match_expected"] is True
    assert support["loss_literal_support"]["symbol_binding_ce"] is True
    assert support["objective_literals_supported"]["structured_repo_state.evidence_role"] is False
    assert support["objective_literals_supported"]["structured_repo_state.evidence_route"] is False
    assert support["objective_literals_supported"]["structured_repo_state.hypothesis_status"] is False
    assert support["combined_manifest_requires_adapter"] is True


def test_build_packet_blocks_training_authorization_without_adapter() -> None:
    summary, audit, checks = stage.build_packet()
    assert summary["decision"] == "BLOCKED_TRAINER_CONTRACT_ADAPTER_REQUIRED"
    assert summary["dataset_rows_admitted"] is True
    assert summary["combined_dataset_rows_admitted"] is True
    assert summary["training_authorization_preflight_passed"] is False
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["training_admitted"] is False
    assert summary["next_required_action"] == "stage12667_combined_curriculum_trainer_contract_adapter_preflight_only"
    assert audit["authorization_blockers"] == summary["authorization_blockers"]
    assert [row["check_id"] for row in checks if row["status"] == "blocked"] == [
        "canonical_manifest_schema_binding",
        "trainer_objective_binding",
        "training_execution_authority",
    ]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)


def test_public_records_are_sanitized() -> None:
    summary, audit, _ = stage.build_packet()
    for label, record in (("summary", summary), ("audit", audit)):
        stage.assert_no_forbidden(record, label, stage.PUBLIC_FORBIDDEN_SUBSTRINGS)
        encoded = json.dumps(record, sort_keys=True)
        for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
            assert needle not in encoded


def test_build_writes_preflight_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "authorization_audit.json",
        "contract.json",
        "digest_pointer.json",
        "private/authorization_checks.jsonl",
        "private/training_authorization_preflight_packet.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/training_authorization_preflight_packet.json")
    audit = read_json(out / "authorization_audit.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["audit_sha256"] == stable(audit)
    assert sum(1 for _ in (out / "private/authorization_checks.jsonl").open()) == 6


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "authorization_audit.json")
    assert summary == external
    assert summary["combined_rows_checked"] == 2445
    assert summary["decision"] == "BLOCKED_TRAINER_CONTRACT_ADAPTER_REQUIRED"
    assert audit["decision"] == summary["decision"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
