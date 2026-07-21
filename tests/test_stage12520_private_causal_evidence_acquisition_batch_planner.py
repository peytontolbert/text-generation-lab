import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12520_private_causal_evidence_acquisition_batch_planner.py"


def load_stage12520():
    spec = importlib.util.spec_from_file_location("stage12520", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


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
    stage12520 = load_stage12520()
    worklist_rows = []
    blocker_rows = []
    matrix_rows = []
    for rec_idx, identity in enumerate(identities):
        slot_refs = []
        blocker_counts = {}
        for slot_idx, slot in enumerate(stage12520.FULL_SEVEN_SLOTS):
            work_order_id = f"a{rec_idx:03x}{slot_idx:020x}"[-24:]
            matrix_id = f"m{rec_idx:03x}{slot_idx:020x}"[-24:]
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
            blocker_counts["status_non_proof_blocked_unavailable"] = blocker_counts.get("status_non_proof_blocked_unavailable", 0) + 1
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


def test_tmp_plans_batches_without_dropping_any_seven_slot_refs(tmp_path: Path) -> None:
    stage12520 = load_stage12520()
    _stage12519_rows(
        tmp_path,
        [
            _identity(1, language="python", task="transition_next_action", source_stage="stage_unit_safe"),
            _identity(2, language="python", task="transition_next_action", source_stage="stage_unit_safe"),
        ],
    )

    summary = stage12520.build(tmp_path)

    assert summary["input_missing_worklist_count"] == 2
    assert summary["expanded_missing_slot_count"] == 14
    assert summary["batch_slot_ref_count"] == 14
    assert summary["dedupe_dropped_slot_count"] == 0
    assert summary["planned_batch_count"] == 7
    assert summary["full_seven_slot_set_seen"] is True
    assert summary["candidate_return_records_written"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False

    out = tmp_path / "runs/local/artifacts/stage12520_private_causal_evidence_acquisition_batch_planner"
    manifests = _read_jsonl(out / "private_causal_evidence_acquisition_batch_manifest.jsonl")
    assert [row["priority_rank"] for row in manifests] == list(range(1, 8))
    assert sum(row["missing_slot_count"] for row in manifests) == 14
    assert all(row["root_or_window_hash_unique_key_allowed"] is False for row in manifests)
    assert all(row["dedupe_dropped_slots"] is False for row in manifests)
    assert all(len(row["slot_refs"]) == 2 for row in manifests)


def test_tmp_groups_by_language_task_source_stage_and_slot(tmp_path: Path) -> None:
    stage12520 = load_stage12520()
    _stage12519_rows(
        tmp_path,
        [
            _identity(1, language="python", task="transition_next_action", source_stage="stage_a"),
            _identity(2, language="rust", task="transition_next_action", source_stage="stage_a"),
            _identity(3, language="python", task="transition_continue_or_stop", source_stage="stage_a"),
            _identity(4, language="python", task="transition_next_action", source_stage="stage_b"),
        ],
    )

    summary = stage12520.build(tmp_path)

    assert summary["expanded_missing_slot_count"] == 28
    assert summary["planned_batch_count"] == 28
    out = tmp_path / "runs/local/artifacts/stage12520_private_causal_evidence_acquisition_batch_planner"
    manifests = _read_jsonl(out / "private_causal_evidence_acquisition_batch_manifest.jsonl")
    group_keys = {(row["language_family"], row["task_family"], row["source_stage"], row["evidence_slot"]) for row in manifests}
    assert len(group_keys) == 28
    assert ("python", "transition_next_action", "stage_a", stage12520.FULL_SEVEN_SLOTS[0]) in group_keys
    assert ("rust", "transition_next_action", "stage_a", stage12520.FULL_SEVEN_SLOTS[0]) in group_keys


def test_tmp_instructions_include_required_gates_and_explicit_status_guidance(tmp_path: Path) -> None:
    stage12520 = load_stage12520()
    _stage12519_rows(tmp_path, [_identity(1)])

    stage12520.build(tmp_path)

    out = tmp_path / "runs/local/artifacts/stage12520_private_causal_evidence_acquisition_batch_planner"
    instructions = _read_jsonl(out / "private_causal_evidence_acquisition_batch_instructions.jsonl")
    by_slot = {row["evidence_slot"]: row for row in instructions}
    assert by_slot["patch_apply_or_no_patch_status"]["explicit_non_present_status_allowed_for_slot"] is True
    assert by_slot["stop_continue_policy_label"]["explicit_non_present_status_allowed_for_slot"] is True
    assert by_slot["structured_state_before_codes"]["explicit_non_present_status_allowed_for_slot"] is False
    for row in instructions:
        assert row["status_hash_as_proof_allowed"] is False
        assert row["observed_action_imitation_allowed"] is False
        assert row["pass_to_pass_repair_credit_allowed"] is False
        assert row["required_evidence_slots_for_complete_record"] == stage12520.FULL_SEVEN_SLOTS
        assert row["output_boundary"] == "planner_manifest_and_instruction_only_no_candidate_return_written"


def test_raw_leak_guard_rejects_public_fields(tmp_path: Path) -> None:
    stage12520 = load_stage12520()
    _stage12519_rows(tmp_path, [_identity(1)])
    worklist_path = (
        tmp_path
        / "runs/local/artifacts/stage12519_private_causal_evidence_semantic_sufficiency_gate/missing_private_causal_evidence_worklist.jsonl"
    )
    rows = _read_jsonl(worklist_path)
    rows[0]["slot_refs"][0]["policy_label"] = "stop"
    _write_jsonl(worklist_path, rows)

    with pytest.raises(stage12520.RawLeakError):
        stage12520.build(tmp_path)


def test_slot_accounting_rejects_matrix_worklist_mismatch(tmp_path: Path) -> None:
    stage12520 = load_stage12520()
    _stage12519_rows(tmp_path, [_identity(1)])
    matrix_path = (
        tmp_path
        / "runs/local/artifacts/stage12519_private_causal_evidence_semantic_sufficiency_gate/private_causal_evidence_semantic_sufficiency_matrix.jsonl"
    )
    rows = _read_jsonl(matrix_path)
    _write_jsonl(matrix_path, rows[:-1])

    with pytest.raises(stage12520.SlotAccountingError):
        stage12520.build(tmp_path)


def test_production_stage12519_batch_counts_when_available(tmp_path: Path) -> None:
    stage12520 = load_stage12520()
    if not stage12520.MISSING_WORKLIST.exists():
        pytest.skip("Stage12519 production worklist is not present")

    out = tmp_path / "runs/local/artifacts/stage12519_private_causal_evidence_semantic_sufficiency_gate"
    out.mkdir(parents=True, exist_ok=True)
    (out / "missing_private_causal_evidence_worklist.jsonl").write_text(
        stage12520.MISSING_WORKLIST.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (out / "private_causal_evidence_semantic_sufficiency_blockers.jsonl").write_text(
        stage12520.BLOCKERS.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (out / "private_causal_evidence_semantic_sufficiency_matrix.jsonl").write_text(
        stage12520.MATRIX.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    summary = stage12520.build(tmp_path)

    assert summary["input_missing_worklist_count"] == 49
    assert summary["input_blocker_count"] == 49
    assert summary["expanded_missing_slot_count"] == 343
    assert summary["batch_slot_ref_count"] == 343
    assert summary["dedupe_dropped_slot_count"] == 0
    assert summary["full_seven_slot_set_seen"] is True
    assert summary["candidate_return_records_written"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["raw_leak_count"] == 0
