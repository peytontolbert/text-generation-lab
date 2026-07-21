import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12528_private_binding_review_return_preflight.py"


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
    return {
        "record_type": "stage12527_public_safe_private_review_queue_item_v1",
        "private_review_packet_id_hash": f"{idx:024x}",
        "priority_rank": idx,
        "priority_score": 8000 - idx,
        "review_band": "p1_trusted_binding_review",
        "candidate_binding_source_id_hash": f"{idx + 100:024x}",
        "candidate_class": candidate_class,
        "candidate_parent_name": "stage_unit_public_safe_parent",
        "candidate_suffix": ".json",
        "preserved_slot_count_context": 343,
        "public_safe_metadata_only": True,
        "candidate_contents_read": False,
        "private_review_required": True,
        "readiness_claimed": False,
    }


def write_stage12527_fixture(root: Path, rows: list[dict]) -> None:
    out = root / "runs/local/artifacts/stage12527_private_binding_review_queue"
    write_json(
        out / "summary.json",
        {
            "record_type": "stage12527_private_binding_review_queue_summary_v1",
            "decision": "public_safe_private_review_queue_emitted_no_readiness_claimed",
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
    write_json(
        out / "review_criteria.json",
        {
            "record_type": "stage12527_private_review_criteria_v1",
            "accept_criteria": ["private_reviewer_confirms_candidate_is_intended_for_trusted_executor_or_return_writer_binding"],
            "reject_criteria": ["candidate_does_not_identify_a_trusted_executor_binding_or_authorized_return_writer_in_private_context"],
            "public_safe_metadata_only": True,
        },
    )


def review_return(row: dict, action: str, idx: int, **overrides) -> dict:
    ready = action in {"trusted_binding", "authorized_return_writer"}
    blocked = action == "blocked"
    value = {
        "record_type": "stage12528_private_binding_review_return_v1",
        "private_review_packet_id_hash": row["private_review_packet_id_hash"],
        "candidate_binding_source_id_hash": row["candidate_binding_source_id_hash"],
        "review_action": action,
        "private_reviewer_id_hash": f"{idx + 500:024x}",
        "reviewer_conflict_check_hash": f"{idx + 700:024x}",
        "reviewer_independence_attestation": True,
        "review_decision_reason_code": f"{action}_unit_reason",
        "acceptance_criteria_passed": ready,
        "trusted_binding_confirmed": action == "trusted_binding",
        "authorized_return_writer_confirmed": action == "authorized_return_writer",
        "binding_authority_current": ready,
        "scope_limited_to_stage12521_stage12516_stage12503_flow": ready,
        "return_writer_destination_authorized": action == "authorized_return_writer",
        "maps_to_343_slot_context": ready,
        "slot_context_gap_code": "private_context_gap_documented" if blocked else None,
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
        "blocker_codes": ["private_review_blocked_unit"] if blocked else [],
    }
    value.update(overrides)
    return value


def test_no_return_file_blocks_all_queue_items_and_writes_no_manifests(tmp_path: Path) -> None:
    stage12528 = load_module(SCRIPT, "stage12528_no_return")
    rows = [queue_item(1), queue_item(2)]
    write_stage12527_fixture(tmp_path, rows)

    summary = stage12528.build(tmp_path)

    assert summary["decision"] == "blocked_no_private_binding_review_return_file"
    assert summary["stage12527_private_review_queue_count"] == 2
    assert summary["return_file_present"] is False
    assert summary["accepted_private_review_status_count"] == 0
    assert summary["ready_review_status_count"] == 0
    assert summary["ready_candidate_count"] == 0
    assert summary["blocked_private_review_queue_item_count"] == 2
    assert summary["preserved_slot_count_context"] == 343
    assert summary["stage12521_readiness_manifests_written"] is False
    assert summary["stage12516_candidate_row_count"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_rows_emitted"] == 0

    out = tmp_path / "runs/local/artifacts/stage12528_private_binding_review_return_preflight"
    assert read_jsonl(out / "accepted_private_binding_review_statuses.jsonl") == []
    blockers = read_jsonl(out / "private_binding_review_return_blockers.jsonl")
    assert len(blockers) == 2
    assert all("private_binding_review_return_absent" in row["blocker_codes"] for row in blockers)
    schema = read_json(out / "private_binding_review_return_schema.json")
    assert schema["required_public_safe_return_fields"] == stage12528.REQUIRED_RETURN_FIELDS
    assert schema["allowed_review_actions"] == ["authorized_return_writer", "blocked", "reject", "trusted_binding"]
    assert not (
        tmp_path
        / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract/"
        "private_executor_resolver_readiness_manifest.json"
    ).exists()


def test_temp_valid_reject_blocked_and_ready_review_returns_validate_without_downstream_outputs(tmp_path: Path) -> None:
    stage12528 = load_module(SCRIPT, "stage12528_valid_returns")
    rows = [
        queue_item(1, "trusted_binding_candidate_name"),
        queue_item(2, "private_executor_config_candidate_name"),
        queue_item(3, "trusted_binding_candidate_name"),
        queue_item(4, "authorized_return_writer_candidate_name"),
    ]
    write_stage12527_fixture(tmp_path, rows)
    stage12527_out = tmp_path / "runs/local/artifacts/stage12527_private_binding_review_queue"
    write_jsonl(
        stage12527_out / "private_binding_review_returns.jsonl",
        [
            review_return(rows[0], "trusted_binding", 1),
            review_return(rows[1], "reject", 2),
            review_return(rows[2], "blocked", 3),
            review_return(rows[3], "authorized_return_writer", 4),
        ],
    )

    summary = stage12528.build(tmp_path)

    assert summary["decision"] == "private_binding_review_returns_validated_status_only_no_manifests"
    assert summary["return_file_present"] is True
    assert summary["return_record_count"] == 4
    assert summary["accepted_private_review_status_count"] == 4
    assert summary["rejected_private_review_return_count"] == 0
    assert summary["blocked_private_review_queue_item_count"] == 0
    assert summary["ready_review_status_count"] == 2
    assert summary["ready_candidate_count"] == 0
    assert summary["accepted_review_action_counts"] == {
        "authorized_return_writer": 1,
        "blocked": 1,
        "reject": 1,
        "trusted_binding": 1,
    }
    assert summary["stage12521_readiness_manifest_count"] == 0
    assert summary["stage12521_readiness_manifests_written"] is False
    assert summary["stage12516_candidate_row_count"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["admitted_rows"] == 0

    out = tmp_path / "runs/local/artifacts/stage12528_private_binding_review_return_preflight"
    accepted = read_jsonl(out / "accepted_private_binding_review_statuses.jsonl")
    assert len(accepted) == 4
    assert {row["public_safe_status"] for row in accepted} == {"ready_review", "reject", "blocked"}
    assert read_jsonl(out / "rejected_private_binding_review_returns.jsonl") == []
    assert read_jsonl(out / "private_binding_review_return_blockers.jsonl") == []
    assert not (
        tmp_path
        / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract/"
        "private_executor_resolver_readiness_manifest.json"
    ).exists()
    assert not (
        tmp_path
        / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/"
        "private_causal_evidence_return_candidates.jsonl"
    ).exists()
