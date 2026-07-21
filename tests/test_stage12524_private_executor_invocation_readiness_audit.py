import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12524_private_executor_invocation_readiness_audit.py"


def load_stage12524():
    spec = importlib.util.spec_from_file_location("stage12524", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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


def _slot_ref(stage12524, idx: int, slot: str) -> dict:
    return {
        "expanded_slot_id_hash": _hash("e", idx),
        "revalidation_id_hash": "abc123def456abc123def456",
        "request_id_hash": "123abc456def123abc456def",
        "work_item_id_hash": "234abc456def123abc456def",
        "packet_id_hash": "345abc456def123abc456def",
        "root_or_window_hash": "456abc123def456abc123def",
        "acquisition_work_order_id_hash": _hash("a", idx),
        "source_stage": "stage_unit_safe_source",
        "source_kind": "selected_test_bounded_transition_support",
        "language_family": "python",
        "task_family": "transition_next_action",
        "evidence_slot": slot,
        "proof_class": f"proof_class_{idx}",
        "public_safe_status_only": True,
    }


def _write_stage12521_and_stage12523_fixture(root: Path, stage12524) -> list[dict]:
    slot_refs = [_slot_ref(stage12524, idx + 1, slot) for idx, slot in enumerate(stage12524.FULL_SEVEN_SLOTS)]
    stage12521_out = root / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract"
    stage12523_out = root / "runs/local/artifacts/stage12523_private_executor_return_fixture_contract"
    _write_jsonl(
        stage12521_out / "private_causal_evidence_executor_handoff_shards.jsonl",
        [
            {
                "record_type": "stage12521_private_causal_evidence_executor_handoff_shard_v1",
                "executor_handoff_shard_id_hash": "789abc123def789abc123def",
                "priority_rank": 1,
                "language_family": "python",
                "task_family": "transition_next_action",
                "source_stage_name": "stage_unit_safe_source",
                "evidence_slot": "mixed_unit_slots",
                "slot_ref_count": len(slot_refs),
                "slot_refs": slot_refs,
                "public_safe_status_only": True,
            }
        ],
    )
    _write_jsonl(
        stage12523_out / "private_executor_return_fixture_contract_slots.jsonl",
        [
            {
                "record_type": "stage12523_private_executor_return_fixture_contract_slot_v1",
                "fixture_contract_slot_id_hash": _hash("f", idx),
                **slot_ref,
                "executor_return_filename_contract": "private_causal_evidence_executor_returns.jsonl",
                "public_safe_status_only": True,
            }
            for idx, slot_ref in enumerate(slot_refs, start=1)
        ],
    )
    _write_json(
        stage12523_out / "private_executor_return_acquisition_runbook.json",
        {
            "record_type": "stage12523_private_executor_return_acquisition_runbook_v1",
            "executor_return_file_must_be_placed_under_stage12521": "private_causal_evidence_executor_returns.jsonl",
            "executor_return_rows_must_match_contract_slots": len(slot_refs),
            "adapter_to_run_after_real_returns": "stage12522_private_causal_evidence_executor_return_adapter",
            "stage12516_candidate_output_ref_after_adapter_only": (
                "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/"
                "private_causal_evidence_return_candidates.jsonl"
            ),
            "public_safe_status_only": True,
        },
    )
    return slot_refs


def _write_ready_manifests(root: Path, stage12524, slot_count: int) -> None:
    stage12521_out = root / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract"
    _write_json(
        stage12521_out / stage12524.RESOLVER_MANIFEST,
        {
            "record_type": "stage12524_private_executor_resolver_readiness_manifest_v1",
            "readiness_manifest_id_hash": "111abc222def333abc444def",
            "private_resolver_ready": True,
            "private_locator_inputs_available": True,
            "resolver_slot_count": slot_count,
            "public_safe_status_only": True,
        },
    )
    _write_json(
        stage12521_out / stage12524.EXECUTOR_MANIFEST,
        {
            "record_type": "stage12524_private_executor_runtime_readiness_manifest_v1",
            "readiness_manifest_id_hash": "555abc666def777abc888def",
            "private_executor_ready": True,
            "supports_stage12516_return_schema": True,
            "executor_slot_count": slot_count,
            "expected_executor_return_filename": "private_causal_evidence_executor_returns.jsonl",
            "public_safe_status_only": True,
        },
    )


def test_missing_private_executor_inputs_emit_exact_blockers_and_zero_returns(tmp_path: Path) -> None:
    stage12524 = load_stage12524()
    _write_stage12521_and_stage12523_fixture(tmp_path, stage12524)

    summary = stage12524.build(tmp_path)

    assert summary["decision"] == "blocked_missing_private_executor_inputs_zero_returns"
    assert summary["executor_invocation_ready"] is False
    assert summary["readiness_blocker_codes"] == [
        "private_executor_manifest_missing",
        "private_resolver_manifest_missing",
    ]
    assert summary["readiness_blocker_row_count"] == 7
    assert summary["executor_return_records_written"] == 0
    assert summary["stage12516_candidate_row_count"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_rows_emitted"] == 0
    assert summary["preserved_slot_identity_count"] == 7
    assert summary["dedupe_dropped_slot_count"] == 0

    out = tmp_path / "runs/local/artifacts/stage12524_private_executor_invocation_readiness_audit"
    blockers = _read_jsonl(out / "private_executor_invocation_readiness_blockers.jsonl")
    plan = _read_json(out / "private_executor_invocation_readiness_plan.json")
    assert len(blockers) == 7
    assert plan == {}
    assert all(row["blocker_codes"] == summary["readiness_blocker_codes"] for row in blockers)
    assert len({row["root_or_window_hash"] for row in blockers}) == 1


def test_temp_root_ready_fixture_writes_invocation_plan_not_returns(tmp_path: Path) -> None:
    stage12524 = load_stage12524()
    slot_refs = _write_stage12521_and_stage12523_fixture(tmp_path, stage12524)
    _write_ready_manifests(tmp_path, stage12524, len(slot_refs))

    summary = stage12524.build(tmp_path)

    assert summary["decision"] == "ready_public_safe_executor_invocation_plan_written_no_returns"
    assert summary["executor_invocation_ready"] is True
    assert summary["readiness_blocker_codes"] == []
    assert summary["readiness_blocker_row_count"] == 0
    assert summary["expected_stage12521_return_row_count"] == 7
    assert summary["executor_return_records_written"] == 0
    assert summary["stage12516_candidate_row_count"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["preserved_slot_identity_count"] == 7
    assert summary["dedupe_dropped_slot_count"] == 0

    out = tmp_path / "runs/local/artifacts/stage12524_private_executor_invocation_readiness_audit"
    blockers = _read_jsonl(out / "private_executor_invocation_readiness_blockers.jsonl")
    plan = _read_json(out / "private_executor_invocation_readiness_plan.json")
    assert blockers == []
    assert plan["executor_return_filename_expected_under_stage12521"] == "private_causal_evidence_executor_returns.jsonl"
    assert (
        plan["executor_return_file_ref_for_future_stage12522_adapter"]
        == "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract/private_causal_evidence_executor_returns.jsonl"
    )
    assert plan["expected_stage12521_return_row_count"] == 7
    assert plan["executor_return_records_written"] == 0
    assert plan["stage12516_candidate_row_count"] == 0
    assert plan["invocation_boundary"] == "plan_only_private_executor_not_invoked_by_stage12524"
