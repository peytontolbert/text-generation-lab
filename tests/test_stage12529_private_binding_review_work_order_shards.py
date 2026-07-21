import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12529_private_binding_review_work_order_shards.py"


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


def queue_item(idx: int, candidate_class: str = "trusted_binding_candidate_name") -> dict:
    band = "p0_authorized_writer_binding_review" if candidate_class == "authorized_return_writer_candidate_name" else "p1_trusted_binding_review"
    return {
        "record_type": "stage12527_public_safe_private_review_queue_item_v1",
        "private_review_packet_id_hash": f"{idx:024x}",
        "priority_rank": idx,
        "priority_score": 9000 - idx,
        "review_band": band,
        "candidate_binding_source_id_hash": f"{idx + 1000:024x}",
        "candidate_class": candidate_class,
        "candidate_parent_name": f"stage_unit_public_safe_parent_{idx % 3}",
        "candidate_suffix": ".json",
        "preserved_slot_count_context": 343,
        "public_safe_metadata_only": True,
        "candidate_contents_read": False,
        "private_review_required": True,
        "readiness_claimed": False,
        "stage12521_readiness_manifest_count": 0,
        "stage12516_candidate_row_count": 0,
        "stage12503_return_records_written": 0,
        "training_rows_emitted": 0,
        "admitted_rows": 0,
        "executor_return_records_written": 0,
    }


def blocker_for(row: dict) -> dict:
    return {
        "record_type": "stage12528_private_binding_review_return_blocker_v1",
        "blocker_id_hash": f"{int(row['priority_rank']) + 2000:024x}",
        "private_review_packet_id_hash": row["private_review_packet_id_hash"],
        "candidate_binding_source_id_hash": row["candidate_binding_source_id_hash"],
        "candidate_class": row["candidate_class"],
        "review_band": row["review_band"],
        "preserved_slot_count_context": 343,
        "blocker_codes": [
            "private_binding_review_return_absent",
            "private_reviewer_return_required_before_stage12521_readiness",
            "stage12528_writes_status_only_no_stage12521_manifest",
        ],
        "required_return_schema_ref": "private_binding_review_return_schema.json",
        "public_safe_status_only": True,
        "stage12521_readiness_manifest_count": 0,
        "stage12516_candidate_row_count": 0,
        "stage12503_return_records_written": 0,
        "training_rows_emitted": 0,
        "admitted_rows": 0,
        "executor_return_records_written": 0,
    }


def write_stage12527_fixture(root: Path, rows: list[dict]) -> None:
    out = root / "runs/local/artifacts/stage12527_private_binding_review_queue"
    write_json(
        out / "summary.json",
        {
            "record_type": "stage12527_private_binding_review_queue_summary_v1",
            "decision": "public_safe_private_review_queue_emitted_no_readiness_claimed" if rows else "blocked",
            "private_review_queue_count": len(rows),
            "preserved_slot_count_context": 343,
            "stage12521_readiness_manifests_written": False,
            "stage12516_candidate_row_count": 0,
            "stage12503_return_records_written": 0,
            "training_rows_emitted": 0,
            "admitted_rows": 0,
        },
    )
    write_jsonl(out / "private_review_queue.jsonl", rows)


def write_stage12528_fixture(root: Path, blockers: list[dict]) -> None:
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
            "stage12527_private_review_queue_count": len(blockers),
            "preserved_slot_count_context": 343,
            "return_file_present": False,
            "blocked_private_review_queue_item_count": len(blockers),
            "ready_candidate_count": 0,
            "stage12521_readiness_manifests_written": False,
            "stage12516_candidate_row_count": 0,
            "stage12503_return_records_written": 0,
            "training_rows_emitted": 0,
            "admitted_rows": 0,
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
            "global_must_be_true_fields": ["reviewer_independence_attestation", "no_training_admission_level3_patch_trace_requested"],
            "global_must_be_false_fields": ["raw_private_values_revealed", "raw_source_output_included"],
            "public_safe_metadata_only": True,
        },
    )
    write_jsonl(out / "private_binding_review_return_blockers.jsonl", blockers)


def test_no_queue_and_no_blockers_produces_blocked_work_order_inputs(tmp_path: Path) -> None:
    stage12529 = load_module(SCRIPT, "stage12529_blocked")
    write_stage12527_fixture(tmp_path, [])
    write_stage12528_fixture(tmp_path, [])

    summary = stage12529.build(tmp_path)

    assert summary["decision"] == "blocked_missing_stage12527_queue_or_stage12528_blockers"
    assert summary["stage12527_private_review_queue_count"] == 0
    assert summary["stage12528_return_blocker_count"] == 0
    assert summary["work_order_item_count"] == 0
    assert summary["work_order_shard_count"] == 0
    assert summary["preserved_slot_count_context"] == 343
    assert summary["readiness_claimed"] is False
    assert summary["stage12521_readiness_manifest_count"] == 0
    assert summary["stage12516_candidate_row_count"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_rows_emitted"] == 0

    out = tmp_path / "runs/local/artifacts/stage12529_private_binding_review_work_order_shards"
    assert read_jsonl(out / "private_binding_review_work_order_items.jsonl") == []
    assert read_jsonl(out / "private_binding_review_work_order_shards.jsonl") == []
    blockers = read_jsonl(out / "private_binding_review_work_order_blockers.jsonl")
    assert {row["blocker_code"] for row in blockers} == {
        "stage12527_private_review_queue_absent",
        "stage12528_private_binding_review_return_blockers_absent",
    }


def test_current_like_queue_creates_public_safe_shards_without_readiness(tmp_path: Path) -> None:
    stage12529 = load_module(SCRIPT, "stage12529_current_like")
    rows = [
        queue_item(idx, "authorized_return_writer_candidate_name" if idx % 17 == 0 else "trusted_binding_candidate_name")
        for idx in range(1, 70)
    ]
    write_stage12527_fixture(tmp_path, rows)
    write_stage12528_fixture(tmp_path, [blocker_for(row) for row in rows])

    summary = stage12529.build(tmp_path)

    assert summary["decision"] == "private_reviewer_work_order_shards_emitted_no_readiness_claimed"
    assert summary["stage12527_private_review_queue_count"] == 69
    assert summary["stage12528_return_blocker_count"] == 69
    assert summary["work_order_item_count"] == 69
    assert summary["work_order_shard_count"] == 4
    assert summary["preserved_slot_count_context"] == 343
    assert summary["target_return_stage"] == "stage12527_private_binding_review_queue"
    assert summary["target_return_filename"] == "private_binding_review_returns.jsonl"
    assert "review_action" in summary["required_public_safe_return_fields"]
    assert summary["allowed_review_actions"] == ["authorized_return_writer", "blocked", "reject", "trusted_binding"]
    assert summary["readiness_claimed"] is False
    assert summary["stage12521_readiness_manifest_count"] == 0
    assert summary["stage12516_candidate_row_count"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["admitted_rows"] == 0

    out = tmp_path / "runs/local/artifacts/stage12529_private_binding_review_work_order_shards"
    items = read_jsonl(out / "private_binding_review_work_order_items.jsonl")
    shards = read_jsonl(out / "private_binding_review_work_order_shards.jsonl")
    assert len(items) == 69
    assert len(shards) == 4
    assert sum(row["work_order_item_count"] for row in shards) == 69
    assert {item["candidate_binding_source_id_hash"] for item in items} == {
        row["candidate_binding_source_id_hash"] for row in rows
    }
    assert all(item["preserved_slot_count_context"] == 343 for item in items)
    assert all(item["target_return_filename"] == "private_binding_review_returns.jsonl" for item in items)
    assert all(item["candidate_contents_read"] is False for item in items)
    assert all(item["readiness_claimed"] is False for item in items)
    assert all(item["stage12521_readiness_manifest_count"] == 0 for item in items)
    assert all(item["stage12516_candidate_row_count"] == 0 for item in items)
    assert all(item["stage12503_return_records_written"] == 0 for item in items)
    assert all("candidate_name" not in item for item in items)
    assert read_jsonl(out / "private_binding_review_work_order_blockers.jsonl") == []
    assert not (
        tmp_path
        / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract/"
        "private_executor_resolver_readiness_manifest.json"
    ).exists()
