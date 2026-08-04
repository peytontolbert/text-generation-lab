from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12670_symbol_binding_trainer_contract_validation_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12670", SCRIPT)
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


def test_load_inputs_pins_stage12669_and_symbol_lane() -> None:
    loaded = stage.load_inputs()
    assert loaded["summary"]["next_required_action"] == stage.STAGE
    assert len(loaded["symbol_rows"]) == 58


def test_identity_bound_rows_adds_heldout_identity_without_target_drift() -> None:
    rows = stage.identity_bound_rows(stage.load_inputs()["symbol_rows"])
    assert len(rows) == 58
    assert stage.count(rows, "split") == stage.EXPECTED_SPLITS
    assert all(row["contract_validation_identity_bound"] is True for row in rows)
    assert all(row["repo_family"] == "source_backed_symbol_binding_knowledge" for row in rows)
    assert all(str(row["root_identity"]).startswith("symbol_binding_") for row in rows)
    assert dict(sorted(__import__("collections").Counter(row["target"]["binding_action"] for row in rows).items())) == stage.EXPECTED_ACTIONS
    assert all(row["training_allowed"] is False and row["training_run_allowed"] is False for row in rows)


def test_trainer_contract_validation_passes_without_execution(tmp_path: Path) -> None:
    rows = stage.identity_bound_rows(stage.load_inputs()["symbol_rows"])
    manifest = tmp_path / "identity_bound_symbol.jsonl"
    stage.write_jsonl(manifest, rows)
    card = stage.validate_identity_bound_manifest(manifest, tmp_path / "validation_out")
    assert card["passed"] is True
    assert card["mode"] == "symbol_binding_probe"
    assert card["rows"] == 58
    assert card["split_counts"] == {"eval": 19, "other": 0, "strict_eval": 16, "train": 23}
    assert card["loss_counts"] == {"symbol_binding_ce": 58}
    assert card["authority_rows"] == 0
    assert card["unsafe_loss_rows"] == 0
    assert card["model_execution_attempted"] is False


def test_build_writes_validation_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/identity_bound_symbol_binding_probe_candidate_manifest.jsonl",
        "private/symbol_binding_contract_validation_checks.jsonl",
        "private/symbol_binding_contract_validation_packet.json",
        "summary.json",
        "symbol_binding_contract_validation_audit.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/symbol_binding_contract_validation_packet.json")
    audit = read_json(out / "symbol_binding_contract_validation_audit.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["audit_sha256"] == stable(audit)
    assert sum(1 for _ in (out / "private/identity_bound_symbol_binding_probe_candidate_manifest.jsonl").open()) == 58


def test_build_packet_keeps_training_blocked() -> None:
    summary = stage.build()
    audit = read_json(stage.OUT / "symbol_binding_contract_validation_audit.json")
    assert summary["decision"] == "PASS_SYMBOL_BINDING_TRAINER_CONTRACT_VALIDATION_NO_EXECUTION"
    assert summary["trainer_contract_validation_passed"] is True
    assert summary["symbol_binding_lane_contract_validated"] is True
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["next_required_action"] == "stage12671_symbol_binding_lane_independent_review_only"
    assert audit["trainer_contract_card"]["passed"] is True
    assert audit["trainer_contract_card"]["model_execution_attempted"] is False
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)


def test_public_and_private_artifacts_are_sanitized() -> None:
    stage.build()
    for path in [
        stage.SUMMARY,
        stage.OUT / "summary.json",
        stage.OUT / "symbol_binding_contract_validation_audit.json",
        stage.OUT / "contract.json",
        stage.OUT / "digest_pointer.json",
        stage.OUT / "private/symbol_binding_contract_validation_packet.json",
        stage.OUT / "private/identity_bound_symbol_binding_probe_candidate_manifest.jsonl",
    ]:
        text = path.read_text(encoding="utf-8")
        for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if "private/identity_bound" not in str(path) else stage.PRIVATE_FORBIDDEN_SUBSTRINGS:
            assert needle not in text
