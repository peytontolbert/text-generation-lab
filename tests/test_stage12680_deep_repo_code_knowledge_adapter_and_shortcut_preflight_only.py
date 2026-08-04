from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12680_deep_repo_code_knowledge_adapter_and_shortcut_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12680", SCRIPT)
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


def test_load_inputs_pins_stage12679_and_stage12678_rows() -> None:
    summary79, audit79, rows = stage.load_inputs()
    assert summary79["recommended_next_stage"] == stage.STAGE
    assert summary79["deep_knowledge_rows_reviewed"] == 120000
    assert audit79["target_duplicate_instances"] == 80334
    assert len(rows) == 120000


def test_build_adapter_quarantines_worst_deep_shortcuts_and_downweights_rest() -> None:
    _, _, rows = stage.load_inputs()
    adapter_rows, quarantine_rows, shortcut_audit = stage.build_adapter(rows)
    assert len(adapter_rows) == 97462
    assert len(quarantine_rows) == 22538
    assert shortcut_audit["target_signature_count"] == 45033
    assert shortcut_audit["target_duplicate_instances_before_policy"] == 80334
    assert shortcut_audit["target_duplicate_excess_rows_before_policy"] == 74967
    assert shortcut_audit["target_duplicate_signatures_cross_split_before_policy"] == 1068
    assert shortcut_audit["quarantine_threshold"] == 1000
    assert shortcut_audit["quarantined_target_signatures"] == 9
    assert shortcut_audit["effective_weighted_rows"] == 52073.566783
    assert shortcut_audit["split_counts"] == {"eval": 16232, "strict_eval": 16393, "train": 64837}
    first = adapter_rows[0]
    assert set(first) >= stage.CANONICAL_REQUIRED_FIELDS
    assert first["loss_mask"] == {"deep_repo_code_knowledge_ce": True}
    assert first["adapter_status"] == "deep_repo_code_knowledge_adapter_bound_shortcut_weighted_review_required"
    assert first["authority"] == {
        "body_emission_authorized": False,
        "loss_authorized": False,
        "model_execution_authorized": False,
        "optimizer_step_authorized": False,
        "runtime_authorized": False,
        "source_emission_authorized": False,
        "training_allowed": False,
        "training_run_allowed": False,
    }
    stage.assert_no_forbidden(first, "first_adapter_row")


def test_build_packet_materializes_policy_without_training_admission() -> None:
    summary, audit, shortcut_audit, adapter_rows, quarantine_rows = stage.build_packet()
    assert summary["decision"] == "DEEP_REPO_CODE_KNOWLEDGE_ADAPTER_AND_SHORTCUT_POLICY_MATERIALIZED_REVIEW_REQUIRED"
    assert summary["source_rows_reviewed"] == 120000
    assert summary["adapter_candidate_rows"] == 97462
    assert summary["quarantined_rows"] == 22538
    assert summary["effective_weighted_rows"] == 52073.566783
    assert summary["enabled_loss_counts"] == {"deep_repo_code_knowledge_ce": 97462}
    assert summary["next_required_action"] == "stage12681_precise_symbol_doc_test_link_materialization_preflight_only"
    assert audit["stage12679_blockers_addressed"]["trainer_adapter_fit"].startswith("resolved_canonical")
    assert audit["stage12679_blockers_addressed"]["file_split_repair_status"].startswith("not_resolved")
    assert audit["training_source_rows_admitted"] == 0
    assert len(adapter_rows) == 97462
    assert len(quarantine_rows) == 22538
    assert shortcut_audit["adapter_candidate_rows"] == 97462
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
    assert_execution_gates_closed(shortcut_audit)


def test_public_records_are_sanitized() -> None:
    summary, audit, shortcut_audit, _, _ = stage.build_packet()
    stage.assert_no_forbidden(summary, "summary")
    stage.assert_no_forbidden(audit, "audit")
    stage.assert_no_forbidden(shortcut_audit, "shortcut_audit")


def test_build_writes_adapter_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "deep_repo_code_knowledge_adapter_audit.json",
        "deep_repo_code_knowledge_shortcut_baseline_audit.json",
        "digest_pointer.json",
        "private/deep_repo_code_knowledge_adapter_candidates.jsonl",
        "private/deep_repo_code_knowledge_adapter_packet.json",
        "private/deep_repo_code_knowledge_shortcut_quarantine.jsonl",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/deep_repo_code_knowledge_adapter_packet.json")
    audit = read_json(out / "deep_repo_code_knowledge_adapter_audit.json")
    shortcut_audit = read_json(out / "deep_repo_code_knowledge_shortcut_baseline_audit.json")
    adapter_rows = [json.loads(line) for line in (out / "private/deep_repo_code_knowledge_adapter_candidates.jsonl").read_text().splitlines()]
    quarantine_rows = [json.loads(line) for line in (out / "private/deep_repo_code_knowledge_shortcut_quarantine.jsonl").read_text().splitlines()]
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["audit_sha256"] == stable(audit)
    assert pointer["shortcut_audit_sha256"] == stable(shortcut_audit)
    assert pointer["adapter_rows_sha256"] == stable(adapter_rows)
    assert pointer["quarantine_rows_sha256"] == stable(quarantine_rows)
    assert len(adapter_rows) == 97462
    assert len(quarantine_rows) == 22538


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "deep_repo_code_knowledge_adapter_audit.json")
    shortcut_audit = read_json(stage.OUT / "deep_repo_code_knowledge_shortcut_baseline_audit.json")
    assert summary == external
    assert summary["adapter_candidate_rows"] == 97462
    assert summary["quarantined_rows"] == 22538
    assert shortcut_audit["effective_weighted_rows"] == 52073.566783
    assert audit["decision"] == summary["decision"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
    assert_execution_gates_closed(shortcut_audit)
