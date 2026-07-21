import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12531_private_binding_review_return_coordination_guardrail.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def required_fields() -> list[str]:
    return [
        "record_type",
        "private_review_packet_id_hash",
        "candidate_binding_source_id_hash",
        "review_action",
        "private_reviewer_id_hash",
        "reviewer_conflict_check_hash",
        "reviewer_independence_attestation",
        "review_decision_reason_code",
        "acceptance_criteria_passed",
        "trusted_binding_confirmed",
        "authorized_return_writer_confirmed",
        "binding_authority_current",
        "scope_limited_to_stage12521_stage12516_stage12503_flow",
        "return_writer_destination_authorized",
        "maps_to_343_slot_context",
        "slot_context_gap_code",
        "no_training_admission_level3_patch_trace_requested",
        "raw_private_values_revealed",
        "raw_source_output_included",
        "raw_paths_included",
        "raw_commands_included",
        "raw_diffs_included",
        "raw_verifier_output_included",
        "candidate_file_contents_read_publicly",
        "stage12521_readiness_manifest_written",
        "stage12516_candidate_row_written",
        "stage12503_return_file_written",
        "training_allowed",
        "admission_allowed",
        "level3_atom_materialized",
        "patch_trace_materialized",
        "blocker_codes",
    ]


def write_stage12528_fixture(root: Path) -> None:
    out = root / "runs/local/artifacts/stage12528_private_binding_review_return_preflight"
    write_json(
        out / "summary.json",
        {
            "record_type": "stage12528_private_binding_review_return_preflight_summary_v1",
            "decision": "blocked_no_private_binding_review_return_file",
            "preserved_slot_count_context": 343,
            "return_file_present": False,
            "ready_candidate_count": 0,
        },
    )
    write_json(
        out / "private_binding_review_return_schema.json",
        {
            "record_type": "stage12528_private_binding_review_return_schema_v1",
            "return_record_type": "stage12528_private_binding_review_return_v1",
            "required_public_safe_return_fields": required_fields(),
            "allowed_review_actions": ["authorized_return_writer", "blocked", "reject", "trusted_binding"],
            "ready_review_actions": ["authorized_return_writer", "trusted_binding"],
            "public_safe_metadata_only": True,
        },
    )


def dashboard_row(shard_index: int, item_count: int) -> dict:
    return {
        "record_type": "stage12530_private_binding_review_missing_return_dashboard_v1",
        "dashboard_row_id_hash": f"{shard_index + 1000:024x}",
        "work_order_shard_id_hash": f"{shard_index + 2000:024x}",
        "work_order_shard_index": shard_index,
        "work_order_shard_count": 2,
        "work_order_item_count": item_count,
        "candidate_binding_source_id_hashes": [f"{shard_index + 3000:024x}"],
        "private_review_packet_id_hashes": [f"{shard_index + 4000:024x}"],
        "target_return_stage": "stage12527_private_binding_review_queue",
        "target_return_filename": "private_binding_review_returns.jsonl",
        "return_file_present": False,
        "blocker_code": "stage12527_private_binding_review_returns_jsonl_absent",
        "required_next_stage": "stage12528_private_binding_review_return_preflight",
        "stage12528_validation_required": False,
        "public_safe_metadata_only": True,
        "preserved_slot_count_context": 343,
        "return_file_contents_read": False,
        "readiness_claimed": False,
    }


def write_stage12530_fixture(root: Path) -> None:
    out = root / "runs/local/artifacts/stage12530_private_binding_review_return_presence_audit"
    rows = [dashboard_row(1, 20), dashboard_row(2, 9)]
    write_jsonl(out / "private_binding_review_missing_return_dashboard.jsonl", rows)
    write_json(
        out / "summary.json",
        {
            "record_type": "stage12530_private_binding_review_return_presence_audit_summary_v1",
            "decision": "blocked_missing_stage12527_private_binding_review_returns_dashboard_emitted",
            "target_return_stage": "stage12527_private_binding_review_queue",
            "target_return_filename": "private_binding_review_returns.jsonl",
            "return_file_present": False,
            "return_file_contents_read": False,
            "stage12530_dashboard_row_count": 2,
            "preserved_slot_count_context": 343,
            "training_rows_emitted": 0,
            "level3_atom_count": 0,
            "patch_trace_rows": 0,
        },
    )


def write_inputs(root: Path) -> None:
    write_stage12528_fixture(root)
    write_stage12530_fixture(root)


def test_missing_return_file_emits_operator_coordination_without_fabricating_outputs(tmp_path: Path) -> None:
    stage12531 = load_module(SCRIPT, "stage12531_absent")
    write_inputs(tmp_path)

    summary = stage12531.build(tmp_path)

    assert summary["decision"] == "blocked_missing_private_binding_review_return_coordination_guardrail_emitted"
    assert summary["return_file_present"] is False
    assert summary["return_file_contents_read"] is False
    assert summary["next_stage"] == "private_reviewer_supplies_stage12527_private_binding_review_returns_jsonl"
    assert summary["coordination_checklist_row_count"] == 2
    assert summary["work_order_item_count"] == 29
    assert summary["work_order_shard_count"] == 2
    assert summary["stage12529_work_order_item_count"] == 29
    assert summary["stage12529_work_order_shard_count"] == 2
    assert summary["stage12528_validation_required"] is False
    assert summary["ready_candidate_count"] == 0
    assert summary["stage12521_readiness_manifest_count"] == 0
    assert summary["stage12516_candidate_row_count"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_rows_emitted"] == 0
    assert summary["level3_atom_count"] == 0
    assert summary["patch_trace_rows"] == 0

    out = tmp_path / "runs/local/artifacts/stage12531_private_binding_review_return_coordination_guardrail"
    checklist = read_jsonl(out / "private_binding_review_return_coordination_checklist.jsonl")
    assert [row["work_order_item_count"] for row in checklist] == [20, 9]
    assert {row["required_operator_action_code"] for row in checklist} == {
        "supply_stage12527_private_binding_review_returns_jsonl"
    }
    assert {row["destination_token"] for row in checklist} == {
        "stage12527_private_binding_review_queue::private_binding_review_returns.jsonl"
    }
    assert all(row["return_file_contents_read"] is False for row in checklist)
    assert all(row["readiness_claimed"] is False for row in checklist)
    assert all(row["stage12521_readiness_manifest_count"] == 0 for row in checklist)

    gate = read_json(out / "private_binding_review_return_validation_gate.json")
    assert gate["validation_gate_status"] == "blocked_until_return_file_supplied"
    assert gate["return_file_contents_read"] is False
    assert gate["required_public_safe_return_fields"] == required_fields()


def test_present_return_file_points_to_stage12528_without_reading_or_validating_rows(tmp_path: Path) -> None:
    stage12531 = load_module(SCRIPT, "stage12531_present")
    write_inputs(tmp_path)
    return_out = tmp_path / "runs/local/artifacts/stage12527_private_binding_review_queue"
    write_jsonl(return_out / "private_binding_review_returns.jsonl", [{"not_read_by_stage12531": True}])

    summary = stage12531.build(tmp_path)

    assert summary["decision"] == "return_file_present_rerun_stage12528_validation_no_stage12531_parse"
    assert summary["return_file_present"] is True
    assert summary["return_file_contents_read"] is False
    assert summary["stage12528_validation_required"] is True
    assert summary["next_stage"] == "rerun_stage12528_private_binding_review_return_preflight_for_validation"
    assert summary["work_order_item_count"] == 29
    assert summary["work_order_shard_count"] == 2
    assert summary["accepted_private_review_status_count"] == 0
    assert summary["ready_review_status_count"] == 0
    assert summary["ready_candidate_count"] == 0

    out = tmp_path / "runs/local/artifacts/stage12531_private_binding_review_return_coordination_guardrail"
    checklist = read_jsonl(out / "private_binding_review_return_coordination_checklist.jsonl")
    assert {row["required_operator_action_code"] for row in checklist} == {
        "rerun_stage12528_private_binding_review_return_preflight"
    }
    assert all(row["stage12528_validation_required"] is True for row in checklist)
    assert all(row["return_file_contents_read"] is False for row in checklist)

    gate = read_json(out / "private_binding_review_return_validation_gate.json")
    assert gate["validation_gate_status"] == "stage12528_validation_pending"
    assert gate["private_return_rows_created_by_stage"] is False
