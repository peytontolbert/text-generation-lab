import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12521_private_causal_evidence_executor_handoff_contract.py"
STAGE12520_SCRIPT = ROOT / "scripts/build_stage12520_private_causal_evidence_acquisition_batch_planner.py"


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_stage12521():
    return load_script(SCRIPT, "stage12521")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _identity(idx: int, *, language: str = "python", task: str = "transition_next_action", source_stage: str = "stage_unit_safe") -> dict:
    return {
        "revalidation_id_hash": f"r{idx:023x}"[-24:],
        "request_id_hash": f"q{idx:023x}"[-24:],
        "work_item_id_hash": f"w{idx:023x}"[-24:],
        "packet_id_hash": f"p{idx:023x}"[-24:],
        "root_or_window_hash": "same_root_context_hash",
        "source_stage": source_stage,
        "source_kind": "selected_test_bounded_transition_support",
        "language_family": language,
        "task_family": task,
    }


def _stage12519_rows(root: Path, identities: list[dict]) -> None:
    stage12520 = load_script(STAGE12520_SCRIPT, "stage12520_for_12521")
    worklist_rows = []
    blocker_rows = []
    matrix_rows = []
    for rec_idx, identity in enumerate(identities):
        slot_refs = []
        blocker_counts = {}
        for slot_idx, slot in enumerate(stage12520.FULL_SEVEN_SLOTS):
            work_order_id = f"a{rec_idx:03x}{slot_idx:020x}"[-24:]
            matrix_id = f"m{rec_idx:03x}{slot_idx:020x}"[-24:]
            blocker_counts["status_non_proof_blocked_unavailable"] = blocker_counts.get("status_non_proof_blocked_unavailable", 0) + 1
            slot_refs.append(
                {
                    "acquisition_work_order_id_hash": work_order_id,
                    "evidence_slot": slot,
                    "proof_class": f"proof_class_{slot_idx}",
                    "current_independent_slot_status": "blocked_unavailable",
                    "blocker_codes": ["status_non_proof_blocked_unavailable"],
                    "needed_evidence": "independent_semantic_evidence_or_explicit_no_patch_no_stop_semantics_status_only",
                }
            )
            matrix_rows.append(
                {
                    "record_type": "stage12519_private_causal_evidence_slot_semantic_matrix_row_v1",
                    "semantic_matrix_row_id_hash": matrix_id,
                    **identity,
                    "acquisition_work_order_id_hash": work_order_id,
                    "evidence_slot": slot,
                    "proof_class": f"proof_class_{slot_idx}",
                    "independent_slot_status": "blocked_unavailable",
                    "semantic_sufficient": False,
                    "semantic_sufficiency_reason": "blocked_unavailable_is_non_proof",
                    "blocker_codes": ["status_non_proof_blocked_unavailable"],
                    "status_hash_as_proof_allowed": False,
                    "digest_hash_as_proof_allowed": False,
                    "observed_action_imitation_allowed": False,
                    "pass_to_pass_repair_credit_allowed": False,
                    "public_safe_status_only": True,
                }
            )
        worklist_rows.append(
            {
                "record_type": "stage12519_missing_private_causal_evidence_worklist_v1",
                "missing_evidence_worklist_id_hash": f"l{rec_idx:023x}"[-24:],
                **identity,
                "slot_count": len(slot_refs),
                "slot_refs": slot_refs,
                "candidate_output_written_by_stage12519": False,
                "validated_returns_written_by_stage12519": False,
                "stage12503_returns_written_by_stage12519": False,
                "public_safe_status_only": True,
            }
        )
        blocker_rows.append(
            {
                "record_type": "stage12519_private_causal_evidence_semantic_sufficiency_blocker_v1",
                "semantic_sufficiency_blocker_id_hash": f"b{rec_idx:023x}"[-24:],
                **identity,
                "decision": "blocked_private_causal_evidence_semantically_insufficient",
                "semantic_sufficient_slot_count": 0,
                "required_slot_count": 7,
                "missing_or_insufficient_slots": list(stage12520.FULL_SEVEN_SLOTS),
                "blocker_code_counts": blocker_counts,
                "status_hash_as_proof_gate": "status_and_digest_hashes_are_never_proof",
                "observed_action_imitation_gate": "observed_action_available_to_labeler_false_and_observed_action_used_as_label_false_required",
                "pass_to_pass_gate": "pass_to_pass_support_only_no_repair_credit",
                "full_seven_slot_gate": "all_seven_slots_required_and_semantic_sufficiency_required",
                "public_safe_status_only": True,
            }
        )
    out = root / "runs/local/artifacts/stage12519_private_causal_evidence_semantic_sufficiency_gate"
    _write_jsonl(out / "missing_private_causal_evidence_worklist.jsonl", worklist_rows)
    _write_jsonl(out / "private_causal_evidence_semantic_sufficiency_blockers.jsonl", blocker_rows)
    _write_jsonl(out / "private_causal_evidence_semantic_sufficiency_matrix.jsonl", matrix_rows)


def _build_stage12520(root: Path) -> None:
    stage12520 = load_script(STAGE12520_SCRIPT, "stage12520_builder_for_12521")
    stage12520.build(root)


def test_tmp_emits_handoff_shards_without_dropping_slot_refs_or_writing_returns(tmp_path: Path) -> None:
    stage12521 = load_stage12521()
    _stage12519_rows(tmp_path, [_identity(1), _identity(2)])
    _build_stage12520(tmp_path)

    summary = stage12521.build(tmp_path)

    assert summary["input_expanded_slot_count"] == 14
    assert summary["handoff_slot_ref_count"] == 14
    assert summary["dedupe_dropped_slot_count"] == 0
    assert summary["handoff_shard_count"] == 7
    assert summary["full_seven_slot_set_seen"] is True
    assert summary["candidate_return_records_written"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False

    out = tmp_path / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract"
    shards = _read_jsonl(out / "private_causal_evidence_executor_handoff_shards.jsonl")
    assert [row["priority_rank"] for row in shards] == list(range(1, 8))
    assert sum(row["slot_ref_count"] for row in shards) == 14
    assert all(row["output_boundary"] == "handoff_contract_only_no_execution_no_candidate_returns_written" for row in shards)
    assert all(row["root_or_window_hash_unique_key_allowed"] is False for row in shards)
    assert all(row["dedupe_dropped_slots"] is False for row in shards)


def test_tmp_groups_handoff_by_priority_language_task_source_and_slot(tmp_path: Path) -> None:
    stage12521 = load_stage12521()
    _stage12519_rows(
        tmp_path,
        [
            _identity(1, language="python", task="transition_next_action", source_stage="stage_a"),
            _identity(2, language="rust", task="transition_next_action", source_stage="stage_a"),
            _identity(3, language="python", task="transition_continue_or_stop", source_stage="stage_a"),
            _identity(4, language="python", task="transition_next_action", source_stage="stage_b"),
        ],
    )
    _build_stage12520(tmp_path)

    summary = stage12521.build(tmp_path)

    assert summary["input_expanded_slot_count"] == 28
    assert summary["handoff_shard_count"] == 28
    out = tmp_path / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract"
    shards = _read_jsonl(out / "private_causal_evidence_executor_handoff_shards.jsonl")
    keys = {
        (
            row["language_family"],
            row["task_family"],
            row["source_stage_name"],
            row["evidence_slot"],
        )
        for row in shards
    }
    assert len(keys) == 28
    assert all(isinstance(row["priority_rank"], int) for row in shards)
    assert ("python", "transition_next_action", "stage_a", stage12521.FULL_SEVEN_SLOTS[0]) in keys
    assert ("rust", "transition_next_action", "stage_a", stage12521.FULL_SEVEN_SLOTS[0]) in keys


def test_tmp_handoff_contains_exact_stage12516_candidate_schema_and_required_gates(tmp_path: Path) -> None:
    stage12521 = load_stage12521()
    _stage12519_rows(tmp_path, [_identity(1)])
    _build_stage12520(tmp_path)

    stage12521.build(tmp_path)

    out = tmp_path / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract"
    contract = _read_json(out / "private_causal_evidence_executor_handoff_contract.json")
    shards = _read_jsonl(out / "private_causal_evidence_executor_handoff_shards.jsonl")
    assert contract["target_future_return_record_type"] == "stage12516_private_causal_evidence_return_candidate_v1"
    assert contract["required_stage12516_candidate_return_fields"] == stage12521.REQUIRED_STAGE12516_RETURN_FIELDS
    assert contract["semantic_sufficiency_gate"] == "downstream_stage12519_semantic_sufficiency_required_after_stage12516_validation"
    for row in shards:
        schema = row["expected_output_contract"]
        assert schema["target_return_record_type"] == "stage12516_private_causal_evidence_return_candidate_v1"
        assert schema["required_public_safe_return_fields_in_exact_stage12516_order"] == stage12521.REQUIRED_STAGE12516_RETURN_FIELDS
        assert row["status_hash_as_proof_allowed"] is False
        assert row["observed_action_imitation_allowed"] is False
        assert row["pass_to_pass_repair_credit_allowed"] is False
        assert row["root_or_window_hash_unique_key_allowed"] is False
        assert row["semantic_sufficiency_gate"] == "downstream_stage12519_semantic_sufficiency_required_after_stage12516_validation"
        assert row["candidate_return_records_written"] == 0


def test_raw_leak_guard_rejects_stage12520_raw_marker(tmp_path: Path) -> None:
    stage12521 = load_stage12521()
    _stage12519_rows(tmp_path, [_identity(1)])
    _build_stage12520(tmp_path)
    manifest_path = (
        tmp_path
        / "runs/local/artifacts/stage12520_private_causal_evidence_acquisition_batch_planner/private_causal_evidence_acquisition_batch_manifest.jsonl"
    )
    manifests = _read_jsonl(manifest_path)
    manifests[0]["slot_refs"][0]["source_stage"] = "stdout from private verifier output"
    _write_jsonl(manifest_path, manifests)

    with pytest.raises(stage12521.RawLeakError):
        stage12521.build(tmp_path)


def test_slot_accounting_rejects_manifest_slot_drop(tmp_path: Path) -> None:
    stage12521 = load_stage12521()
    _stage12519_rows(tmp_path, [_identity(1)])
    _build_stage12520(tmp_path)
    manifest_path = (
        tmp_path
        / "runs/local/artifacts/stage12520_private_causal_evidence_acquisition_batch_planner/private_causal_evidence_acquisition_batch_manifest.jsonl"
    )
    manifests = _read_jsonl(manifest_path)
    manifests[0]["slot_refs"] = []
    manifests[0]["missing_slot_count"] = 0
    _write_jsonl(manifest_path, manifests)

    with pytest.raises(stage12521.SlotAccountingError):
        stage12521.build(tmp_path)


def test_production_stage12520_handoff_counts_when_available(tmp_path: Path) -> None:
    stage12521 = load_stage12521()
    if not stage12521.EXPANDED_SLOTS.exists() or not stage12521.BATCH_MANIFESTS.exists() or not stage12521.BATCH_INSTRUCTIONS.exists():
        pytest.skip("Stage12520 production handoff inputs are not present")

    out = tmp_path / "runs/local/artifacts/stage12520_private_causal_evidence_acquisition_batch_planner"
    out.mkdir(parents=True, exist_ok=True)
    (out / "expanded_missing_private_causal_evidence_slots.jsonl").write_text(
        stage12521.EXPANDED_SLOTS.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (out / "private_causal_evidence_acquisition_batch_manifest.jsonl").write_text(
        stage12521.BATCH_MANIFESTS.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (out / "private_causal_evidence_acquisition_batch_instructions.jsonl").write_text(
        stage12521.BATCH_INSTRUCTIONS.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    summary = stage12521.build(tmp_path)

    assert summary["input_expanded_slot_count"] == 343
    assert summary["handoff_slot_ref_count"] == 343
    assert summary["input_batch_manifest_count"] == 154
    assert summary["handoff_shard_count"] == 154
    assert summary["dedupe_dropped_slot_count"] == 0
    assert summary["full_seven_slot_set_seen"] is True
    assert summary["candidate_return_records_written"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["raw_leak_count"] == 0
