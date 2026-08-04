#!/usr/bin/env python3
# Build Stage12641 independent review of canonical curriculum renderer preflight artifacts.
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12641_canonical_curriculum_renderer_independent_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12640 = ROOT / "runs/local/artifacts/stage12640_canonical_curriculum_renderer_preflight_only"
S12640_SUMMARY = ROOT / "runs/summaries/stage12640_canonical_curriculum_renderer_preflight_only.json"

EXPECTED_HASHES = {
    "stage12640_summary": "6e25597c3e5477b716ee03f3be02d7cfc348bfc67cd6d532aa05e6ba3c78aa4a",
    "stage12640_contract": "ad88cd0cfbfb94c70f55e5c6ccacb49e561a61b916777950fb494425d6d26039",
    "stage12640_pointer": "da74142c7f9fc8ec7b61813dad4383804aa599400ade3efb1c1cb62ae7ad418e",
    "stage12640_card": "bd913f847143fe866e98aec38724e89b8b951296e9d4bf8ade473ed582890eef",
    "stage12640_private": "8cd62840f9ff4fe46e89e190f46e4742e2e295fce06d2e689bd798ea0ff4d05d",
    "stage12640_rows_bytes": "2e61d2dc9c8331ebe0dc5f36da28a7332c20b91306a5c809fc8737b92824b0b3",
}
EXPECTED_STAGE12640_ARTIFACTS = [
    "canonical_renderer_card.json",
    "contract.json",
    "digest_pointer.json",
    "private/canonical_candidate_curriculum_rows_preflight.jsonl",
    "private/canonical_curriculum_renderer_preflight_only.json",
    "summary.json",
]
CANONICAL_REQUIRED_FIELDS = (
    "row_id", "split", "language_family", "input_state", "target", "loss_mask", "authority", "source_provenance", "anti_cheat_contract"
)
EXPECTED_TASK_COUNTS = {
    "transition_candidate_selection": 17,
    "transition_continue_or_stop": 25,
    "transition_evidence_citation": 16,
    "transition_next_action": 16,
    "transition_verifier_transition": 25,
}
EXPECTED_LANGUAGE_COUNTS = {"c_cpp": 10, "python": 41, "rust": 22, "web_js_ts_html": 26}

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12629_allowed", "stage12630_allowed", "stage12631_allowed", "stage12632_allowed", "stage12633_allowed",
    "stage12634_allowed", "stage12636_allowed", "stage12637_allowed", "stage12639_allowed", "stage12640_allowed",
    "stage12641_allowed", "stage12639_training_admission_allowed", "stage12640_training_admission_allowed",
    "stage12641_training_admission_allowed", "stage12642_training_admission_allowed",
    "vm_branch_active", "vm_runner_execution_allowed", "execution_performed", "replay_trustworthy",
    "causal_transition_atoms_present", "causal_transition_atoms_allowed", "level3_preflight_allowed", "level_3_materialized",
    "level_3_materialization_allowed", "gpu_allocation_requested", "cuda2_training_allowed",
    "training_admission_allowed", "training_admission_preflight_allowed", "training_admitted", "training_allowed", "training_run_allowed",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "admission_allowed", "ranking_allowed", "positive_stop", "dry_run_ready",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream", "stdout.raw", "stderr.raw",
    "before_commit_oid", "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch", "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
    "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
    "guardrail_scan.json", "combined_train_support_ledger", "jsonl", "row_id", "stable_lineage_key",
)


class CanonicalRendererIndependentReviewError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CanonicalRendererIndependentReviewError("json_object_required:" + path.name)
    return value


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise CanonicalRendererIndependentReviewError(f"candidate_row_object_required:{line_number}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def no_claim_fields() -> dict[str, Any]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise CanonicalRendererIndependentReviewError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise CanonicalRendererIndependentReviewError(f"{label}_public_leak:{needle}")


def load_stage12640() -> dict[str, Any]:
    emitted = sorted(path.relative_to(S12640).as_posix() for path in S12640.rglob("*") if path.is_file())
    if emitted != EXPECTED_STAGE12640_ARTIFACTS:
        raise CanonicalRendererIndependentReviewError("stage12640_artifact_manifest_drift")
    summary = read_json(S12640 / "summary.json")
    external = read_json(S12640_SUMMARY)
    contract = read_json(S12640 / "contract.json")
    pointer = read_json(S12640 / "digest_pointer.json")
    card = read_json(S12640 / "canonical_renderer_card.json")
    private = read_json(S12640 / "private/canonical_curriculum_renderer_preflight_only.json")
    rows_bytes = (S12640 / "private/canonical_candidate_curriculum_rows_preflight.jsonl").read_bytes()
    if summary != external:
        raise CanonicalRendererIndependentReviewError("stage12640_external_summary_mismatch")
    for label, value in (
        ("stage12640_summary", summary),
        ("stage12640_contract", contract),
        ("stage12640_pointer", pointer),
        ("stage12640_card", card),
        ("stage12640_private", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise CanonicalRendererIndependentReviewError("stage12640_pin_drift:" + label)
    if sha256_bytes(rows_bytes) != EXPECTED_HASHES["stage12640_rows_bytes"]:
        raise CanonicalRendererIndependentReviewError("stage12640_rows_hash_drift")
    rows = read_jsonl_bytes(rows_bytes)
    if pointer.get("contract_sha256") != EXPECTED_HASHES["stage12640_contract"]:
        raise CanonicalRendererIndependentReviewError("stage12640_pointer_contract_hash_drift")
    if pointer.get("private_canonical_curriculum_renderer_preflight_sha256") != EXPECTED_HASHES["stage12640_private"]:
        raise CanonicalRendererIndependentReviewError("stage12640_pointer_private_hash_drift")
    if pointer.get("canonical_renderer_card_sha256") != EXPECTED_HASHES["stage12640_card"]:
        raise CanonicalRendererIndependentReviewError("stage12640_pointer_card_hash_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("card", card)):
        assert_public_sanitized(record, "stage12640_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "card": card, "private": private, "rows": rows}


def validate_stage12640(stage12640: Mapping[str, Any]) -> dict[str, Any]:
    summary = stage12640["summary"]
    contract = stage12640["contract"]
    card = stage12640["card"]
    rows = stage12640["rows"]
    for field in (
        "stage12640_canonical_curriculum_renderer_preflight_allowed",
        "stage12640_canonical_curriculum_renderer_preflight_only",
        "stage12640_canonical_curriculum_renderer_preflight_performed",
        "stage12641_canonical_curriculum_renderer_independent_review_allowed",
    ):
        if summary.get(field) is not True or contract.get(field) is not True:
            raise CanonicalRendererIndependentReviewError("stage12640_true_marker_drift:" + field)
    for field in (
        "dataset_rows_admitted", "new_rows_admitted", "training_admission_allowed", "training_allowed",
        "strict_eval_admitted", "sealed_eval_admitted", "replay_trustworthy", "level_3_materialized",
        "gpu_allocation_requested", "vm_runner_execution_allowed", "causal_transition_atoms_present",
    ):
        if summary.get(field) is not False:
            raise CanonicalRendererIndependentReviewError("stage12640_forbidden_gate_drift:" + field)
    if summary.get("decision") != "CANONICAL_CURRICULUM_ROWS_RENDERED_NO_ADMISSION_OR_TRAINING":
        raise CanonicalRendererIndependentReviewError("stage12640_decision_drift")
    if summary.get("rendered_candidate_rows") != 99 or summary.get("schema_complete_rows") != 99 or summary.get("schema_blocked_rows") != 0:
        raise CanonicalRendererIndependentReviewError("stage12640_schema_count_drift")
    if summary.get("normalized_suffix_choice_rows") != 99 or summary.get("decoder_ce_rows") != 0:
        raise CanonicalRendererIndependentReviewError("stage12640_loss_policy_drift")
    if summary.get("answer_placeholder_rows_after_renderer") != 0 or summary.get("label_correctness_unproved_rows") != 0:
        raise CanonicalRendererIndependentReviewError("stage12640_placeholder_or_label_proof_drift")
    if sum((summary.get("label_correctness_proof_counts") or {}).values()) != 99:
        raise CanonicalRendererIndependentReviewError("stage12640_label_proof_count_drift")
    if summary.get("next_required_action") != STAGE:
        raise CanonicalRendererIndependentReviewError("stage12640_next_action_drift")
    if card.get("loss_key_counts") != {"suffix_choice_ce": 99} or card.get("unsupported_loss_rows") != 0:
        raise CanonicalRendererIndependentReviewError("stage12640_card_loss_drift")
    if card.get("answer_placeholder_rows") != 0 or card.get("label_correctness_unproved_rows") != 0:
        raise CanonicalRendererIndependentReviewError("stage12640_card_placeholder_or_label_proof_drift")
    if card.get("unsafe_authority_rows") != 0 or card.get("duplicate_rendered_ids") != 0:
        raise CanonicalRendererIndependentReviewError("stage12640_card_authority_or_duplicate_drift")
    if card.get("task_family_counts") != EXPECTED_TASK_COUNTS or card.get("language_counts") != EXPECTED_LANGUAGE_COUNTS:
        raise CanonicalRendererIndependentReviewError("stage12640_card_distribution_drift")
    required = set(CANONICAL_REQUIRED_FIELDS)
    ids = []
    task_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    loss_counts: Counter[str] = Counter()
    unsafe_authority_rows = 0
    old_anti_cheat_key_rows = 0
    truthful_contract_rows = 0
    answer_placeholder_rows = 0
    label_correctness_proof_rows = 0
    for row in rows:
        if not required <= set(row):
            raise CanonicalRendererIndependentReviewError("candidate_required_field_missing")
        ids.append(str(row["row_id"]))
        if not str(row["row_id"]).startswith("stage12640::"):
            raise CanonicalRendererIndependentReviewError("candidate_identity_prefix_drift")
        if row.get("split") != "train" or row.get("candidate_only_no_admission") is not True:
            raise CanonicalRendererIndependentReviewError("candidate_split_or_admission_drift")
        if row.get("training_allowed") is not False or row.get("dataset_rows_admitted") is not False:
            raise CanonicalRendererIndependentReviewError("candidate_training_gate_drift")
        if row.get("strict_eval_eligible") is not False or row.get("sealed_eval_eligible") is not False or row.get("level3_admitted") is not False:
            raise CanonicalRendererIndependentReviewError("candidate_eval_or_level3_gate_drift")
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        if loss_mask != {"suffix_choice_ce": True}:
            raise CanonicalRendererIndependentReviewError("candidate_loss_mask_drift")
        loss_counts.update(key for key, value in loss_mask.items() if value)
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        unsafe_authority_rows += int(any(value is not False for value in authority.values()))
        provenance = row.get("source_provenance") if isinstance(row.get("source_provenance"), dict) else {}
        if provenance.get("raw_source_emitted") is not False or provenance.get("raw_verifier_log_emitted") is not False or provenance.get("project_training_authority") is not False:
            raise CanonicalRendererIndependentReviewError("candidate_source_provenance_gate_drift")
        anti = row.get("anti_cheat_contract") if isinstance(row.get("anti_cheat_contract"), dict) else {}
        old_anti_cheat_key_rows += int("target_label_not_visible_in_input_state" in anti or "target_value_not_visible_in_input_state" in anti)
        truthful_contract_rows += int(
            anti.get("option_labels_may_appear_in_input_state") is True
            and anti.get("answer_label_not_marked_as_correct_in_input_state") is True
            and anti.get("supervised_signal_stored_only_in_target") is True
            and anti.get("raw_source_not_emitted") is True
            and anti.get("raw_verifier_log_not_emitted") is True
        )
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        input_state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
        rendered = input_state.get("rendered_input_text") if isinstance(input_state.get("rendered_input_text"), str) else ""
        answer_placeholder_rows += int("answer:" in rendered.lower())
        proof = target.get("label_correctness_proof") if isinstance(target.get("label_correctness_proof"), dict) else {}
        label_correctness_proof_rows += int(bool(proof.get("proof_mode")) and proof.get("answer_placeholder_removed") is True)
        task_counts[str(target.get("task_family") or "unknown")] += 1
        language_counts[str(row.get("language_family") or "unknown")] += 1
    if len(rows) != 99 or len(set(ids)) != 99:
        raise CanonicalRendererIndependentReviewError("candidate_row_count_or_identity_drift")
    if unsafe_authority_rows != 0 or old_anti_cheat_key_rows != 0 or truthful_contract_rows != 99:
        raise CanonicalRendererIndependentReviewError("candidate_authority_or_anti_cheat_drift")
    if answer_placeholder_rows != 0 or label_correctness_proof_rows != 99:
        raise CanonicalRendererIndependentReviewError("candidate_placeholder_or_label_proof_drift")
    if dict(sorted(task_counts.items())) != EXPECTED_TASK_COUNTS or dict(sorted(language_counts.items())) != EXPECTED_LANGUAGE_COUNTS:
        raise CanonicalRendererIndependentReviewError("candidate_distribution_drift")
    if dict(sorted(loss_counts.items())) != {"suffix_choice_ce": 99}:
        raise CanonicalRendererIndependentReviewError("candidate_loss_count_drift")
    return {
        "candidate_count": len(rows),
        "unique_candidate_ids": len(set(ids)),
        "schema_complete_rows": len(rows),
        "loss_key_counts": dict(sorted(loss_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "unsafe_authority_rows": unsafe_authority_rows,
        "truthful_anti_cheat_contract_rows": truthful_contract_rows,
        "answer_placeholder_rows": answer_placeholder_rows,
        "label_correctness_proof_rows": label_correctness_proof_rows,
    }


def build_review(stage12640: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    row_audit = validate_stage12640(stage12640)
    checks = [
        {"check_id": "stage12640_public_and_private_hashes_pinned", "status": "passed"},
        {"check_id": "stage12640_artifact_manifest_exact", "status": "passed", "artifact_count": len(EXPECTED_STAGE12640_ARTIFACTS)},
        {"check_id": "candidate_rows_are_99_unique_schema_complete_rows", "status": "passed", "candidate_rows": row_audit["candidate_count"]},
        {"check_id": "loss_policy_suffix_choice_only_decoder_ce_disabled", "status": "passed"},
        {"check_id": "answer_placeholders_absent_from_all_rendered_inputs", "status": "passed"},
        {"check_id": "target_labels_have_row_local_correctness_proofs", "status": "passed"},
        {"check_id": "candidate_authority_closed_no_admission", "status": "passed"},
        {"check_id": "anti_cheat_contract_truthful_for_option_label_inputs", "status": "passed"},
        {"check_id": "public_artifacts_have_no_private_leaks", "status": "passed"},
        {"check_id": "training_eval_replay_level3_gpu_vm_forbidden", "status": "passed"},
    ]
    review = {
        "record_type": "stage12641_canonical_curriculum_renderer_independent_review_v1",
        "review_scope": "canonical_curriculum_renderer_independent_review_only",
        "reviewed_stage": "stage12640_canonical_curriculum_renderer_preflight_only",
        "reviewed_hashes": EXPECTED_HASHES,
        "review_checks": checks,
        "review_check_count": len(checks),
        "review_status": "independent_review_passed_candidate_rows_remain_private_no_admission",
        "candidate_rows_independently_reviewed": row_audit["candidate_count"],
        "schema_complete_rows_after_review": row_audit["schema_complete_rows"],
        "schema_blocked_rows_after_review": 0,
        "normalized_suffix_choice_rows_after_review": 99,
        "decoder_ce_rows_after_review": 0,
        "unsafe_authority_rows_after_review": row_audit["unsafe_authority_rows"],
        "truthful_anti_cheat_contract_rows": row_audit["truthful_anti_cheat_contract_rows"],
        "answer_placeholder_rows_after_review": row_audit["answer_placeholder_rows"],
        "label_correctness_proof_rows_after_review": row_audit["label_correctness_proof_rows"],
        "candidate_rows_admitted_after_review": False,
        "training_allowed_after_review": False,
        "strict_eval_admitted_after_review": False,
        "sealed_eval_admitted_after_review": False,
        "level_3_materialized_after_review": False,
        "replay_trustworthy_after_review": False,
        "vm_runner_execution_after_review": False,
    }
    public_card = {
        "record_type": "stage12641_public_canonical_curriculum_renderer_independent_review_card_v1",
        "review_scope": "canonical_curriculum_renderer_independent_review_only",
        "review_status": review["review_status"],
        "candidate_rows_independently_reviewed": row_audit["candidate_count"],
        "schema_complete_rows": row_audit["schema_complete_rows"],
        "schema_blocked_rows": 0,
        "unique_candidate_ids": row_audit["unique_candidate_ids"],
        "duplicate_candidate_ids": 0,
        "loss_key_counts": row_audit["loss_key_counts"],
        "decoder_ce_rows": 0,
        "task_family_counts": row_audit["task_family_counts"],
        "language_counts": row_audit["language_counts"],
        "unsafe_authority_rows": 0,
        "truthful_anti_cheat_contract_rows": row_audit["truthful_anti_cheat_contract_rows"],
        "answer_placeholder_rows_after_review": row_audit["answer_placeholder_rows"],
        "label_correctness_proof_rows_after_review": row_audit["label_correctness_proof_rows"],
        "candidate_rows_admitted_after_review": False,
        "training_allowed_after_review": False,
    }
    return review, public_card


def build_packet(stage12640: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    review, public_card = build_review(stage12640)
    true_fields = {
        "authoritative_ledger_update_allowed": True,
        "authoritative_ledger_updated": True,
        "ledger_update_materialized": True,
        "stage12638_authoritative_ledger_update_materialization_only_allowed": True,
        "stage12639_curriculum_coverage_preflight_allowed": True,
        "stage12639_curriculum_coverage_preflight_performed": True,
        "stage12640_canonical_curriculum_renderer_preflight_allowed": True,
        "stage12640_canonical_curriculum_renderer_preflight_only": True,
        "stage12640_canonical_curriculum_renderer_preflight_performed": True,
        "stage12641_canonical_curriculum_renderer_independent_review_allowed": True,
        "stage12641_canonical_curriculum_renderer_independent_review_only": True,
        "stage12641_canonical_curriculum_renderer_independent_review_performed": True,
        "stage12642_causal_transition_atom_preflight_allowed": True,
        "vm_branch_remains_paused": True,
    }
    private = {
        "record_type": "stage12641_private_canonical_curriculum_renderer_independent_review_only_v1",
        **no_claim_fields(),
        **true_fields,
        "source_hashes": EXPECTED_HASHES,
        "canonical_curriculum_renderer_independent_review": review,
        "public_review_card": public_card,
        "decision": "CANONICAL_CURRICULUM_RENDERER_INDEPENDENT_REVIEW_PASSED_NO_ADMISSION_OR_TRAINING",
    }
    contract = {
        "record_type": "stage12641_public_canonical_curriculum_renderer_independent_review_only_contract_v1",
        **no_claim_fields(),
        **true_fields,
        "stage12640_summary_sha256": EXPECTED_HASHES["stage12640_summary"],
        "stage12640_contract_sha256": EXPECTED_HASHES["stage12640_contract"],
        "stage12640_rows_sha256": EXPECTED_HASHES["stage12640_rows_bytes"],
        "canonical_renderer_independent_review_sha256": stable_hash(review),
        "public_review_card_sha256": stable_hash(public_card),
        "private_canonical_renderer_independent_review_sha256": stable_hash(private),
        "claim_boundary": {
            "review": "canonical_renderer_independent_review_only",
            "candidate_rows": "private_candidates_reviewed_but_not_admitted",
            "dataset_row_admission": "not_performed",
            "training": "not_authorized",
            "eval": "not_authorized",
            "replay": "not_executed",
            "level3": "not_materialized",
            "gpu": "not_authorized",
            "vm": "paused_not_used_for_review",
        },
    }
    summary = {
        "record_type": "stage12641_public_canonical_curriculum_renderer_independent_review_only_summary_v1",
        **no_claim_fields(),
        **true_fields,
        "stage": STAGE,
        "decision": "CANONICAL_CURRICULUM_RENDERER_INDEPENDENT_REVIEW_PASSED_NO_ADMISSION_OR_TRAINING",
        "stage12640_summary_sha256": EXPECTED_HASHES["stage12640_summary"],
        "stage12640_contract_sha256": EXPECTED_HASHES["stage12640_contract"],
        "stage12640_rows_sha256": EXPECTED_HASHES["stage12640_rows_bytes"],
        "canonical_renderer_independent_review_sha256": stable_hash(review),
        "public_review_card_sha256": stable_hash(public_card),
        "private_canonical_renderer_independent_review_sha256": stable_hash(private),
        "review_status": review["review_status"],
        "authoritative_admitted_train_support_tasks_after_review": 190,
        "authoritative_gap_to_500_after_review": 310,
        "candidate_rows_independently_reviewed": review["candidate_rows_independently_reviewed"],
        "schema_complete_rows_after_review": review["schema_complete_rows_after_review"],
        "schema_blocked_rows_after_review": 0,
        "normalized_suffix_choice_rows_after_review": 99,
        "decoder_ce_rows_after_review": 0,
        "answer_placeholder_rows_after_review": review["answer_placeholder_rows_after_review"],
        "label_correctness_proof_rows_after_review": review["label_correctness_proof_rows_after_review"],
        "candidate_rows_admitted_after_review": False,
        "dataset_rows_admitted_after_review": False,
        "training_allowed_after_review": False,
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": [
            "causal_transition_atoms_not_materialized",
            "level_3_not_materialized",
            "rendered_rows_not_admitted",
            "training_admission_forbidden",
        ],
        "next_required_action": "stage12642_causal_transition_atom_preflight_only",
    }
    for label, record in (("summary", summary), ("contract", contract), ("card", public_card)):
        check_false(record, "stage12641_" + label)
        assert_public_sanitized(record, "stage12641_" + label)
    check_false(private, "stage12641_private")
    return summary, contract, private, public_card


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12640 = load_stage12640()
    summary, contract, private, public_card = build_packet(stage12640)
    pointer = {
        "record_type": "stage12641_public_private_canonical_curriculum_renderer_independent_review_pointer_v1",
        **no_claim_fields(),
        "stage12640_summary_sha256": EXPECTED_HASHES["stage12640_summary"],
        "contract_sha256": stable_hash(contract),
        "private_canonical_renderer_independent_review_sha256": stable_hash(private),
        "canonical_renderer_independent_review_sha256": stable_hash(private["canonical_curriculum_renderer_independent_review"]),
        "public_review_card_sha256": stable_hash(public_card),
        "authoritative_ledger_update_allowed": True,
        "authoritative_ledger_updated": True,
        "ledger_update_materialized": True,
        "stage12638_authoritative_ledger_update_materialization_only_allowed": True,
        "stage12639_curriculum_coverage_preflight_allowed": True,
        "stage12639_curriculum_coverage_preflight_performed": True,
        "stage12640_canonical_curriculum_renderer_preflight_allowed": True,
        "stage12640_canonical_curriculum_renderer_preflight_only": True,
        "stage12640_canonical_curriculum_renderer_preflight_performed": True,
        "stage12641_canonical_curriculum_renderer_independent_review_allowed": True,
        "stage12641_canonical_curriculum_renderer_independent_review_only": True,
        "stage12641_canonical_curriculum_renderer_independent_review_performed": True,
        "stage12642_causal_transition_atom_preflight_allowed": True,
        "vm_branch_remains_paused": True,
    }
    check_false(pointer, "stage12641_pointer")
    assert_public_sanitized(pointer, "stage12641_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "public_review_card.json", public_card)
    write_json(out / "private/canonical_curriculum_renderer_independent_review_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
