#!/usr/bin/env python3
"""Build Stage12412 raw-private Open-SWE semantic reviewer returns.

This stage may inspect raw private parquet rows internally for the Stage12411
allowlisted requests whose Stage12410 private locator hash matches. Public
artifacts emit only hashes, classes, statuses, counts, and zero-admission
guardrail flags. It never executes replay, applies patches, runs tests, or
admits training/eval/Level-3/patch-trace rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12412_open_swe_raw_private_semantic_reviewer"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12411_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12411_open_swe_row_lineage_repaired_replay_requests/"
    "open_swe_row_lineage_repaired_replay_requests.jsonl"
)
STAGE12410_PRIVATE = (
    ROOT
    / "runs/local/private/stage12410_private_open_swe_locator_index_preflight_qc/"
    "open_swe_raw_locator_index.private.jsonl"
)

ROWS_NAME = "open_swe_raw_private_semantic_review_returns.jsonl"
LOCAL_SUMMARY_NAME = "open_swe_raw_private_semantic_review_summary.json"
GUARDRAIL_NAME = "guardrail_scan.json"
SAFE_SCHEMA = "stage12412_safe_raw_private_semantic_review_return_v1"

ALLOWED_SEMANTIC_STATUSES = {
    "blocked_allowlist_miss",
    "blocked_private_locator_mismatch",
    "blocked_raw_row_not_found",
    "blocked_raw_read_error",
    "blocked_required_safe_evidence_missing",
    "blocked_semantic_proofs_incomplete",
    "blocked_uncertain_fail_closed",
    "reviewed_hash_only_semantic_proofs_complete_no_admission",
    "hard_rejected_raw_leak",
    "hard_rejected_execution_or_training_claim",
}

REQUESTED_SAFE_RETURN_SCHEMA = [
    "state_before_identity_hash",
    "chosen_action_ref_hash",
    "observation_ref_hash",
    "verifier_identity_hash",
    "verifier_output_class",
    "patch_application_status",
    "state_after_identity_hash",
    "stop_continue_status",
    "causal_linkage_status",
    "raw_content_policy",
]

PROOF_SLOTS = [
    "state_before",
    "action",
    "observation",
    "verifier_identity",
    "verifier_output_class",
    "patch_application",
    "causal_linkage",
    "state_after",
    "stop_continue",
    "correct_next_action_policy",
]

RAW_CONTENT_POLICY: dict[str, bool] = {
    "raw_parquet_row_read_internally_for_hash_only_review": False,
    "raw_parquet_row_content_emitted": False,
    "private_locator_values_emitted_publicly": False,
    "raw_trajectory_text_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_patches_emitted": False,
    "source_text_emitted": False,
    "absolute_paths_emitted": False,
    "raw_dataset_paths_emitted": False,
    "urls_emitted": False,
    "issue_bodies_emitted": False,
    "line_contents_emitted": False,
    "patch_diffs_emitted": False,
}

CLAIM_BOUNDARY: dict[str, bool | str] = {
    "boundary": "raw_private_hash_only_semantic_review_no_replay_no_admission",
    "raw_locator_emitted": False,
    "raw_row_content_emitted": False,
    "replay_executed": False,
    "patch_applied": False,
    "tests_run": False,
    "training_claim": False,
    "eval_claim": False,
    "admission_claim": False,
    "level3_claim": False,
    "repair_claim": False,
    "fail_to_pass_claim": False,
    "patch_trace_claim": False,
}

ZERO_ADMISSION_FLAGS: dict[str, bool | int] = {
    "admission": False,
    "training_allowed": False,
    "training_row_count": 0,
    "eval_row_count": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "patch_trace_admitted": 0,
    "repair_claim_admitted": 0,
    "fail_to_pass_claim_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
}

SAFE_MARKERS = {
    "PASSED": "verifier_pass_marker",
    "FAILED": "verifier_fail_marker",
    "ERROR": "verifier_error_marker",
    "Traceback": "traceback_marker",
    "AssertionError": "assertion_marker",
    "pytest": "pytest_marker",
    "mvn test": "maven_test_marker",
    "cargo test": "cargo_test_marker",
    "npm test": "npm_test_marker",
}

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
MULTILINE_RE = re.compile(r"[\r\n]")
DIFF_RE = re.compile(r"diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|\*\*\* Begin Patch", re.MULTILINE)
HEX_RE = re.compile(r"^[0-9a-f]{12,64}$")
RAW_KEY_RE = re.compile(
    r"(?:^|_)(trajectory|command|output|stdout|stderr|source_text|issue_body|line_content|url|path)(?:$|_)",
    re.IGNORECASE,
)
SAFE_KEY_CONTEXT_RE = re.compile(
    r"(?:status|code|codes|proof|gate|hash|hashes|class|classes|signal|policy|count|counts|bucket|ref|refs|emitted|allowed|stage|schema|boundary|flags)",
    re.IGNORECASE,
)
FORBIDDEN_PUBLIC_KEYS = {
    "source_record_ref",
    "dataset_file",
    "instance_id",
    "trajectory_id",
    "raw_path",
    "url",
    "command_text",
    "stdout",
    "stderr",
    "issue_body",
    "source_text",
    "line_content",
    "raw_parquet_row_content",
    "raw_row",
    "verifier_command",
}


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    if not path.exists():
        return rows, [f"missing_input_{path.name}"]
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                issues.append(f"{path.name}_line_{line_number}_invalid_json")
                continue
            if not isinstance(value, dict):
                issues.append(f"{path.name}_line_{line_number}_not_object")
                continue
            rows.append(value)
    return rows, issues


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def private_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("source_record_ref_hash") or ""): row for row in rows if row.get("source_record_ref_hash")}


def marker_classes_for_text(text: str) -> list[str]:
    return sorted({klass for marker, klass in SAFE_MARKERS.items() if marker in text})


def role_class(turn: dict[str, Any]) -> str:
    role = str(turn.get("role") or "unknown").lower()
    if role in {"system", "user", "assistant", "tool"}:
        return f"role_{role}"
    return "role_other"


def classify_tool_name(name: str) -> str:
    lowered = name.lower()
    if any(token in lowered for token in ("bash", "shell", "terminal", "exec")):
        return "shell_tool_call"
    if any(token in lowered for token in ("edit", "patch", "write", "replace")):
        return "file_mutation_tool_call"
    if any(token in lowered for token in ("read", "open", "view", "grep", "search")):
        return "file_inspection_tool_call"
    return "other_tool_call"


def event_classes(turn: dict[str, Any]) -> dict[str, Any]:
    content = str(turn.get("content") or "")
    markers = marker_classes_for_text(content)
    calls = turn.get("tool_calls") if isinstance(turn.get("tool_calls"), list) else []
    call_classes: list[str] = []
    for call in calls:
        function = call.get("function") if isinstance(call, dict) else {}
        call_classes.append(classify_tool_name(str((function or {}).get("name") or "")))
    action_class = "no_tool_call_action"
    if call_classes:
        unique = sorted(set(call_classes))
        action_class = unique[0] if len(unique) == 1 else "mixed_tool_call_action"
    elif str(turn.get("role") or "").lower() == "tool":
        action_class = "tool_observation"

    status_class = "status_not_observation"
    if str(turn.get("role") or "").lower() == "tool":
        present = set(markers)
        if {"verifier_pass_marker", "verifier_fail_marker"} <= present:
            status_class = "mixed_pass_fail_observation_marker"
        elif {"verifier_pass_marker", "verifier_error_marker"} <= present:
            status_class = "mixed_pass_error_observation_marker"
        elif "verifier_pass_marker" in present:
            status_class = "pass_observation_marker_not_correctness"
        elif "verifier_fail_marker" in present:
            status_class = "fail_observation_marker_not_correctness"
        elif "verifier_error_marker" in present:
            status_class = "error_observation_marker_not_correctness"
        elif present:
            status_class = "nonverifier_observation_marker"
        else:
            status_class = "observation_marker_absent"

    lowered = content.lower()
    patch_signal_class = "patch_signal_absent"
    if "file_mutation_tool_call" in call_classes:
        patch_signal_class = "patch_tool_call_class_present_not_apply_proof"
    elif "diff --git" in lowered or "*** begin patch" in lowered:
        patch_signal_class = "patch_body_marker_present_not_apply_proof"

    verifier_signal_class = "verifier_signal_absent"
    present = set(markers)
    if {"verifier_pass_marker", "verifier_fail_marker"} <= present:
        verifier_signal_class = "mixed_pass_fail_marker_not_causality"
    elif "verifier_pass_marker" in present:
        verifier_signal_class = "pass_marker_not_correctness_proof"
    elif "verifier_fail_marker" in present:
        verifier_signal_class = "fail_marker_not_correctness_proof"
    elif "verifier_error_marker" in present:
        verifier_signal_class = "error_marker_not_correctness_proof"
    elif present:
        verifier_signal_class = "nonverifier_marker_present"

    return {
        "role_class": role_class(turn),
        "action_class": action_class,
        "status_class": status_class,
        "patch_signal_class": patch_signal_class,
        "verifier_signal_class": verifier_signal_class,
        "marker_classes": markers,
        "tool_call_class_count": len(call_classes),
        "has_tool_call_count": int(bool(call_classes)),
        "has_tool_observation_count": int(str(turn.get("role") or "").lower() == "tool"),
    }


def safe_event_signature(turn: dict[str, Any], ordinal: int) -> dict[str, Any]:
    classes = event_classes(turn)
    content = str(turn.get("content") or "")
    return {
        "ordinal_hash": stable_hash(ordinal, 16),
        "role_class": classes["role_class"],
        "action_class": classes["action_class"],
        "status_class": classes["status_class"],
        "patch_signal_class": classes["patch_signal_class"],
        "verifier_signal_class": classes["verifier_signal_class"],
        "marker_classes": classes["marker_classes"],
        "content_ref_hash": stable_hash(content, 24) if content else "missing",
        "tool_call_class_count": classes["tool_call_class_count"],
        "has_tool_call_count": classes["has_tool_call_count"],
        "has_tool_observation_count": classes["has_tool_observation_count"],
    }


def bucket_count(count: int) -> str:
    if count <= 0:
        return "none"
    if count == 1:
        return "one"
    if count <= 3:
        return "two_to_three"
    if count <= 8:
        return "four_to_eight"
    if count <= 32:
        return "nine_to_thirty_two"
    return "many"


def read_private_raw_row(locator: dict[str, Any]) -> tuple[dict[str, Any], str]:
    ref = locator.get("source_record_ref") if isinstance(locator.get("source_record_ref"), dict) else {}
    dataset_file = ref.get("dataset_file")
    if not dataset_file:
        return {}, "blocked_raw_read_error_private_locator_missing_dataset_file"
    parquet_path = Path(str(dataset_file))
    if not parquet_path.exists():
        return {}, "blocked_raw_read_error_private_dataset_file_unavailable"
    try:
        import pyarrow.parquet as pq  # type: ignore
    except Exception:
        return {}, "blocked_raw_read_error_pyarrow_unavailable"

    wanted_instance = ref.get("instance_id")
    wanted_trajectory = ref.get("trajectory_id")
    if not wanted_instance or not wanted_trajectory:
        return {}, "blocked_raw_read_error_private_locator_missing_row_keys"

    try:
        parquet_file = pq.ParquetFile(parquet_path)
        available = set(parquet_file.schema_arrow.names)
        columns = [
            column
            for column in ["instance_id", "trajectory_id", "trajectory", "model_patch", "resolved", "metadata"]
            if column in available
        ]
        if "instance_id" not in available or "trajectory_id" not in available:
            return {}, "blocked_raw_read_error_required_locator_columns_missing"
        table = pq.read_table(
            parquet_path,
            columns=columns,
            filters=[
                ("instance_id", "=", wanted_instance),
                ("trajectory_id", "=", wanted_trajectory),
            ],
        )
    except Exception:
        return {}, "blocked_raw_read_error_private_parquet_read_failed"

    for record in table.to_pylist():
        if record.get("instance_id") == wanted_instance and record.get("trajectory_id") == wanted_trajectory:
            return record, "raw_private_row_read_internal_hash_only"
    return {}, "blocked_raw_row_not_found"


def nearest_event_index(
    signatures: list[dict[str, Any]],
    anchor: int,
    predicate_key: str,
    absent_value: str,
) -> int | None:
    if not signatures:
        return None
    bounded_anchor = max(0, min(anchor, len(signatures) - 1))
    offsets = list(range(0, len(signatures)))
    candidates: list[int] = []
    for offset in offsets:
        for index in (bounded_anchor - offset, bounded_anchor + offset):
            if 0 <= index < len(signatures):
                candidates.append(index)
        for index in candidates:
            if signatures[index].get(predicate_key) != absent_value:
                return index
        candidates.clear()
    return None


def bounded_counts(signatures: list[dict[str, Any]]) -> dict[str, Any]:
    counters: dict[str, Counter[str]] = {
        "role_class_counts": Counter(),
        "action_class_counts": Counter(),
        "status_class_counts": Counter(),
        "patch_signal_class_counts": Counter(),
        "verifier_signal_class_counts": Counter(),
    }
    tool_call_count = 0
    tool_observation_count = 0
    for signature in signatures:
        counters["role_class_counts"][str(signature.get("role_class") or "missing")] += 1
        counters["action_class_counts"][str(signature.get("action_class") or "missing")] += 1
        counters["status_class_counts"][str(signature.get("status_class") or "missing")] += 1
        counters["patch_signal_class_counts"][str(signature.get("patch_signal_class") or "missing")] += 1
        counters["verifier_signal_class_counts"][str(signature.get("verifier_signal_class") or "missing")] += 1
        tool_call_count += int(signature.get("has_tool_call_count") or 0)
        tool_observation_count += int(signature.get("has_tool_observation_count") or 0)
    return {
        "raw_private_event_count": len(signatures),
        "raw_private_event_count_bucket_class": bucket_count(len(signatures)),
        "tool_call_count": tool_call_count,
        "tool_observation_count": tool_observation_count,
        **{key: dict(sorted(counter.items())) for key, counter in counters.items()},
    }


def model_patch_signal_counts(model_patch: Any) -> dict[str, Any]:
    if not isinstance(model_patch, str) or not model_patch:
        return {
            "model_patch_signal_present_count": 0,
            "model_patch_modified_file_count_bucket_class": "none",
            "model_patch_line_count_bucket_class": "none",
        }
    modified_file_count = len({match for match in re.findall(r"^diff --git\s+a/\S+\s+b/\S+", model_patch, re.MULTILINE)})
    return {
        "model_patch_signal_present_count": 1,
        "model_patch_modified_file_count_bucket_class": bucket_count(modified_file_count),
        "model_patch_line_count_bucket_class": bucket_count(len(model_patch.splitlines())),
    }


def metadata_signal_counts(metadata: Any) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {
            "metadata_present_count": 0,
            "metadata_category_present_count": 0,
            "metadata_category_hash": "missing",
        }
    category = metadata.get("category")
    return {
        "metadata_present_count": 1,
        "metadata_category_present_count": int(category is not None),
        "metadata_category_hash": stable_hash(category, 24) if category is not None else "missing",
    }


def build_safe_proofs(request: dict[str, Any], raw_row: dict[str, Any]) -> dict[str, Any]:
    trajectory = raw_row.get("trajectory")
    turns = [turn for turn in trajectory if isinstance(turn, dict)] if isinstance(trajectory, list) else []
    signatures = [safe_event_signature(turn, ordinal) for ordinal, turn in enumerate(turns)]
    anchor = int(request.get("window_anchor_ordinal") or 0)
    bounded_anchor = max(0, min(anchor, len(signatures) - 1)) if signatures else 0
    patch_index = nearest_event_index(signatures, bounded_anchor, "patch_signal_class", "patch_signal_absent")
    verifier_index = nearest_event_index(signatures, bounded_anchor, "verifier_signal_class", "verifier_signal_absent")
    observation_index = nearest_event_index(signatures, bounded_anchor, "status_class", "status_not_observation")

    state_before_basis = {
        "source_record_ref_hash": request.get("source_record_ref_hash") or "missing",
        "trajectory_ref_hash": request.get("trajectory_ref_hash") or "missing",
        "prefix_digest_hash": stable_hash(signatures[:bounded_anchor], 24) if signatures else "missing",
    }
    state_after_basis = {
        "source_record_ref_hash": request.get("source_record_ref_hash") or "missing",
        "trajectory_ref_hash": request.get("trajectory_ref_hash") or "missing",
        "suffix_digest_hash": stable_hash(signatures[bounded_anchor:], 24) if signatures else "missing",
        "resolved_metadata_present_count": int(raw_row.get("resolved") is not None),
    }

    chosen_action_ref_hash = "missing"
    if patch_index is not None:
        chosen_action_ref_hash = stable_hash(signatures[patch_index], 24)
    elif signatures:
        chosen_action_ref_hash = stable_hash(signatures[bounded_anchor], 24)

    observation_ref_hash = "missing"
    if observation_index is not None:
        observation_ref_hash = str(signatures[observation_index].get("content_ref_hash") or "missing")

    verifier_identity_hash = "missing"
    verifier_output_class = "verifier_signal_absent"
    if verifier_index is not None:
        verifier_signature = signatures[verifier_index]
        verifier_identity_hash = stable_hash(
            {
                "role_class": verifier_signature.get("role_class"),
                "status_class": verifier_signature.get("status_class"),
                "verifier_signal_class": verifier_signature.get("verifier_signal_class"),
                "marker_classes": verifier_signature.get("marker_classes"),
            },
            24,
        )
        verifier_output_class = str(verifier_signature.get("status_class") or "unknown")

    patch_application_status = "patch_application_not_proven"
    if patch_index is not None:
        patch_application_status = str(signatures[patch_index].get("patch_signal_class") or "patch_signal_present_not_apply_proof")

    causal_linkage_status = "causal_linkage_not_proven"
    if patch_index is not None and verifier_index is not None:
        causal_linkage_status = (
            "patch_and_verifier_co_present_ordered_not_causal_proof"
            if patch_index <= verifier_index
            else "verifier_before_patch_not_causal_proof"
        )
    elif patch_index is not None:
        causal_linkage_status = "patch_signal_without_verifier_signal_not_causal_proof"
    elif verifier_index is not None:
        causal_linkage_status = "verifier_signal_without_patch_signal_not_causal_proof"

    stop_continue_status = "stop_continue_not_authoritatively_proven"
    if signatures and bounded_anchor >= len(signatures) - 1:
        stop_continue_status = "terminal_window_position_not_policy_proof"

    return {
        "state_before_identity_hash": "missing",
        "chosen_action_ref_hash": chosen_action_ref_hash,
        "observation_ref_hash": observation_ref_hash,
        "verifier_identity_hash": verifier_identity_hash,
        "verifier_output_class": verifier_output_class,
        "patch_application_status": patch_application_status,
        "state_after_identity_hash": "missing",
        "stop_continue_status": stop_continue_status,
        "causal_linkage_status": causal_linkage_status,
        "raw_private_bounded_counts": {
            **bounded_counts(signatures),
            **model_patch_signal_counts(raw_row.get("model_patch")),
            **metadata_signal_counts(raw_row.get("metadata")),
            "resolved_signal_present_count": int(raw_row.get("resolved") is not None),
        },
        "raw_row_hash_only_digest": stable_hash(
            {
                "source_record_ref_hash": request.get("source_record_ref_hash") or "missing",
                "event_signature_digest_hash": stable_hash(signatures, 24),
                "model_patch_ref_hash_present_count": int(bool(raw_row.get("model_patch"))),
                "resolved_metadata_present_count": int(raw_row.get("resolved") is not None),
            },
            24,
        ),
    }


def proof_slots_for(proofs: dict[str, Any], raw_status: str) -> dict[str, dict[str, Any]]:
    field_by_slot = {
        "state_before": "state_before_identity_hash",
        "action": "chosen_action_ref_hash",
        "observation": "observation_ref_hash",
        "verifier_identity": "verifier_identity_hash",
        "verifier_output_class": "verifier_output_class",
        "patch_application": "patch_application_status",
        "causal_linkage": "causal_linkage_status",
        "state_after": "state_after_identity_hash",
        "stop_continue": "stop_continue_status",
        "correct_next_action_policy": "stop_continue_status",
    }
    slots: dict[str, dict[str, Any]] = {}
    raw_read = raw_status == "raw_private_row_read_internal_hash_only"
    for slot in PROOF_SLOTS:
        field = field_by_slot[slot]
        value = proofs.get(field, "missing")
        has_safe_field = value not in (None, "", "missing", "verifier_signal_absent")
        status = "safe_hash_or_class_present_not_admission_proof" if raw_read and has_safe_field else "blocked_required_safe_evidence_missing"
        if slot in {"patch_application", "causal_linkage", "stop_continue", "correct_next_action_policy"} and has_safe_field:
            status = f"{slot}_not_authoritatively_proven_fail_closed"
        slots[slot] = {
            "proof_status": status,
            "proof_proven": False,
            "proof_ref_hash": stable_hash({"slot": slot, "field": field, "value": value}, 24) if has_safe_field else "missing",
            "evidence_class": "hash_class_status_only_raw_private_inspection_not_replay_proof",
            "status_code": status,
        }
    return slots


def hard_reject_reasons_for(request: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if request.get("execution_attempt_status") not in {None, "not_attempted"}:
        reasons.append("hard_reject_execution_attempt_claim")
    if request.get("replay_outcome_status") not in {None, "not_run"}:
        reasons.append("hard_reject_replay_outcome_claim")
    zero_flags = request.get("zero_admission_flags") if isinstance(request.get("zero_admission_flags"), dict) else {}
    for key, expected in ZERO_ADMISSION_FLAGS.items():
        if zero_flags.get(key, expected) != expected:
            reasons.append(f"hard_reject_nonzero_{key}")
    for key in ("level3_status", "target_next_stage"):
        value = str(request.get(key) or "")
        if "admitted" in value.lower() or "training" in value.lower():
            reasons.append(f"hard_reject_overclaim_{key}")
    return sorted(set(reasons))


def build_blocked_proofs() -> dict[str, Any]:
    return {
        "state_before_identity_hash": "missing",
        "chosen_action_ref_hash": "missing",
        "observation_ref_hash": "missing",
        "verifier_identity_hash": "missing",
        "verifier_output_class": "missing",
        "patch_application_status": "blocked_no_raw_private_semantic_inspection",
        "state_after_identity_hash": "missing",
        "stop_continue_status": "blocked_no_raw_private_semantic_inspection",
        "causal_linkage_status": "blocked_no_raw_private_semantic_inspection",
        "raw_private_bounded_counts": {
            "raw_private_event_count": 0,
            "raw_private_event_count_bucket_class": "none",
            "tool_call_count": 0,
            "tool_observation_count": 0,
            "role_class_counts": {},
            "action_class_counts": {},
            "status_class_counts": {},
            "patch_signal_class_counts": {},
            "verifier_signal_class_counts": {},
        },
        "raw_row_hash_only_digest": "missing",
    }


def choose_semantic_status(
    *,
    allowlist_match: bool,
    locator_match: bool,
    raw_status: str,
    hard_rejects: list[str],
    proofs: dict[str, Any],
    slots: dict[str, dict[str, Any]],
) -> str:
    if hard_rejects:
        return "hard_rejected_execution_or_training_claim"
    if not allowlist_match:
        return "blocked_allowlist_miss"
    if not locator_match:
        return "blocked_private_locator_mismatch"
    if raw_status == "blocked_raw_row_not_found":
        return "blocked_raw_row_not_found"
    if raw_status.startswith("blocked_raw_read_error"):
        return "blocked_raw_read_error"
    missing_safe = any(proofs.get(field) in (None, "", "missing") for field in REQUESTED_SAFE_RETURN_SCHEMA if field != "raw_content_policy")
    if missing_safe:
        return "blocked_required_safe_evidence_missing"
    incomplete = any(not bool(slot.get("proof_proven")) for slot in slots.values())
    if incomplete:
        return "blocked_semantic_proofs_incomplete"
    return "reviewed_hash_only_semantic_proofs_complete_no_admission"


def build_row(
    request: dict[str, Any],
    locator_by_source_hash: dict[str, dict[str, Any]],
    allowlist: set[str],
) -> tuple[dict[str, Any], int]:
    repair_request_id = str(request.get("repair_request_id") or "missing")
    request_hash = stable_hash(repair_request_id, 24)
    source_ref_hash = str(request.get("source_record_ref_hash") or "missing")
    stage12411_locator_ref_hash = str(request.get("private_locator_ref_hash") or "missing")
    locator = locator_by_source_hash.get(source_ref_hash, {})
    computed_locator_ref_hash = stable_hash(locator.get("private_locator_id") if locator else "missing", 24)
    allowlist_match = repair_request_id in allowlist
    locator_match = bool(locator) and computed_locator_ref_hash == stage12411_locator_ref_hash
    hard_rejects = hard_reject_reasons_for(request)

    proofs = build_blocked_proofs()
    raw_status = "blocked_allowlist_miss"
    raw_rows_read = 0
    if allowlist_match and not locator_match:
        raw_status = "blocked_private_locator_mismatch"
    elif allowlist_match and locator_match and not hard_rejects:
        raw_row, raw_status = read_private_raw_row(locator)
        if raw_status == "raw_private_row_read_internal_hash_only":
            raw_rows_read = 1
            proofs = build_safe_proofs(request, raw_row)

    slots = proof_slots_for(proofs, raw_status)
    semantic_status = choose_semantic_status(
        allowlist_match=allowlist_match,
        locator_match=locator_match,
        raw_status=raw_status,
        hard_rejects=hard_rejects,
        proofs=proofs,
        slots=slots,
    )
    if semantic_status not in ALLOWED_SEMANTIC_STATUSES:
        semantic_status = "blocked_uncertain_fail_closed"

    blockers = set(str(blocker) for blocker in request.get("blockers", []) if isinstance(blocker, str))
    blockers.update(
        {
            "no_replay_executed",
            "no_patch_apply_executed",
            "no_tests_run",
            "raw_private_hash_only_review_is_not_training_admission",
            "raw_parquet_row_read_is_not_replay_proof",
            "fail_closed_until_authoritative_state_patch_verifier_causality_proven",
        }
    )
    if semantic_status.startswith("blocked") or semantic_status.startswith("hard_rejected"):
        blockers.add(semantic_status)
    blockers.update(hard_rejects)

    raw_policy = dict(RAW_CONTENT_POLICY)
    raw_policy["raw_parquet_row_read_internally_for_hash_only_review"] = bool(raw_rows_read)

    row: dict[str, Any] = {
        "record_type": "open_swe_raw_private_semantic_review_return",
        "stage": STAGE,
        "safe_schema_version": SAFE_SCHEMA,
        "repair_request_id": repair_request_id,
        "stage12411_request_hash": request_hash,
        "source_record_ref_hash": source_ref_hash,
        "private_locator_ref_hash": stage12411_locator_ref_hash,
        "dataset_file_hash": str(request.get("dataset_file_hash") or locator.get("dataset_file_hash") or "missing"),
        "instance_ref_hash": str(request.get("instance_ref_hash") or locator.get("instance_ref_hash") or "missing"),
        "trajectory_ref_hash": str(request.get("trajectory_ref_hash") or locator.get("trajectory_ref_hash") or "missing"),
        "language_family": str(request.get("language_family") or locator.get("language_family") or "unknown"),
        "repo_family_hash": str(request.get("repo_family_hash") or locator.get("repo_family_hash") or "missing"),
        "semantic_review_status": semantic_status,
        "raw_private_inspection_status": raw_status,
        "allowlist_match_status": "stage12411_allowlist_match" if allowlist_match else "stage12411_allowlist_miss",
        "private_locator_match_status": "private_locator_hash_matched" if locator_match else "private_locator_hash_mismatch",
        "hard_reject_reasons": hard_rejects,
        "blockers": sorted(blockers),
        "state_before_identity_hash": proofs["state_before_identity_hash"],
        "chosen_action_ref_hash": proofs["chosen_action_ref_hash"],
        "observation_ref_hash": proofs["observation_ref_hash"],
        "verifier_identity_hash": proofs["verifier_identity_hash"],
        "verifier_output_class": proofs["verifier_output_class"],
        "patch_application_status": proofs["patch_application_status"],
        "state_after_identity_hash": proofs["state_after_identity_hash"],
        "stop_continue_status": proofs["stop_continue_status"],
        "causal_linkage_status": proofs["causal_linkage_status"],
        "requested_safe_return_schema_hash": stable_hash(request.get("requested_safe_return_schema") or REQUESTED_SAFE_RETURN_SCHEMA, 24),
        "requested_safe_return_schema_status": (
            "stage12411_requested_safe_return_schema_matched"
            if request.get("requested_safe_return_schema") == REQUESTED_SAFE_RETURN_SCHEMA
            else "stage12411_requested_safe_return_schema_mismatch"
        ),
        "required_safe_proof_field_count": len(REQUESTED_SAFE_RETURN_SCHEMA),
        "safe_proof_field_present_count": sum(
            1
            for field in REQUESTED_SAFE_RETURN_SCHEMA
            if field == "raw_content_policy" or proofs.get(field) not in (None, "", "missing")
        ),
        "raw_private_bounded_counts": proofs["raw_private_bounded_counts"],
        "raw_row_hash_only_digest": proofs["raw_row_hash_only_digest"],
        "raw_content_policy": raw_policy,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
        "proof_slot_statuses": slots,
    }
    return row, raw_rows_read


def validate_row(row: dict[str, Any], row_index: int) -> list[str]:
    issues: list[str] = []
    required = [
        "record_type",
        "stage",
        "safe_schema_version",
        "repair_request_id",
        "stage12411_request_hash",
        "source_record_ref_hash",
        "private_locator_ref_hash",
        "dataset_file_hash",
        "instance_ref_hash",
        "trajectory_ref_hash",
        "language_family",
        "repo_family_hash",
        "semantic_review_status",
        "raw_private_inspection_status",
        "allowlist_match_status",
        "hard_reject_reasons",
        "blockers",
        *REQUESTED_SAFE_RETURN_SCHEMA,
        "claim_boundary",
        "zero_admission_flags",
        "proof_slot_statuses",
    ]
    for key in required:
        if key not in row:
            issues.append(f"row_{row_index}_missing_{key}")
    if row.get("safe_schema_version") != SAFE_SCHEMA:
        issues.append(f"row_{row_index}_safe_schema_version_mismatch")
    if row.get("semantic_review_status") not in ALLOWED_SEMANTIC_STATUSES:
        issues.append(f"row_{row_index}_semantic_review_status_not_allowed")
    for key, expected in ZERO_ADMISSION_FLAGS.items():
        if row.get("zero_admission_flags", {}).get(key) != expected:
            issues.append(f"row_{row_index}_zero_admission_{key}_mismatch")
    for key, expected in CLAIM_BOUNDARY.items():
        if row.get("claim_boundary", {}).get(key) != expected:
            issues.append(f"row_{row_index}_claim_boundary_{key}_mismatch")
    for key, expected in RAW_CONTENT_POLICY.items():
        if key == "raw_parquet_row_read_internally_for_hash_only_review":
            continue
        if row.get("raw_content_policy", {}).get(key) != expected:
            issues.append(f"row_{row_index}_raw_content_policy_{key}_mismatch")
    if sorted(row.get("proof_slot_statuses", {})) != sorted(PROOF_SLOTS):
        issues.append(f"row_{row_index}_proof_slot_set_mismatch")
    for slot, proof in (row.get("proof_slot_statuses") or {}).items():
        if proof.get("proof_proven") is not False:
            issues.append(f"row_{row_index}_proof_slot_{slot}_proven_overclaim")
    for key in ("stage12411_request_hash", "source_record_ref_hash", "private_locator_ref_hash", "dataset_file_hash", "instance_ref_hash", "trajectory_ref_hash", "repo_family_hash"):
        value = row.get(key)
        if value != "missing" and not (isinstance(value, str) and HEX_RE.match(value)):
            issues.append(f"row_{row_index}_{key}_not_hash")
    return issues


def scan_value(value: Any, artifact: str, issues: list[dict[str, Any]], key_path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{key_path}.{key}" if key_path else str(key)
            if str(key) in FORBIDDEN_PUBLIC_KEYS:
                issues.append({"artifact": artifact, "issue": "forbidden_public_key", "key_hash": stable_hash(child_path, 16)})
            if (
                RAW_KEY_RE.search(str(key))
                and not SAFE_KEY_CONTEXT_RE.search(str(key))
                and isinstance(child, str)
                and child
                and not HEX_RE.match(child)
            ):
                issues.append({"artifact": artifact, "issue": "raw_like_key_with_string_value", "key_hash": stable_hash(child_path, 16)})
            scan_value(child, artifact, issues, child_path)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            scan_value(child, artifact, issues, f"{key_path}[{index}]")
        return
    if not isinstance(value, str):
        return
    if ABS_PATH_RE.search(value):
        issues.append({"artifact": artifact, "issue": "absolute_path_string", "key_hash": stable_hash(key_path, 16)})
    if URL_RE.search(value):
        issues.append({"artifact": artifact, "issue": "url_string", "key_hash": stable_hash(key_path, 16)})
    if MULTILINE_RE.search(value):
        issues.append({"artifact": artifact, "issue": "multiline_string", "key_hash": stable_hash(key_path, 16)})
    if DIFF_RE.search(value):
        issues.append({"artifact": artifact, "issue": "diff_like_string", "key_hash": stable_hash(key_path, 16)})
    if key_path.endswith("_hash") and value != "missing" and not HEX_RE.match(value):
        issues.append({"artifact": artifact, "issue": "non_hash_value_in_hash_field", "key_hash": stable_hash(key_path, 16)})


def guardrail_scan(paths: list[Path]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    parsed_json_values = 0
    scanned_jsonl_rows = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if ABS_PATH_RE.search(text):
            issues.append({"artifact": path.name, "issue": "absolute_path_pattern"})
        if URL_RE.search(text):
            issues.append({"artifact": path.name, "issue": "url_pattern"})
        if DIFF_RE.search(text):
            issues.append({"artifact": path.name, "issue": "diff_like_pattern"})
        if path.suffix == ".jsonl":
            for line_number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                scanned_jsonl_rows += 1
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    issues.append({"artifact": path.name, "issue": "invalid_jsonl", "line_count": line_number})
                    continue
                scan_value(value, path.name, issues, f"line[{line_number}]")
        else:
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                issues.append({"artifact": path.name, "issue": "invalid_json"})
                continue
            parsed_json_values += 1
            scan_value(value, path.name, issues)
    return {
        "scan_passed": not issues,
        "issues": issues,
        "scanned_artifact_count": len(paths),
        "parsed_json_values": parsed_json_values,
        "scanned_jsonl_rows": scanned_jsonl_rows,
    }


def proof_slot_status_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        slots = row.get("proof_slot_statuses") if isinstance(row.get("proof_slot_statuses"), dict) else {}
        for slot, proof in slots.items():
            counts[str(slot)][str(proof.get("proof_status") or "missing")] += 1
    return {slot: dict(sorted(counter.items())) for slot, counter in sorted(counts.items())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12411_rows, input_issues = read_jsonl(STAGE12411_ROWS)
    private_rows, private_issues = read_jsonl(STAGE12410_PRIVATE)
    input_issues.extend(private_issues)
    locator_by_source_hash = private_index(private_rows)
    allowlist = {str(row.get("repair_request_id") or "") for row in stage12411_rows if row.get("repair_request_id")}

    rows: list[dict[str, Any]] = []
    raw_rows_read = 0
    for request in stage12411_rows:
        row, read_count = build_row(request, locator_by_source_hash, allowlist)
        rows.append(row)
        raw_rows_read += read_count

    rows_path = OUT / ROWS_NAME
    local_summary_path = OUT / LOCAL_SUMMARY_NAME
    guardrail_path = OUT / GUARDRAIL_NAME
    write_jsonl(rows_path, rows)

    schema_issues = input_issues + [issue for index, row in enumerate(rows, 1) for issue in validate_row(row, index)]
    status_counts = Counter(str(row.get("semantic_review_status") or "missing") for row in rows)
    raw_status_counts = Counter(str(row.get("raw_private_inspection_status") or "missing") for row in rows)
    allowlist_counts = Counter(str(row.get("allowlist_match_status") or "missing") for row in rows)
    locator_counts = Counter(str(row.get("private_locator_match_status") or "missing") for row in rows)
    language_counts = Counter(str(row.get("language_family") or "unknown") for row in rows)
    blocker_counts = Counter(str(blocker) for row in rows for blocker in row.get("blockers", []))
    hard_reject_count = sum(1 for row in rows if row.get("hard_reject_reasons"))
    overclaim_reject_count = sum(
        1
        for row in rows
        for reason in row.get("hard_reject_reasons", [])
        if "claim" in str(reason) or "nonzero" in str(reason)
    )

    summary: dict[str, Any] = {
        "stage": STAGE,
        "record_type": "open_swe_raw_private_semantic_review_summary",
        "decision": "fail_closed_raw_private_semantic_review_zero_admission",
        "safe_schema_version": SAFE_SCHEMA,
        "input_stage12411_rows": len(stage12411_rows),
        "input_stage12410_private_locator_rows": len(private_rows),
        "allowlisted_request_rows": len(allowlist),
        "private_locator_matched_rows": locator_counts.get("private_locator_hash_matched", 0),
        "raw_parquet_rows_read_internal_count": raw_rows_read,
        "raw_content_emitted_count": 0,
        "raw_leak_count": 0,
        "replay_attempted_count": 0,
        "patch_apply_attempted_count": 0,
        "tests_run_count": 0,
        "admitted_rows": 0,
        "training_allowed": False,
        "training_row_count": 0,
        "eval_row_count": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "repair_claim_admitted": 0,
        "fail_to_pass_claim_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "semantic_review_status_counts": dict(sorted(status_counts.items())),
        "raw_private_inspection_status_counts": dict(sorted(raw_status_counts.items())),
        "allowlist_match_status_counts": dict(sorted(allowlist_counts.items())),
        "private_locator_match_status_counts": dict(sorted(locator_counts.items())),
        "language_family_counts": dict(sorted(language_counts.items())),
        "proof_slot_status_counts": proof_slot_status_counts(rows),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "hard_reject_count": hard_reject_count,
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "overclaim_reject_count": overclaim_reject_count,
        "allowlist_miss_count": allowlist_counts.get("stage12411_allowlist_miss", 0),
        "private_locator_mismatch_count": locator_counts.get("private_locator_hash_mismatch", 0),
        "source_stage_artifact_hashes": {
            "stage12411_rows_hash": file_hash(STAGE12411_ROWS),
            "stage12410_private_locator_index_hash": file_hash(STAGE12410_PRIVATE),
        },
        "generated_artifact_count": 3,
        "generated_artifact_name_hashes": {
            "rows": stable_hash(ROWS_NAME, 24),
            "local_summary": stable_hash(LOCAL_SUMMARY_NAME, 24),
            "guardrail": stable_hash(GUARDRAIL_NAME, 24),
        },
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
        "guardrail_scan": None,
        "guardrail_issue_count": 0,
        "raw_leak_findings": [],
    }
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)

    guardrail = guardrail_scan([rows_path, local_summary_path, SUMMARY])
    write_json(guardrail_path, guardrail)
    summary["guardrail_scan"] = guardrail
    summary["guardrail_issue_count"] = len(guardrail["issues"])
    summary["raw_leak_findings"] = guardrail["issues"]
    summary["raw_leak_count"] = len(guardrail["issues"])
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)

    if schema_issues or guardrail["issues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
