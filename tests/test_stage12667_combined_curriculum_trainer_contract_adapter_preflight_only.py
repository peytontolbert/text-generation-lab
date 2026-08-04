from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12667_combined_curriculum_trainer_contract_adapter_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12667", SCRIPT)
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


def test_load_inputs_pins_stage12666_and_source_sidecars() -> None:
    loaded = stage.load_inputs()
    assert loaded["summary"]["next_required_action"] == stage.STAGE
    assert loaded["summary"]["training_allowed"] is False
    assert len(loaded["combined"]) == 2445
    assert len(loaded["examples"]) == 280


def test_adapt_rows_materializes_canonical_required_fields() -> None:
    loaded = stage.load_inputs()
    rows = stage.adapt_rows(loaded["combined"], loaded["examples"])
    assert len(rows) == 2445
    for row in rows:
        assert not stage.CANONICAL_REQUIRED_FIELDS.difference(row)
        assert row["authority"]["training_allowed"] is False
        assert row["authority"]["optimizer_step_authorized"] is False
    repo = next(row for row in rows if row["row_id"].startswith("repo_code_"))
    assert repo["input_state"]["prompt_surface"]
    assert repo["target"]["decoder_text"]
    structured = next(row for row in rows if row["row_id"].startswith("structured_state_"))
    assert structured["target"]["bounded_choice_target_label"]


def test_adapter_audit_detects_loss_binding_blockers() -> None:
    loaded = stage.load_inputs()
    rows = stage.adapt_rows(loaded["combined"], loaded["examples"])
    audit = stage.adapter_audit(rows)
    assert audit["adapter_candidate_rows"] == 2445
    assert audit["split_counts"] == stage.EXPECTED_SPLITS
    assert audit["canonical_required_fields_present"] is True
    assert audit["all_authority_gates_closed"] is True
    assert audit["enabled_loss_counts"] == {
        "repo_code_ce": 200,
        "structured_repo_state_ce": 2187,
        "symbol_binding_ce": 58,
    }
    assert audit["unsupported_loss_key_rows"] == 2387
    assert audit["rows_with_no_supported_loss_key"] == 2387
    assert audit["adapter_manifest_trainer_runnable"] is False


def test_build_packet_materializes_candidate_but_blocks_training() -> None:
    summary, audit, checks, rows = stage.build_packet()
    assert len(rows) == 2445
    assert summary["decision"] == "ADAPTER_CANDIDATE_MATERIALIZED_BLOCKED_LOSS_AND_SCHEDULE_BINDING"
    assert summary["adapter_candidate_rows"] == 2445
    assert summary["canonical_required_fields_present"] is True
    assert summary["unsupported_loss_key_rows"] == 2387
    assert summary["rows_with_no_supported_loss_key"] == 2387
    assert summary["adapter_manifest_trainer_runnable"] is False
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["next_required_action"] == "stage12668_combined_curriculum_loss_and_schedule_binding_preflight_only"
    assert [row["check_id"] for row in checks if row["status"] == "blocked"] == [
        "loss_key_trainer_binding",
        "mixed_objective_schedule_binding",
        "training_execution_authority",
    ]
    assert audit["authorization_blockers"] == summary["authorization_blockers"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)


def test_public_records_are_sanitized() -> None:
    summary, audit, _, _ = stage.build_packet()
    for label, record in (("summary", summary), ("audit", audit)):
        stage.assert_no_forbidden(record, label, stage.PUBLIC_FORBIDDEN_SUBSTRINGS)
        encoded = json.dumps(record, sort_keys=True)
        for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
            assert needle not in encoded


def test_private_adapter_manifest_has_no_forbidden_markers() -> None:
    _, _, _, rows = stage.build_packet()
    encoded = json.dumps(rows, sort_keys=True, ensure_ascii=True)
    for needle in stage.PRIVATE_FORBIDDEN_SUBSTRINGS:
        assert needle not in encoded


def test_build_writes_adapter_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "adapter_audit.json",
        "contract.json",
        "digest_pointer.json",
        "private/adapter_checks.jsonl",
        "private/combined_curriculum_canonical_adapter_candidate_manifest.jsonl",
        "private/trainer_contract_adapter_packet.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/trainer_contract_adapter_packet.json")
    audit = read_json(out / "adapter_audit.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["audit_sha256"] == stable(audit)
    assert sum(1 for _ in (out / "private/adapter_checks.jsonl").open()) == 7
    assert sum(1 for _ in (out / "private/combined_curriculum_canonical_adapter_candidate_manifest.jsonl").open()) == 2445


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "adapter_audit.json")
    assert summary == external
    assert summary["adapter_candidate_rows"] == 2445
    assert summary["decision"] == "ADAPTER_CANDIDATE_MATERIALIZED_BLOCKED_LOSS_AND_SCHEDULE_BINDING"
    assert audit["adapter_manifest_trainer_runnable"] is False
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
