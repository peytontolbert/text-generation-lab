#!/usr/bin/env python3
# Build Stage12640 canonical curriculum renderer preflight only.
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12640_canonical_curriculum_renderer_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12639 = ROOT / "runs/local/artifacts/stage12639_curriculum_coverage_admission_preflight_only"
S12639_SUMMARY = ROOT / "runs/summaries/stage12639_curriculum_coverage_admission_preflight_only.json"
S12638_ROWS = ROOT / "runs/local/artifacts/stage12638_authoritative_ledger_update_materialization_only/private/authoritative_update_evidence_rows.jsonl"
LOSS_SCHEMA = ROOT / "configs/schema/loss_mask.schema.json"
MANIFEST_ROW_SCHEMA = ROOT / "configs/schema/manifest_row.schema.json"

EXPECTED_HASHES = {
    "stage12639_summary": "60b62304f5c8f0ba5b4acc54bd0f7e57683cd4ae21fd945007a2ec1b47364e1a",
    "stage12639_contract": "8b316150045effb7ccb090973265a8b10ca56a2e33469bf2aa1d65d50ed63160",
    "stage12639_pointer": "a9b87d9b473b7d0f88e0cee352d6dcdfa92d9dfe3dab1f47e4bfac104176b581",
    "stage12639_private": "f50f28127ce0f3f658b5436b4dffd21653a2a91bde4ac0b8a6cf359a9b779e57",
    "stage12639_matrix": "4c71220361b6135cad8c9ba4a199676ed4c7dcd9f2d2e65431c72e98feeeacaf",
    "stage12639_row_audit_bytes": "f1bac082251e3bb2e548aea6cf84b44526f9ae87d4d11a50531bed8b791da66a",
    "stage12638_rows_bytes": "065923de4ef183501b5f528d82065814826bd257a9b1814d54850680fe6cbce5",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12629_allowed", "stage12630_allowed", "stage12631_allowed", "stage12632_allowed", "stage12633_allowed",
    "stage12634_allowed", "stage12636_allowed", "stage12637_allowed", "stage12639_allowed", "stage12640_allowed",
    "stage12631_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_update_dry_run_only_allowed",
    "stage12633_authoritative_ledger_update_dry_run_only_allowed",
    "stage12634_authoritative_ledger_update_dry_run_only_allowed",
    "stage12639_training_admission_allowed", "stage12640_training_admission_allowed",
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

CANONICAL_REQUIRED_FIELDS = (
    "row_id", "split", "language_family", "input_state", "target", "loss_mask", "authority", "source_provenance", "anti_cheat_contract"
)
AUTHORITY_KEYS = (
    "model_execution_authorized_next", "decoder_ce_training_authorized_next", "runtime_authorized",
    "source_emission_authorized", "body_emission_authorized", "gemma_execution_authorized_next",
    "harness_execution_authorized_next", "scoring_authorized_next", "controller_complete_merge_authorized_next",
    "promotion_ready", "training_allowed", "training_admission_allowed", "dataset_rows_admitted",
)
SUPPORTED_TASKS = (
    "transition_candidate_selection", "transition_continue_or_stop", "transition_evidence_citation",
    "transition_next_action", "transition_verifier_transition",
)

class CanonicalCurriculumRendererError(RuntimeError):
    pass

def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def short_hash(value: str, n: int = 24) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:n]

def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CanonicalCurriculumRendererError("json_object_required:" + path.name)
    return value

def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise CanonicalCurriculumRendererError(f"row_object_required:{line_number}")
        rows.append(value)
    return rows

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())

def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n")
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
            raise CanonicalCurriculumRendererError(f"{label}_gate_drift:{field}")

def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise CanonicalCurriculumRendererError(f"{label}_public_leak:{needle}")

def load_schema() -> dict[str, Any]:
    row_schema = read_json(MANIFEST_ROW_SCHEMA)
    loss_schema = read_json(LOSS_SCHEMA)
    required_fields = tuple(row_schema.get("required") or CANONICAL_REQUIRED_FIELDS)
    allowed_loss_keys = set((loss_schema.get("properties") or {}).keys())
    if set(required_fields) != set(CANONICAL_REQUIRED_FIELDS):
        raise CanonicalCurriculumRendererError("manifest_schema_required_field_drift")
    if "suffix_choice_ce" not in allowed_loss_keys:
        raise CanonicalCurriculumRendererError("loss_schema_missing_suffix_choice_ce")
    return {"required_fields": required_fields, "allowed_loss_keys": allowed_loss_keys}

def load_stage12639() -> dict[str, Any]:
    summary = read_json(S12639 / "summary.json")
    external = read_json(S12639_SUMMARY)
    contract = read_json(S12639 / "contract.json")
    pointer = read_json(S12639 / "digest_pointer.json")
    private = read_json(S12639 / "private/curriculum_coverage_admission_preflight_only.json")
    matrix = read_json(S12639 / "curriculum_coverage_matrix.json")
    row_audit_bytes = (S12639 / "private/row_curriculum_audit.jsonl").read_bytes()
    source_rows_bytes = S12638_ROWS.read_bytes()
    if summary != external:
        raise CanonicalCurriculumRendererError("stage12639_external_summary_mismatch")
    for label, value in (("stage12639_summary", summary), ("stage12639_contract", contract), ("stage12639_pointer", pointer), ("stage12639_private", private), ("stage12639_matrix", matrix)):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise CanonicalCurriculumRendererError("stage12639_pin_drift:" + label)
    if sha256_bytes(row_audit_bytes) != EXPECTED_HASHES["stage12639_row_audit_bytes"]:
        raise CanonicalCurriculumRendererError("stage12639_row_audit_hash_drift")
    if sha256_bytes(source_rows_bytes) != EXPECTED_HASHES["stage12638_rows_bytes"]:
        raise CanonicalCurriculumRendererError("stage12638_rows_hash_drift")
    rows = read_jsonl_bytes(source_rows_bytes)
    if summary.get("canonical_trainer_ready_rows") != 0 or summary.get("canonical_trainer_blocked_rows") != 99:
        raise CanonicalCurriculumRendererError("stage12639_readiness_drift")
    if summary.get("stage12640_canonical_curriculum_renderer_preflight_allowed") is not True:
        raise CanonicalCurriculumRendererError("stage12640_preflight_not_allowed")
    for field in ("dataset_rows_admitted", "new_rows_admitted", "training_allowed", "level_3_materialized", "replay_trustworthy"):
        if summary.get(field) is not False:
            raise CanonicalCurriculumRendererError("stage12639_forbidden_gate_drift:" + field)
    if len(rows) != 99:
        raise CanonicalCurriculumRendererError("source_row_count_drift")
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private, "matrix": matrix, "rows": rows}

def task_name(row: Mapping[str, Any]) -> str:
    return str(row.get("task_family") or row.get("task_projection") or row.get("record_type") or "unknown")

def strip_answer_placeholders(text: str) -> str:
    cleaned: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s*answer\s*:\s*(.*)$", line, flags=re.IGNORECASE)
        if match:
            if match.group(1).strip():
                raise CanonicalCurriculumRendererError("answer_placeholder_contains_supervised_text")
            continue
        cleaned.append(line)
    normalized = "\n".join(cleaned).strip()
    if re.search(r"(?im)^\s*answer\s*:", normalized):
        raise CanonicalCurriculumRendererError("answer_placeholder_not_removed")
    return normalized

def option_evidence_ids(option: Mapping[str, Any]) -> list[Any]:
    candidate = option.get("semantic_candidate") if isinstance(option.get("semantic_candidate"), dict) else {}
    evidence = candidate.get("evidence_ids") if isinstance(candidate.get("evidence_ids"), list) else []
    return evidence

def option_semantic_values(option: Mapping[str, Any]) -> set[str]:
    candidate = option.get("semantic_candidate") if isinstance(option.get("semantic_candidate"), dict) else {}
    values = {option.get("semantic_id"), option.get("semantic_value"), option.get("value"), candidate.get("value"), candidate.get("role")}
    return {str(value) for value in values if isinstance(value, str) and value}

def label_correctness_proof(row: Mapping[str, Any], label: str, options: list[Any]) -> dict[str, Any]:
    typed_options = [option for option in options if isinstance(option, dict)]
    chosen = [option for option in typed_options if option.get("label") == label]
    if len(chosen) != 1:
        raise CanonicalCurriculumRendererError("target_label_not_unique_in_options")
    chosen_option = chosen[0]
    target_semantic = row.get("target_semantic_id") or row.get("target_semantic_value")
    chosen_values = option_semantic_values(chosen_option)
    chosen_evidence = option_evidence_ids(chosen_option)
    alt_evidence_count = sum(1 for option in typed_options if option is not chosen_option and option_evidence_ids(option))
    chosen_value_text = str(chosen_option.get("value") or "")
    alt_selected_test_backed = sum(1 for option in typed_options if option is not chosen_option and "selected_test_backed" in str(option.get("value") or ""))
    if isinstance(target_semantic, str) and target_semantic in chosen_values:
        proof_mode = "target_semantic_matches_chosen_option"
    elif chosen_evidence and alt_evidence_count == 0:
        proof_mode = "chosen_option_has_unique_evidence_ids"
    elif "selected_test_backed" in chosen_value_text and alt_selected_test_backed == 0:
        proof_mode = "chosen_option_value_is_unique_selected_test_backed"
    else:
        raise CanonicalCurriculumRendererError("target_label_lacks_row_local_correctness_proof")
    return {
        "proof_mode": proof_mode,
        "chosen_option_semantic_id": str(chosen_option.get("semantic_id") or ""),
        "chosen_option_value": chosen_value_text,
        "source_target_semantic": str(target_semantic or ""),
        "chosen_option_has_evidence_ids": bool(chosen_evidence),
        "alternative_evidence_option_count": alt_evidence_count,
        "answer_placeholder_removed": True,
    }

def target_label(row: Mapping[str, Any]) -> str:
    label = row.get("bounded_choice_target_label") or row.get("target_label") or row.get("decoder_text")
    if not isinstance(label, str) or not label:
        raise CanonicalCurriculumRendererError("target_label_missing")
    return label

def input_text(row: Mapping[str, Any], task: str) -> str:
    if isinstance(row.get("input_text"), str) and row["input_text"]:
        return strip_answer_placeholders(row["input_text"])
    options = row.get("opaque_options") if isinstance(row.get("opaque_options"), list) else []
    option_text = "; ".join(f"{opt.get('label')}={opt.get('semantic_value') or opt.get('value') or opt.get('semantic_id') or 'option'}" for opt in options if isinstance(opt, dict) and opt.get("label"))
    return strip_answer_placeholders("\n".join([
        f"Task projection: {task}",
        f"Language: {row.get('language_family') or 'unknown'}",
        f"Record type: {row.get('record_type') or 'unknown'}",
        f"Verifier class: {row.get('verifier_output_class') or 'unknown'}",
        f"Selected-test scope count: {row.get('selected_test_scope_count') or 0}",
        f"Opaque options: {option_text}",
        "Choose the single opaque label best supported by the verifier observation.",
    ]))

def render_row(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    task = task_name(row)
    if task not in SUPPORTED_TASKS:
        raise CanonicalCurriculumRendererError("unsupported_task_for_renderer:" + task)
    label = target_label(row)
    source_id = str(row.get("row_id") or f"source_{index}")
    options = row.get("opaque_options") if isinstance(row.get("opaque_options"), list) else []
    proof = label_correctness_proof(row, label, options)
    semantic_value = row.get("target_semantic_value") if isinstance(row.get("target_semantic_value"), str) else proof["chosen_option_value"]
    return {
        "row_id": "stage12640::" + short_hash(source_id),
        "split": "train",
        "language_family": str(row.get("language_family") or "unknown"),
        "input_state": {
            "curriculum_stage": "maintainer_controller_suffix_choice_preflight",
            "task_family": task,
            "source_record_type": str(row.get("record_type") or "unknown"),
            "source_stage": str(row.get("stage") or row.get("source_stage") or "unknown"),
            "source_row_hash": short_hash(source_id),
            "root_hash": short_hash(str(row.get("root_id") or row.get("root_lineage_key_hash") or row.get("repo_family_hash") or source_id)),
            "rendered_input_text": input_text(row, task),
            "opaque_options": options,
            "selected_test_scope_count": int(row.get("selected_test_scope_count") or 0),
            "verifier_output_class": str(row.get("verifier_output_class") or "unknown"),
            "train_support_only": True,
        },
        "target": {"decoder_text": label, "suffix_choice": label, "target_ref": "opaque_label::" + label, "semantic_value": semantic_value, "task_family": task, "label_correctness_proof": proof},
        "loss_mask": {"suffix_choice_ce": True},
        "authority": {key: False for key in AUTHORITY_KEYS},
        "source_provenance": {
            "source_stage": str(row.get("stage") or row.get("source_stage") or "unknown"),
            "source_row_hash": short_hash(source_id),
            "source_rows_sha256": EXPECTED_HASHES["stage12638_rows_bytes"],
            "rendered_by_stage": STAGE,
            "raw_source_emitted": False,
            "raw_verifier_log_emitted": False,
            "project_training_authority": False,
        },
        "anti_cheat_contract": {
            "option_labels_may_appear_in_input_state": True,
            "answer_label_not_marked_as_correct_in_input_state": True,
            "supervised_signal_stored_only_in_target": True,
            "opaque_label_only_target": True,
            "raw_source_not_emitted": True,
            "raw_verifier_log_not_emitted": True,
            "row_local_training_allowed_normalized_to_train_support_only": bool((row.get("admission") if isinstance(row.get("admission"), dict) else {}).get("training_allowed") or row.get("training_allowed")),
        },
        "candidate_only_no_admission": True,
        "training_allowed": False,
        "dataset_rows_admitted": False,
        "strict_eval_eligible": False,
        "sealed_eval_eligible": False,
        "level3_admitted": False,
    }

def validate_rendered_rows(rows: list[dict[str, Any]], schema: Mapping[str, Any]) -> dict[str, Any]:
    required_fields = set(schema["required_fields"])
    allowed_loss_keys = set(schema["allowed_loss_keys"])
    missing_counts: Counter[str] = Counter(); loss_counts: Counter[str] = Counter(); task_counts: Counter[str] = Counter(); language_counts: Counter[str] = Counter(); split_counts: Counter[str] = Counter(); proof_counts: Counter[str] = Counter()
    unsafe_authority_rows = 0; unsupported_loss_rows = 0; answer_placeholder_rows = 0; unproved_label_rows = 0
    duplicate_ids = len(rows) - len({row.get("row_id") for row in rows})
    for row in rows:
        missing_counts.update(required_fields - set(row))
        split_counts[str(row.get("split"))] += 1
        language_counts[str(row.get("language_family"))] += 1
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        task_counts[str(target.get("task_family") or "unknown")] += 1
        input_state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
        rendered = input_state.get("rendered_input_text") if isinstance(input_state.get("rendered_input_text"), str) else ""
        answer_placeholder_rows += int(bool(re.search(r"(?im)^\s*answer\s*:", rendered)))
        proof = target.get("label_correctness_proof") if isinstance(target.get("label_correctness_proof"), dict) else {}
        proof_mode = str(proof.get("proof_mode") or "")
        proof_counts.update([proof_mode] if proof_mode else [])
        unproved_label_rows += int(not proof_mode or proof.get("answer_placeholder_removed") is not True)
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        enabled = [key for key, value in loss_mask.items() if value]
        loss_counts.update(enabled)
        unsupported_loss_rows += int(any(key not in allowed_loss_keys for key in enabled))
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        unsafe_authority_rows += int(any(bool(value) for value in authority.values()))
        unsafe_authority_rows += int(row.get("training_allowed") is not False or row.get("dataset_rows_admitted") is not False)
    schema_complete = not missing_counts and unsupported_loss_rows == 0 and unsafe_authority_rows == 0 and duplicate_ids == 0
    return {
        "record_type": "stage12640_public_canonical_curriculum_renderer_preflight_card_v1",
        "renderer_scope": "canonical_curriculum_rows_preflight_only",
        "rendered_row_count": len(rows),
        "schema_complete_rows": len(rows) if schema_complete else 0,
        "schema_blocked_rows": 0 if schema_complete else len(rows),
        "duplicate_rendered_ids": duplicate_ids,
        "missing_required_field_counts": dict(sorted(missing_counts.items())),
        "unsupported_loss_rows": unsupported_loss_rows,
        "unsafe_authority_rows": unsafe_authority_rows,
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "loss_key_counts": dict(sorted(loss_counts.items())),
        "label_correctness_proof_counts": dict(sorted(proof_counts.items())),
        "label_correctness_unproved_rows": unproved_label_rows,
        "answer_placeholder_rows": answer_placeholder_rows,
        "canonical_loss_policy": "suffix_choice_ce_only_decoder_ce_disabled",
        "admission_status": "not_admitted_preflight_only",
        "training_allowed_after_renderer": False,
    }

def render_rows(source_rows: list[dict[str, Any]], schema: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rendered = [render_row(row, index) for index, row in enumerate(source_rows)]
    card = validate_rendered_rows(rendered, schema)
    if card["rendered_row_count"] != 99 or card["schema_complete_rows"] != 99:
        raise CanonicalCurriculumRendererError("rendered_rows_not_schema_complete")
    if card["loss_key_counts"] != {"suffix_choice_ce": 99}:
        raise CanonicalCurriculumRendererError("rendered_loss_policy_drift")
    if card["split_counts"] != {"train": 99}:
        raise CanonicalCurriculumRendererError("rendered_split_policy_drift")
    if card["answer_placeholder_rows"] != 0 or card["label_correctness_unproved_rows"] != 0:
        raise CanonicalCurriculumRendererError("rendered_placeholder_or_label_proof_drift")
    if sum(card["label_correctness_proof_counts"].values()) != 99:
        raise CanonicalCurriculumRendererError("rendered_label_proof_count_drift")
    return rendered, card

def build_preflight(card: Mapping[str, Any], rendered_rows_sha256: str) -> dict[str, Any]:
    checks = [
        {"check_id": "stage12639_preflight_pinned", "status": "passed"},
        {"check_id": "source_rows_hash_pinned", "status": "passed", "source_rows": 99},
        {"check_id": "canonical_required_fields_rendered", "status": "passed", "schema_complete_rows": card["schema_complete_rows"]},
        {"check_id": "loss_mask_normalized_to_suffix_choice_only", "status": "passed"},
        {"check_id": "answer_placeholders_removed_from_rendered_inputs", "status": "passed"},
        {"check_id": "target_labels_have_row_local_correctness_proofs", "status": "passed"},
        {"check_id": "authority_closed_on_all_rendered_rows", "status": "passed"},
        {"check_id": "renderer_is_preflight_only_no_admission", "status": "passed"},
        {"check_id": "training_eval_replay_level3_gpu_forbidden", "status": "passed"},
    ]
    return {
        "record_type": "stage12640_canonical_curriculum_renderer_preflight_v1",
        "preflight_scope": "canonical_curriculum_renderer_preflight_only",
        "source_stage12639_summary_sha256": EXPECTED_HASHES["stage12639_summary"],
        "source_stage12638_rows_sha256": EXPECTED_HASHES["stage12638_rows_bytes"],
        "canonical_renderer_card_sha256": stable_hash(card),
        "rendered_candidate_rows_sha256": rendered_rows_sha256,
        "preflight_checks": checks,
        "preflight_check_count": len(checks),
        "preflight_status": "canonical_curriculum_rows_rendered_no_admission_or_training",
        "rendered_candidate_rows": card["rendered_row_count"],
        "schema_complete_rows": card["schema_complete_rows"],
        "schema_blocked_rows": card["schema_blocked_rows"],
        "normalized_loss_key": "suffix_choice_ce",
        "decoder_ce_rows": 0,
        "answer_placeholder_rows": card["answer_placeholder_rows"],
        "label_correctness_proof_counts": card["label_correctness_proof_counts"],
        "label_correctness_unproved_rows": card["label_correctness_unproved_rows"],
        "training_rows_admitted_after_preflight": False,
        "dataset_rows_admitted_after_preflight": False,
        "recommended_next_stage": "stage12641_canonical_curriculum_renderer_independent_review_only",
    }

def build_packet(stage12639: Mapping[str, Any], rendered_rows: list[dict[str, Any]], card: dict[str, Any], rendered_rows_sha256: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    preflight = build_preflight(card, rendered_rows_sha256)
    true_fields = {
        "authoritative_ledger_update_allowed": True, "authoritative_ledger_updated": True, "ledger_update_materialized": True,
        "stage12638_authoritative_ledger_update_materialization_only_allowed": True,
        "stage12639_curriculum_coverage_preflight_allowed": True, "stage12639_curriculum_coverage_preflight_performed": True,
        "stage12640_canonical_curriculum_renderer_preflight_allowed": True, "stage12640_canonical_curriculum_renderer_preflight_only": True,
        "stage12640_canonical_curriculum_renderer_preflight_performed": True,
        "stage12641_canonical_curriculum_renderer_independent_review_allowed": True, "vm_branch_remains_paused": True,
    }
    private = {"record_type": "stage12640_private_canonical_curriculum_renderer_preflight_only_v1", **no_claim_fields(), **true_fields, "source_hashes": EXPECTED_HASHES, "canonical_curriculum_renderer_preflight": preflight, "canonical_renderer_card": card, "rendered_candidate_rows_sha256": rendered_rows_sha256, "rendered_candidate_row_count": len(rendered_rows), "decision": "CANONICAL_CURRICULUM_ROWS_RENDERED_NO_ADMISSION_OR_TRAINING"}
    contract = {"record_type": "stage12640_public_canonical_curriculum_renderer_preflight_only_contract_v1", **no_claim_fields(), **true_fields, "stage12639_summary_sha256": EXPECTED_HASHES["stage12639_summary"], "stage12638_rows_sha256": EXPECTED_HASHES["stage12638_rows_bytes"], "canonical_renderer_card_sha256": stable_hash(card), "canonical_curriculum_renderer_preflight_sha256": stable_hash(preflight), "rendered_candidate_rows_sha256": rendered_rows_sha256, "private_canonical_curriculum_renderer_preflight_sha256": stable_hash(private), "claim_boundary": {"renderer": "canonical_candidate_rows_preflight_only", "canonical_rows": "private_candidate_artifact_not_admitted", "dataset_row_admission": "not_performed", "training": "not_authorized", "eval": "not_authorized", "replay": "not_executed", "level3": "not_materialized", "gpu": "not_authorized"}}
    summary = {"record_type": "stage12640_public_canonical_curriculum_renderer_preflight_only_summary_v1", **no_claim_fields(), **true_fields, "stage": STAGE, "decision": "CANONICAL_CURRICULUM_ROWS_RENDERED_NO_ADMISSION_OR_TRAINING", "stage12639_summary_sha256": EXPECTED_HASHES["stage12639_summary"], "stage12638_rows_sha256": EXPECTED_HASHES["stage12638_rows_bytes"], "canonical_renderer_card_sha256": stable_hash(card), "canonical_curriculum_renderer_preflight_sha256": stable_hash(preflight), "rendered_candidate_rows_sha256": rendered_rows_sha256, "private_canonical_curriculum_renderer_preflight_sha256": stable_hash(private), "preflight_status": "canonical_curriculum_rows_rendered_no_admission_or_training", "authoritative_admitted_train_support_tasks_after_update": 190, "authoritative_gap_to_500_after_update": 310, "source_row_count": 99, "rendered_candidate_rows": card["rendered_row_count"], "schema_complete_rows": card["schema_complete_rows"], "schema_blocked_rows": card["schema_blocked_rows"], "normalized_suffix_choice_rows": card["loss_key_counts"].get("suffix_choice_ce", 0), "decoder_ce_rows": 0, "answer_placeholder_rows_after_renderer": card["answer_placeholder_rows"], "label_correctness_proof_counts": card["label_correctness_proof_counts"], "label_correctness_unproved_rows": card["label_correctness_unproved_rows"], "dataset_rows_admitted_after_renderer": False, "training_allowed_after_renderer": False, "frontier_100m_training_dataset_ready": False, "downstream_blockers": ["canonical_renderer_independent_review_not_materialized", "rendered_rows_not_admitted", "repo_graph_symbol_localization_patch_repair_signals_missing", "training_admission_forbidden"], "next_required_action": "stage12641_canonical_curriculum_renderer_independent_review_only"}
    for label, record in (("summary", summary), ("contract", contract), ("card", card)):
        check_false(record, "stage12640_" + label)
        assert_public_sanitized(record, "stage12640_" + label)
    check_false(private, "stage12640_private")
    return summary, contract, private

def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12639 = load_stage12639()
    schema = load_schema()
    rendered_rows, card = render_rows(stage12639["rows"], schema)
    rendered_rows_data = b"".join(json.dumps(row, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n" for row in rendered_rows)
    rendered_rows_sha256 = sha256_bytes(rendered_rows_data)
    summary, contract, private = build_packet(stage12639, rendered_rows, card, rendered_rows_sha256)
    pointer = {"record_type": "stage12640_public_private_canonical_curriculum_renderer_preflight_pointer_v1", **no_claim_fields(), "stage12639_summary_sha256": EXPECTED_HASHES["stage12639_summary"], "contract_sha256": stable_hash(contract), "private_canonical_curriculum_renderer_preflight_sha256": stable_hash(private), "canonical_curriculum_renderer_preflight_sha256": stable_hash(private["canonical_curriculum_renderer_preflight"]), "canonical_renderer_card_sha256": stable_hash(card), "rendered_candidate_rows_sha256": rendered_rows_sha256, "authoritative_ledger_update_allowed": True, "authoritative_ledger_updated": True, "ledger_update_materialized": True, "stage12638_authoritative_ledger_update_materialization_only_allowed": True, "stage12639_curriculum_coverage_preflight_allowed": True, "stage12639_curriculum_coverage_preflight_performed": True, "stage12640_canonical_curriculum_renderer_preflight_allowed": True, "stage12640_canonical_curriculum_renderer_preflight_only": True, "stage12640_canonical_curriculum_renderer_preflight_performed": True, "stage12641_canonical_curriculum_renderer_independent_review_allowed": True, "vm_branch_remains_paused": True}
    check_false(pointer, "stage12640_pointer"); assert_public_sanitized(pointer, "stage12640_pointer")
    write_json(out / "contract.json", contract); write_json(out / "digest_pointer.json", pointer); write_json(out / "canonical_renderer_card.json", card)
    write_jsonl(out / "private/canonical_candidate_curriculum_rows_preflight.jsonl", rendered_rows)
    write_json(out / "private/canonical_curriculum_renderer_preflight_only.json", private)
    write_json(out / "summary.json", summary); write_json(summary_path, summary)
    fsync_dir(out / "private"); fsync_dir(out); fsync_dir(summary_path.parent)
    return summary

if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
