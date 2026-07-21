import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12530_private_binding_review_return_presence_audit.py"


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


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def work_item(idx: int) -> dict:
    shard_index = (idx - 1) // 20 + 1
    candidate_class = "private_executor_config_candidate_name" if idx <= 44 else "trusted_binding_candidate_name"
    return {
        "record_type": "stage12529_private_binding_review_work_order_item_v1",
        "work_order_item_id_hash": f"{idx + 1000:024x}",
        "work_order_shard_id_hash": f"{shard_index + 2000:024x}",
        "work_order_item_index": idx,
        "work_order_shard_index": shard_index,
        "private_review_packet_id_hash": f"{idx:024x}",
        "candidate_binding_source_id_hash": f"{idx + 3000:024x}",
        "candidate_class": candidate_class,
        "review_band": "p2_executor_config_review" if idx <= 20 else "p1_trusted_binding_review",
        "priority_rank": idx,
        "preserved_slot_count_context": 343,
        "candidate_contents_read": False,
        "readiness_claimed": False,
    }


def shard_rows(items: list[dict]) -> list[dict]:
    rows = []
    for shard_index in range(1, 5):
        shard_items = [item for item in items if item["work_order_shard_index"] == shard_index]
        rows.append(
            {
                "record_type": "stage12529_private_binding_review_work_order_shard_v1",
                "work_order_shard_id_hash": f"{shard_index + 2000:024x}",
                "work_order_shard_index": shard_index,
                "work_order_shard_count": 4,
                "work_order_item_count": len(shard_items),
                "candidate_binding_source_id_hashes": [item["candidate_binding_source_id_hash"] for item in shard_items],
                "private_review_packet_id_hashes": [item["private_review_packet_id_hash"] for item in shard_items],
                "preserved_slot_count_context": 343,
                "target_return_stage": "stage12527_private_binding_review_queue",
                "target_return_filename": "private_binding_review_returns.jsonl",
                "candidate_contents_read": False,
                "readiness_claimed": False,
            }
        )
    return rows


def write_stage12528_fixture(root: Path) -> None:
    out = root / "runs/local/artifacts/stage12528_private_binding_review_return_preflight"
    required = [
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
    write_json(
        out / "summary.json",
        {
            "record_type": "stage12528_private_binding_review_return_preflight_summary_v1",
            "decision": "blocked_no_private_binding_review_return_file",
            "stage12527_private_review_queue_count": 69,
            "preserved_slot_count_context": 343,
            "return_file_present": False,
            "blocked_private_review_queue_item_count": 69,
            "ready_candidate_count": 0,
        },
    )
    write_json(
        out / "private_binding_review_return_schema.json",
        {
            "record_type": "stage12528_private_binding_review_return_schema_v1",
            "source_stage": "stage12527_private_binding_review_queue",
            "return_record_type": "stage12528_private_binding_review_return_v1",
            "required_public_safe_return_fields": required,
            "allowed_review_actions": ["authorized_return_writer", "blocked", "reject", "trusted_binding"],
            "ready_review_actions": ["authorized_return_writer", "trusted_binding"],
            "public_safe_metadata_only": True,
        },
    )


def write_stage12529_fixture(root: Path) -> list[dict]:
    items = [work_item(idx) for idx in range(1, 70)]
    shards = shard_rows(items)
    out = root / "runs/local/artifacts/stage12529_private_binding_review_work_order_shards"
    write_jsonl(out / "private_binding_review_work_order_items.jsonl", items)
    write_jsonl(out / "private_binding_review_work_order_shards.jsonl", shards)
    write_json(
        out / "summary.json",
        {
            "record_type": "stage12529_private_binding_review_work_order_shards_summary_v1",
            "decision": "private_reviewer_work_order_shards_emitted_no_readiness_claimed",
            "stage12527_private_review_queue_count": 69,
            "stage12528_return_blocker_count": 69,
            "work_order_item_count": 69,
            "work_order_shard_count": 4,
            "preserved_slot_count_context": 343,
            "target_return_stage": "stage12527_private_binding_review_queue",
            "target_return_filename": "private_binding_review_returns.jsonl",
            "stage12521_readiness_manifest_count": 0,
            "stage12516_candidate_row_count": 0,
            "stage12503_return_records_written": 0,
            "training_rows_emitted": 0,
            "admitted_rows": 0,
        },
    )
    return items


def valid_return_for(item: dict) -> dict:
    return {
        "record_type": "stage12528_private_binding_review_return_v1",
        "private_review_packet_id_hash": item["private_review_packet_id_hash"],
        "candidate_binding_source_id_hash": item["candidate_binding_source_id_hash"],
        "review_action": "trusted_binding",
        "private_reviewer_id_hash": "000000000000000000001999",
        "reviewer_conflict_check_hash": "000000000000000000002999",
        "reviewer_independence_attestation": True,
        "review_decision_reason_code": "trusted_binding_unit_reason",
        "acceptance_criteria_passed": True,
        "trusted_binding_confirmed": True,
        "authorized_return_writer_confirmed": False,
        "binding_authority_current": True,
        "scope_limited_to_stage12521_stage12516_stage12503_flow": True,
        "return_writer_destination_authorized": False,
        "maps_to_343_slot_context": True,
        "slot_context_gap_code": None,
        "no_training_admission_level3_patch_trace_requested": True,
        "raw_private_values_revealed": False,
        "raw_source_output_included": False,
        "raw_paths_included": False,
        "raw_commands_included": False,
        "raw_diffs_included": False,
        "raw_verifier_output_included": False,
        "candidate_file_contents_read_publicly": False,
        "stage12521_readiness_manifest_written": False,
        "stage12516_candidate_row_written": False,
        "stage12503_return_file_written": False,
        "training_allowed": False,
        "admission_allowed": False,
        "level3_atom_materialized": False,
        "patch_trace_materialized": False,
        "blocker_codes": [],
    }


def write_inputs(root: Path) -> list[dict]:
    write_stage12528_fixture(root)
    return write_stage12529_fixture(root)


def test_no_return_file_emits_exact_missing_return_dashboard(tmp_path: Path) -> None:
    stage12530 = load_module(SCRIPT, "stage12530_no_return")
    write_inputs(tmp_path)

    summary = stage12530.build(tmp_path)

    assert summary["decision"] == "blocked_missing_stage12527_private_binding_review_returns_dashboard_emitted"
    assert summary["return_file_present"] is False
    assert summary["return_file_contents_read"] is False
    assert summary["stage12528_validation_required"] is False
    assert summary["stage12529_work_order_item_count"] == 69
    assert summary["stage12529_work_order_shard_count"] == 4
    assert summary["stage12527_private_review_queue_count"] == 69
    assert summary["preserved_slot_count_context"] == 343
    assert summary["missing_return_dashboard_row_count"] == 4
    assert summary["accepted_private_review_status_count"] == 0
    assert summary["ready_review_status_count"] == 0
    assert summary["ready_candidate_count"] == 0
    assert summary["stage12521_readiness_manifest_count"] == 0
    assert summary["stage12516_candidate_row_count"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_rows_emitted"] == 0

    out = tmp_path / "runs/local/artifacts/stage12530_private_binding_review_return_presence_audit"
    dashboard = read_jsonl(out / "private_binding_review_missing_return_dashboard.jsonl")
    assert len(dashboard) == 4
    assert [row["work_order_item_count"] for row in dashboard] == [20, 20, 20, 9]
    assert {row["blocker_code"] for row in dashboard} == {"stage12527_private_binding_review_returns_jsonl_absent"}
    assert all(row["target_return_filename"] == "private_binding_review_returns.jsonl" for row in dashboard)
    assert all(row["return_file_present"] is False for row in dashboard)
    assert all(row["preserved_slot_count_context"] == 343 for row in dashboard)
    assert not (
        tmp_path
        / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract/"
        "private_executor_resolver_readiness_manifest.json"
    ).exists()


def test_temp_valid_return_file_reports_presence_and_points_to_stage12528_without_downstream_outputs(tmp_path: Path) -> None:
    stage12530 = load_module(SCRIPT, "stage12530_return_present")
    items = write_inputs(tmp_path)
    stage12527_out = tmp_path / "runs/local/artifacts/stage12527_private_binding_review_queue"
    write_jsonl(stage12527_out / "private_binding_review_returns.jsonl", [valid_return_for(items[0])])

    summary = stage12530.build(tmp_path)

    assert summary["decision"] == "return_file_present_stage12528_validation_required_no_stage12530_parse"
    assert summary["return_file_present"] is True
    assert summary["return_file_contents_read"] is False
    assert summary["stage12528_validation_required"] is True
    assert summary["stage12528_validation_stage"] == "stage12528_private_binding_review_return_preflight"
    assert summary["next_stage"] == "rerun_stage12528_private_binding_review_return_preflight_for_validation"
    assert summary["stage12529_work_order_item_count"] == 69
    assert summary["stage12529_work_order_shard_count"] == 4
    assert summary["preserved_slot_count_context"] == 343
    assert summary["accepted_private_review_status_count"] == 0
    assert summary["ready_review_status_count"] == 0
    assert summary["ready_candidate_count"] == 0
    assert summary["stage12521_readiness_manifest_count"] == 0
    assert summary["stage12516_candidate_row_count"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["admitted_rows"] == 0

    out = tmp_path / "runs/local/artifacts/stage12530_private_binding_review_return_presence_audit"
    dashboard = read_jsonl(out / "private_binding_review_missing_return_dashboard.jsonl")
    assert len(dashboard) == 4
    assert {row["blocker_code"] for row in dashboard} == {
        "private_binding_review_return_file_present_stage12528_validation_required"
    }
    assert all(row["stage12528_validation_required"] is True for row in dashboard)
    assert not (
        tmp_path
        / "runs/local/artifacts/stage12528_private_binding_review_return_preflight/"
        "accepted_private_binding_review_statuses.jsonl"
    ).exists()
    assert not (
        tmp_path
        / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract/"
        "private_executor_resolver_readiness_manifest.json"
    ).exists()
