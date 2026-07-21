import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12523_private_executor_return_fixture_contract.py"


def load_stage12523():
    spec = importlib.util.spec_from_file_location("stage12523", SCRIPT)
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


def _slot_ref(stage12523, idx: int, slot: str) -> dict:
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
        "target_return_record_type": stage12523.RETURN_RECORD_TYPE,
        "public_safe_status_only": True,
    }


def _stage12521_and_12522_fixture(root: Path, stage12523) -> list[dict]:
    slot_refs = [_slot_ref(stage12523, idx + 1, slot) for idx, slot in enumerate(stage12523.FULL_SEVEN_SLOTS)]
    stage12521_out = root / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract"
    stage12522_out = root / "runs/local/artifacts/stage12522_private_causal_evidence_executor_return_adapter"
    _write_jsonl(
        stage12521_out / "private_causal_evidence_executor_handoff_shards.jsonl",
        [
            {
                "record_type": "stage12521_private_causal_evidence_executor_handoff_shard_v1",
                "executor_handoff_shard_id_hash": "789abc123def789abc123def",
                "priority_rank": 1,
                "evidence_slot": "mixed_unit_slots",
                "slot_ref_count": len(slot_refs),
                "slot_refs": slot_refs,
                "public_safe_status_only": True,
            }
        ],
    )
    blockers = []
    for idx, slot_ref in enumerate(slot_refs, start=1):
        blockers.append(
            {
                "record_type": "stage12522_private_causal_evidence_executor_return_blocker_v1",
                "blocker_id_hash": _hash("f", idx),
                **{field: slot_ref[field] for field in ["acquisition_work_order_id_hash", *stage12523.IDENTITY_FIELDS]},
                "blocker_codes": [
                    "private_executor_return_absent",
                    "stage12516_candidate_return_required_before_stage12516_validation",
                    "downstream_stage12516_then_stage12519_required",
                ],
                "public_safe_status_only": True,
            }
        )
    _write_jsonl(stage12522_out / "private_causal_evidence_executor_return_blockers.jsonl", blockers)
    _write_json(
        stage12522_out / "summary.json",
        {
            "executor_return_file_present": False,
            "candidate_output_written": False,
            "candidate_output_row_count": 0,
        },
    )
    return slot_refs


def test_tmp_builds_fixture_contract_from_stage12522_blockers_without_candidate_rows(tmp_path: Path) -> None:
    stage12523 = load_stage12523()
    _stage12521_and_12522_fixture(tmp_path, stage12523)

    summary = stage12523.build(tmp_path)

    assert summary["decision"] == "private_executor_return_fixture_contract_and_runbook_written_no_candidate_rows"
    assert summary["contract_slot_count"] == 7
    assert summary["preserved_slot_identity_count"] == 7
    assert summary["dedupe_dropped_slot_count"] == 0
    assert summary["full_seven_slot_set_seen"] is True
    assert summary["stage12522_executor_return_file_present"] is False
    assert summary["candidate_output_written"] is False
    assert summary["stage12516_candidate_rows_written"] is False
    assert summary["stage12516_candidate_row_count"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_rows_emitted"] == 0
    assert summary["admission_allowed"] is False
    target = (
        tmp_path
        / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/private_causal_evidence_return_candidates.jsonl"
    )
    assert not target.exists()

    out = tmp_path / "runs/local/artifacts/stage12523_private_executor_return_fixture_contract"
    rows = _read_jsonl(out / "private_executor_return_fixture_contract_slots.jsonl")
    runbook = _read_json(out / "private_executor_return_acquisition_runbook.json")
    assert len(rows) == 7
    assert runbook["executor_return_rows_must_match_contract_slots"] == 7
    assert runbook["production_fixture_generator_allowed"] is False
    assert all(row["executor_must_return"]["required_fields_in_exact_stage12516_order"] == stage12523.REQUIRED_STAGE12516_RETURN_FIELDS for row in rows)
    assert all(row["blocker_status_is_acquisition_reason_not_proof"] is True for row in rows)
    assert len({(row["acquisition_work_order_id_hash"], row["evidence_slot"]) for row in rows}) == 7
    assert len({row["root_or_window_hash"] for row in rows}) == 1


def test_tmp_contract_never_treats_validated_present_or_blocked_unavailable_as_fabricated_proof(tmp_path: Path) -> None:
    stage12523 = load_stage12523()
    _stage12521_and_12522_fixture(tmp_path, stage12523)

    summary = stage12523.build(tmp_path)

    out = tmp_path / "runs/local/artifacts/stage12523_private_executor_return_fixture_contract"
    rows = _read_jsonl(out / "private_executor_return_fixture_contract_slots.jsonl")
    runbook = _read_json(out / "private_executor_return_acquisition_runbook.json")
    assert summary["validated_present_fabricated"] is False
    assert summary["blocked_unavailable_fabricated"] is False
    assert summary["blocked_unavailable_treated_as_proof"] is False
    assert summary["status_hash_as_proof_allowed"] is False
    assert runbook["validated_present_gate"] == "validated_present_requires_real_private_executor_return_row"
    assert runbook["blocked_unavailable_gate"] == "blocked_unavailable_is_a_blocker_or_executor_status_not_proof"
    assert all(row["validated_present_fabricated"] is False for row in rows)
    assert all(row["blocked_unavailable_fabricated"] is False for row in rows)
    assert all(row["blocked_unavailable_treated_as_proof"] is False for row in rows)
    assert all(row["executor_must_return"]["non_present_statuses_are_not_proof"] is True for row in rows)


def test_slot_accounting_rejects_blocker_slot_drop_or_dedupe(tmp_path: Path) -> None:
    stage12523 = load_stage12523()
    _stage12521_and_12522_fixture(tmp_path, stage12523)
    blocker_path = (
        tmp_path
        / "runs/local/artifacts/stage12522_private_causal_evidence_executor_return_adapter/private_causal_evidence_executor_return_blockers.jsonl"
    )
    blockers = _read_jsonl(blocker_path)
    _write_jsonl(blocker_path, blockers[:-1])

    with pytest.raises(stage12523.SlotAccountingError):
        stage12523.build(tmp_path)


def test_test_only_fixture_templates_are_temp_root_only_and_not_adapter_consumable(tmp_path: Path) -> None:
    stage12523 = load_stage12523()
    _stage12521_and_12522_fixture(tmp_path, stage12523)
    stage12523.build(tmp_path)

    template_path = stage12523.generate_test_only_fixture_templates(tmp_path)

    templates = _read_jsonl(template_path)
    assert len(templates) == 7
    assert all(row["record_type"] == "stage12523_test_only_private_executor_return_template_v1" for row in templates)
    assert all(row["not_a_stage12516_candidate_return"] is True for row in templates)
    assert all(row["not_adapter_consumable"] is True for row in templates)
    assert all(row["placeholder_status"] == "private_executor_must_choose_after_real_private_review" for row in templates)
    assert all("independent_slot_status" not in row for row in templates)

    with pytest.raises(stage12523.ProductionFixtureGenerationError):
        stage12523.generate_test_only_fixture_templates(stage12523.ROOT)
