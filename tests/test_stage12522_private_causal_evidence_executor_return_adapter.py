import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12522_private_causal_evidence_executor_return_adapter.py"
STAGE12516_SCRIPT = ROOT / "scripts/build_stage12516_private_causal_evidence_return_preflight.py"


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_stage12522():
    return load_script(SCRIPT, "stage12522")


def load_stage12516():
    return load_script(STAGE12516_SCRIPT, "stage12516_for_12522")


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _hash(prefix: str, idx: int) -> str:
    return f"{prefix}{idx:023x}"[-24:]


def _slot_ref(idx: int, slot: str) -> dict:
    return {
        "expanded_slot_id_hash": _hash("e", idx),
        "revalidation_id_hash": "abc123def456abc123def456",
        "request_id_hash": "123abc456def123abc456def",
        "work_item_id_hash": "234abc456def123abc456def",
        "packet_id_hash": "345abc456def123abc456def",
        "root_or_window_hash": "456abc123def456abc123def",
        "missing_evidence_worklist_id_hash": _hash("m", idx),
        "semantic_sufficiency_blocker_id_hash": _hash("b", idx),
        "semantic_matrix_row_id_hash": _hash("c", idx),
        "acquisition_work_order_id_hash": _hash("a", idx),
        "source_stage": "stage_unit_safe_source",
        "source_kind": "selected_test_bounded_transition_support",
        "language_family": "python",
        "task_family": "transition_next_action",
        "evidence_slot": slot,
        "proof_class": f"proof_class_{idx}",
        "current_independent_slot_status": "blocked_unavailable",
        "blocker_codes": ["status_non_proof_blocked_unavailable"],
        "target_return_record_type": "stage12516_private_causal_evidence_return_candidate_v1",
        "public_safe_status_only": True,
    }


def _stage12521_fixture(root: Path, stage12522) -> list[dict]:
    slot_refs = [_slot_ref(idx + 1, slot) for idx, slot in enumerate(stage12522.FULL_SEVEN_SLOTS)]
    out = root / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract"
    _write_jsonl(
        out / "private_causal_evidence_executor_handoff_shards.jsonl",
        [
            {
                "record_type": "stage12521_private_causal_evidence_executor_handoff_shard_v1",
                "executor_handoff_shard_id_hash": "789abc123def789abc123def",
                "source_stage": "stage12520_private_causal_evidence_acquisition_batch_planner",
                "priority_rank": 1,
                "evidence_slot": "mixed_unit_slots",
                "slot_ref_count": len(slot_refs),
                "slot_refs": slot_refs,
                "downstream_validation_required": "stage12516_schema_validation_then_stage12519_semantic_sufficiency_required",
                "public_safe_status_only": True,
            }
        ],
    )
    _write_json(
        out / "private_causal_evidence_executor_handoff_contract.json",
        {
            "record_type": "stage12521_private_causal_evidence_executor_handoff_contract_v1",
            "target_future_return_record_type": "stage12516_private_causal_evidence_return_candidate_v1",
            "semantic_sufficiency_gate": "downstream_stage12519_semantic_sufficiency_required_after_stage12516_validation",
        },
    )
    return slot_refs


def _stage12515_work_orders(root: Path, slot_refs: list[dict]) -> None:
    work_orders = []
    for slot_ref in slot_refs:
        work_orders.append(
            {
                "record_type": "stage12515_private_causal_evidence_acquisition_work_order_v1",
                **{field: slot_ref[field] for field in ["acquisition_work_order_id_hash", *load_stage12522().IDENTITY_FIELDS]},
                "acceptable_return_statuses": ["validated_present", "validated_absent", "blocked_unavailable", "not_applicable"],
            }
        )
    _write_jsonl(
        root
        / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/private_causal_evidence_acquisition_work_orders.jsonl",
        work_orders,
    )


def _valid_executor_return(slot_ref: dict, idx: int) -> dict:
    return {
        "record_type": "stage12522_private_causal_evidence_executor_return_v1",
        "acquisition_work_order_id_hash": slot_ref["acquisition_work_order_id_hash"],
        "revalidation_id_hash": slot_ref["revalidation_id_hash"],
        "request_id_hash": slot_ref["request_id_hash"],
        "work_item_id_hash": slot_ref["work_item_id_hash"],
        "packet_id_hash": slot_ref["packet_id_hash"],
        "root_or_window_hash": slot_ref["root_or_window_hash"],
        "source_stage": slot_ref["source_stage"],
        "source_kind": slot_ref["source_kind"],
        "language_family": slot_ref["language_family"],
        "task_family": slot_ref["task_family"],
        "evidence_slot": slot_ref["evidence_slot"],
        "proof_class": slot_ref["proof_class"],
        "private_reviewer_id_hash": _hash("1", idx),
        "reviewer_conflict_check_hash": _hash("2", idx),
        "reviewer_independence_attestation": True,
        "independent_slot_status": "validated_present",
        "independent_evidence_digest_hash": _hash("3", idx),
        "slot_status_reason_code": "independent_digest_supplied",
        "causal_review_digest_hash": _hash("4", idx),
        "raw_private_values_revealed": False,
        "raw_source_output_included": False,
        "raw_paths_included": False,
        "raw_commands_included": False,
        "raw_diffs_included": False,
        "raw_verifier_output_included": False,
        "local_model_authority": False,
        "policy_label_emitted": False,
        "proof_or_admission_requested": False,
        "acceptance_criteria_passed": True,
        "observed_action_available_to_labeler": False,
        "observed_action_used_as_label": False,
        "candidate_action_set_blinded": True,
        "label_leak_attestation": True,
        "model_facing_gold_fields_excluded": True,
        "pass_to_pass_repair_credit_requested": False,
        "repair_credit_requires_before_fail_after_pass_same_verifier": True,
        "blocker_codes": [],
        "training_allowed": False,
        "admission_allowed": False,
        "stage12503_return_file_written": False,
        "stage12503_return_records_written": 0,
    }


def test_tmp_no_executor_return_file_blocks_without_writing_stage12516_candidates(tmp_path: Path) -> None:
    stage12522 = load_stage12522()
    _stage12521_fixture(tmp_path, stage12522)

    summary = stage12522.build(tmp_path)

    target = (
        tmp_path
        / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/private_causal_evidence_return_candidates.jsonl"
    )
    assert summary["decision"] == "blocked_no_stage12516_candidate_rows_from_private_executor_returns"
    assert summary["input_handoff_shard_count"] == 1
    assert summary["expected_slot_ref_count"] == 7
    assert summary["executor_return_file_present"] is False
    assert summary["candidate_output_written"] is False
    assert summary["candidate_output_row_count"] == 0
    assert summary["missing_slot_return_count"] == 7
    assert summary["blocked_slot_count"] == 7
    assert summary["target_stage12516_candidate_output_ref"].endswith("private_causal_evidence_return_candidates.jsonl")
    assert summary["validated_present_fabricated"] is False
    assert summary["dedupe_dropped_slot_count"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_rows_emitted"] == 0
    assert not target.exists()

    out = tmp_path / "runs/local/artifacts/stage12522_private_causal_evidence_executor_return_adapter"
    blockers = _read_jsonl(out / "private_causal_evidence_executor_return_blockers.jsonl")
    assert len(blockers) == 7
    assert all("private_executor_return_absent" in row["blocker_codes"] for row in blockers)


def test_tmp_valid_executor_returns_write_stage12516_consumable_candidates(tmp_path: Path) -> None:
    stage12522 = load_stage12522()
    stage12516 = load_stage12516()
    slot_refs = _stage12521_fixture(tmp_path, stage12522)
    _stage12515_work_orders(tmp_path, slot_refs)
    executor_returns = [_valid_executor_return(slot_ref, idx + 1) for idx, slot_ref in enumerate(slot_refs)]
    _write_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract/private_causal_evidence_executor_returns.jsonl",
        executor_returns,
    )

    summary = stage12522.build(tmp_path)

    target = (
        tmp_path
        / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/private_causal_evidence_return_candidates.jsonl"
    )
    candidates = _read_jsonl(target)
    assert summary["decision"] == "private_executor_returns_adapted_to_stage12516_candidate_rows"
    assert summary["executor_return_file_present"] is True
    assert summary["executor_return_record_count"] == 7
    assert summary["executed_slot_return_count"] == 7
    assert summary["accepted_stage12516_candidate_count"] == 7
    assert summary["candidate_output_written"] is True
    assert summary["candidate_output_path"].endswith("private_causal_evidence_return_candidates.jsonl")
    assert len(candidates) == 7
    assert all(row["record_type"] == "stage12516_private_causal_evidence_return_candidate_v1" for row in candidates)
    assert len({(row["acquisition_work_order_id_hash"], row["evidence_slot"]) for row in candidates}) == 7
    assert len({row["root_or_window_hash"] for row in candidates}) == 1
    assert summary["dedupe_dropped_slot_count"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_rows_emitted"] == 0

    stage12516_summary = stage12516.build(tmp_path)
    assert stage12516_summary["validated_private_causal_evidence_return_count"] == 7
    assert stage12516_summary["rejected_private_causal_evidence_return_count"] == 0
    assert stage12516_summary["blocked_work_order_count"] == 0
    assert stage12516_summary["complete_revalidation_record_count"] == 1
    assert stage12516_summary["stage12503_return_records_written"] == 0
    assert stage12516_summary["training_rows_emitted"] == 0

    adapter_summary = _read_json(
        tmp_path / "runs/local/artifacts/stage12522_private_causal_evidence_executor_return_adapter/summary.json"
    )
    assert adapter_summary["semantic_sufficiency_gate"] == (
        "downstream_stage12516_validation_then_stage12519_semantic_sufficiency_required"
    )
