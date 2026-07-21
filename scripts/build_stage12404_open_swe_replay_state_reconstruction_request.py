#!/usr/bin/env python3
"""Stage12404 Open-SWE replay state reconstruction request.

Consumes Stage12403 replay-target windows, Stage12402 event digests, and
Stage12401 raw-private hydration preflight rows. Emits only a fail-closed
execution/reconstruction request for a capped, language/repo-diverse subset.
No replay is executed and no raw commands, outputs, paths, URLs, source text,
issue bodies, patch bodies/diffs, or line contents are emitted.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12404_open_swe_replay_state_reconstruction_request"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12403_WINDOWS = (
    ROOT
    / "runs/local/artifacts/stage12403_open_swe_event_digest_window_segmenter/"
    / "open_swe_event_digest_replay_target_windows.jsonl"
)
STAGE12403_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12403_open_swe_event_digest_window_segmenter/"
    / "open_swe_event_digest_window_segmenter_summary.json"
)
STAGE12402_DIGESTS = (
    ROOT
    / "runs/local/artifacts/stage12402_open_swe_private_event_digest_extractor/"
    / "open_swe_private_event_digests.jsonl"
)
STAGE12402_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12402_open_swe_private_event_digest_extractor/"
    / "open_swe_private_event_digest_summary.json"
)
STAGE12401_PREFLIGHT = (
    ROOT
    / "runs/local/artifacts/stage12401_open_swe_raw_private_hydration_preflight/"
    / "open_swe_raw_private_hydration_preflight.jsonl"
)
STAGE12401_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12401_open_swe_raw_private_hydration_preflight/"
    / "open_swe_raw_private_hydration_preflight_summary.json"
)

ROWS_NAME = "open_swe_replay_state_reconstruction_request_items.jsonl"
REQUEST_NAME = "open_swe_replay_state_reconstruction_request.json"
LOCAL_SUMMARY_NAME = "open_swe_replay_state_reconstruction_request_summary.json"
GUARDRAIL_NAME = "guardrail_scan.json"

MAX_REQUESTS = 14
MAX_REQUESTS_PER_LANGUAGE = 2
MAX_REQUESTS_PER_REPO = 1
REQUIRED_WINDOW_TYPE = "patch_verifier_co_presence_order_candidate_not_causality"

ZERO_ADMISSION_FLAGS: dict[str, int | bool] = {
    "admission": False,
    "training_allowed": False,
    "training_row_count": 0,
    "level3_admitted": 0,
    "patch_trace_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
    "repair_claim_admitted": 0,
    "transition_window_admitted": 0,
    "replay_target_admitted": 0,
    "reconstruction_request_admitted": 0,
}
RAW_CONTENT_POLICY: dict[str, bool] = {
    "raw_trajectory_text_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_patches_emitted": False,
    "source_text_emitted": False,
    "absolute_paths_emitted": False,
    "urls_emitted": False,
    "issue_bodies_emitted": False,
    "line_contents_emitted": False,
    "patch_diffs_emitted": False,
}
CLAIM_BOUNDARY: dict[str, bool] = {
    "execution_request_only": True,
    "replay_executed": False,
    "raw_private_content_emitted": False,
    "co_presence_order_candidate_only": True,
    "state_before_claim_emitted": False,
    "state_after_claim_emitted": False,
    "patch_application_claim_emitted": False,
    "verifier_relevance_claim_emitted": False,
    "causal_linkage_claim_emitted": False,
    "stop_continue_claim_emitted": False,
    "correct_next_action_policy_claim_emitted": False,
    "transition_proof_claim_emitted": False,
    "training_admission_claim_emitted": False,
}
PROOF_SLOT_STATUS = {
    "state_before": "blocked_missing_authoritative_state_before",
    "state_after": "blocked_missing_authoritative_state_after",
    "patch_application": "blocked_missing_patch_application_proof",
    "verifier_relevance": "blocked_missing_verifier_relevance_proof",
    "causal_linkage": "blocked_missing_causal_verifier_linkage",
    "stop_continue": "blocked_missing_stop_continue_proof",
    "correct_next_action_policy": "blocked_correct_next_action_not_authoritatively_proven",
}
REQUIRED_RECONSTRUCTION_TASKS = {
    "state_before": {
        "task_class": "recover_authoritative_state_before_identity",
        "required_safe_evidence": [
            "state_before_identity_hash",
            "state_before_file_set_hash",
            "state_before_dependency_fingerprint_hash",
        ],
        "accept_only_hash_class_count_status_code": True,
    },
    "state_after": {
        "task_class": "recover_authoritative_state_after_identity",
        "required_safe_evidence": [
            "state_after_identity_hash",
            "state_after_file_set_hash",
            "state_after_dependency_fingerprint_hash",
        ],
        "accept_only_hash_class_count_status_code": True,
    },
    "patch_application": {
        "task_class": "prove_patch_application_without_diff_body",
        "required_safe_evidence": [
            "patch_input_ref_hash",
            "patch_application_status_code",
            "changed_file_set_hash",
            "applied_change_digest_hash",
        ],
        "accept_only_hash_class_count_status_code": True,
    },
    "verifier_relevance": {
        "task_class": "prove_verifier_relevance_without_command_text",
        "required_safe_evidence": [
            "verifier_identity_hash",
            "verifier_scope_class",
            "verifier_target_set_hash",
            "verifier_status_code",
        ],
        "accept_only_hash_class_count_status_code": True,
    },
    "causal_linkage": {
        "task_class": "prove_patch_to_verifier_causal_linkage",
        "required_safe_evidence": [
            "before_status_code",
            "after_status_code",
            "same_verifier_identity_hash",
            "causal_linkage_status_code",
        ],
        "accept_only_hash_class_count_status_code": True,
    },
    "stop_continue": {
        "task_class": "recover_stop_continue_decision_boundary",
        "required_safe_evidence": [
            "terminal_event_ref_hash",
            "stop_continue_status_code",
            "next_action_policy_status_code",
        ],
        "accept_only_hash_class_count_status_code": True,
    },
    "correct_next_action_policy": {
        "task_class": "recover_correct_next_action_policy_boundary",
        "required_safe_evidence": [
            "state_before_identity_hash",
            "candidate_action_set_hash",
            "correct_policy_label_status_code",
            "policy_label_proof_hash",
        ],
        "accept_only_hash_class_count_status_code": True,
    },
}
ACCEPTANCE_CRITERIA = [
    "all_required_reconstruction_tasks_emit_safe_evidence_hashes_or_classes",
    "all_proof_slots_move_from_blocked_to_authoritative_status_codes",
    "state_before_and_state_after_identities_are_distinct_when_patch_application_is_claimed",
    "patch_application_has_status_code_without_patch_body_or_diff_body",
    "verifier_relevance_has_same_verifier_identity_hash_before_and_after",
    "causal_linkage_is_supported_by_before_after_status_code_transition",
    "stop_continue_boundary_has_terminal_event_ref_hash_and_status_code",
    "executor_guardrail_scan_has_zero_raw_content_findings",
    "training_admission_remains_zero_until_separate_qc_stage",
]
BASE_BLOCKERS = [
    "blocked_fail_closed_reconstruction_request_only",
    "blocked_replay_not_executed",
    "blocked_missing_authoritative_state_before",
    "blocked_missing_authoritative_state_after",
    "blocked_missing_patch_application_proof",
    "blocked_missing_verifier_relevance_proof",
    "blocked_missing_causal_verifier_linkage",
    "blocked_missing_stop_continue_proof",
    "blocked_correct_next_action_not_authoritatively_proven",
    "co_presence_order_candidate_not_causality",
    "event_hashes_are_not_state_before_after",
    "no_raw_content_emitted",
    "training_admission_blocked",
]

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
MULTILINE_RE = re.compile(r"[\r\n]")
HEX_RE = re.compile(r"^[0-9a-f]{12,64}$")
RAW_KEY_RE = re.compile(
    r"(?:^|_)(trajectory|command|output|patch|diff|source_text|issue_body|line_content|stdout|stderr|url|path)(?:$|_)",
    re.IGNORECASE,
)
SAFE_KEY_CONTEXT_RE = re.compile(
    r"(?:status|code|codes|proof|gate|hash|hashes|class|classes|signal|policy|count|counts|bucket|ref|refs|emitted|allowed|task|tasks|scan|claim|application|body)",
    re.IGNORECASE,
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def stage_file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:24]


def is_hash(value: Any, allow_missing: bool = True) -> bool:
    text = str(value or "")
    return (allow_missing and text == "missing") or bool(HEX_RE.match(text))


def index_digests(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {stable_hash(row.get("digest_item_id") or "missing", 24): row for row in rows}


def index_preflight(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {stable_hash(row.get("preflight_item_id") or "missing", 24): row for row in rows}


def non_absent_count(counts: dict[str, Any], key: str, absent_class: str) -> int:
    values = counts.get(key) if isinstance(counts.get(key), dict) else {}
    return sum(int(count) for klass, count in values.items() if str(klass) != absent_class)


def candidate_score(row: dict[str, Any]) -> int:
    counts = row.get("window_class_counts") if isinstance(row.get("window_class_counts"), dict) else {}
    score = 0
    if row.get("window_type") == REQUIRED_WINDOW_TYPE:
        score += 1000
    score += non_absent_count(counts, "patch_signal_class_counts", "patch_signal_absent") * 20
    score += non_absent_count(counts, "verifier_signal_class_counts", "verifier_signal_absent") * 20
    score += int(counts.get("tool_action_observation_transition_count") or 0) * 5
    score += int(counts.get("tool_observation_action_transition_count") or 0) * 5
    score += max(0, 20 - int(counts.get("event_count") or 0))
    score += max(0, 10 - int(row.get("selection_rank") or 0))
    return score


def is_patch_verifier_copresence(row: dict[str, Any]) -> bool:
    counts = row.get("window_class_counts") if isinstance(row.get("window_class_counts"), dict) else {}
    return (
        row.get("window_type") == REQUIRED_WINDOW_TYPE
        and non_absent_count(counts, "patch_signal_class_counts", "patch_signal_absent") > 0
        and non_absent_count(counts, "verifier_signal_class_counts", "verifier_signal_absent") > 0
    )


def select_windows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [row for row in rows if is_patch_verifier_copresence(row)]
    candidates.sort(
        key=lambda row: (
            -candidate_score(row),
            str(row.get("language") or "unknown"),
            str(row.get("repo_hash") or "missing"),
            int(row.get("source_selection_rank") or 999999),
            int(row.get("selection_rank") or 999999),
            stable_hash(row.get("window_id") or "missing", 20),
        )
    )

    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        by_language[str(row.get("language") or "unknown")].append(row)

    selected: list[dict[str, Any]] = []
    selected_repos: Counter[str] = Counter()
    selected_languages: Counter[str] = Counter()
    languages = sorted(by_language)
    while len(selected) < MAX_REQUESTS:
        made_progress = False
        for language in languages:
            if len(selected) >= MAX_REQUESTS:
                break
            if selected_languages[language] >= MAX_REQUESTS_PER_LANGUAGE:
                continue
            for row in by_language[language]:
                repo_hash = str(row.get("repo_hash") or "missing")
                if selected_repos[repo_hash] >= MAX_REQUESTS_PER_REPO:
                    continue
                if row in selected:
                    continue
                selected.append(row)
                selected_repos[repo_hash] += 1
                selected_languages[language] += 1
                made_progress = True
                break
        if not made_progress:
            break
    return selected


def proof_slots_all_blocked() -> dict[str, dict[str, str]]:
    return {
        slot: {
            "proof_status": "blocked",
            "status_code": status_code,
            "evidence_class": "reconstruction_required_not_available",
            "proof_ref_hash": "missing",
        }
        for slot, status_code in PROOF_SLOT_STATUS.items()
    }


def source_digest_refs(
    window: dict[str, Any],
    digest_by_hash: dict[str, dict[str, Any]],
    preflight_by_hash: dict[str, dict[str, Any]],
) -> dict[str, str]:
    digest_hash = str(window.get("source_digest_item_id_hash") or "missing")
    digest = digest_by_hash.get(digest_hash, {})
    digest_refs = digest.get("source_stage_ref_hashes") if isinstance(digest.get("source_stage_ref_hashes"), dict) else {}
    raw_refs = digest.get("raw_row_ref_hashes") if isinstance(digest.get("raw_row_ref_hashes"), dict) else {}
    preflight_hash = str(digest_refs.get("stage12401_preflight_item_hash") or "missing")
    preflight = preflight_by_hash.get(preflight_hash, {})
    preflight_refs = (
        preflight.get("source_stage_ref_hashes") if isinstance(preflight.get("source_stage_ref_hashes"), dict) else {}
    )
    return {
        "stage12403_window_id_hash": stable_hash(window.get("window_id") or "missing", 24),
        "stage12402_digest_item_hash": digest_hash,
        "stage12402_event_digest_hash": str(window.get("source_event_digest_hash") or digest.get("event_digest_hash") or "missing"),
        "stage12401_preflight_item_hash": preflight_hash,
        "stage12400_item_hash": str(digest_refs.get("stage12400_item_hash") or preflight_refs.get("stage12400_item_hash") or "missing"),
        "stage12327_private_ref_hash": str(
            digest_refs.get("stage12327_private_ref_hash")
            or preflight_refs.get("stage12327_private_ref_hash")
            or "missing"
        ),
        "candidate_transition_window_ref_hash": str(
            digest_refs.get("candidate_transition_window_ref_hash")
            or preflight_refs.get("candidate_transition_window_ref_hash")
            or "missing"
        ),
        "source_record_ref_hash": str(raw_refs.get("source_record_ref_hash") or "missing"),
        "instance_ref_hash": str(raw_refs.get("instance_ref_hash") or "missing"),
        "trajectory_ref_hash": str(raw_refs.get("trajectory_ref_hash") or "missing"),
        "model_patch_ref_hash": str(raw_refs.get("model_patch_ref_hash") or "missing"),
    }


def build_request_item(
    window: dict[str, Any],
    rank: int,
    digest_by_hash: dict[str, dict[str, Any]],
    preflight_by_hash: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    refs = source_digest_refs(window, digest_by_hash, preflight_by_hash)
    event_refs = [str(ref) for ref in window.get("event_ref_hashes", [])]
    basis = {
        "source_window": refs["stage12403_window_id_hash"],
        "source_digest": refs["stage12402_digest_item_hash"],
        "event_refs": event_refs,
        "rank": rank,
    }
    blockers = sorted(set(BASE_BLOCKERS) | set(str(blocker) for blocker in window.get("blockers", [])))
    return {
        "stage": STAGE,
        "record_type": "blocked_open_swe_replay_state_reconstruction_request_item",
        "request_id": f"{STAGE}::{stable_hash(basis, 20)}",
        "request_rank": rank,
        "source_window_id_hash": refs["stage12403_window_id_hash"],
        "source_digest_refs": refs,
        "language": str(window.get("language") or "unknown"),
        "repo_hash": str(window.get("repo_hash") or "missing"),
        "window_type": str(window.get("window_type") or "missing"),
        "candidate_window_type": str(window.get("candidate_window_type") or window.get("window_type") or "missing"),
        "window_anchor_ordinal": int(window.get("window_anchor_ordinal") or 0),
        "window_anchor_class": str(window.get("window_anchor_class") or "missing"),
        "window_event_ordinals": [int(ordinal) for ordinal in window.get("window_event_ordinals", [])],
        "event_refs": event_refs,
        "event_ref_hashes": event_refs,
        "event_ref_count": len(event_refs),
        "window_class_counts": window.get("window_class_counts", {}),
        "proof_slots": proof_slots_all_blocked(),
        "all_proof_slots_blocked": True,
        "required_reconstruction_tasks": REQUIRED_RECONSTRUCTION_TASKS,
        "execution_task_types": list(REQUIRED_RECONSTRUCTION_TASKS),
        "acceptance_criteria_for_later_executor": ACCEPTANCE_CRITERIA,
        "blockers": blockers,
        "blocker_codes": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
        **ZERO_ADMISSION_FLAGS,
    }


def validate_item(row: dict[str, Any], index: int) -> list[str]:
    issues: list[str] = []
    required = [
        "request_id",
        "source_window_id_hash",
        "source_digest_refs",
        "language",
        "repo_hash",
        "window_type",
        "candidate_window_type",
        "window_anchor_ordinal",
        "window_anchor_class",
        "window_event_ordinals",
        "event_refs",
        "event_ref_hashes",
        "proof_slots",
        "required_reconstruction_tasks",
        "execution_task_types",
        "acceptance_criteria_for_later_executor",
        "blockers",
        "claim_boundary",
        "zero_admission_flags",
    ]
    for key in required:
        if key not in row:
            issues.append(f"row_{index}_missing_{key}")
    if row.get("window_type") != REQUIRED_WINDOW_TYPE:
        issues.append(f"row_{index}_window_type_not_patch_verifier_copresence")
    if not is_hash(row.get("source_window_id_hash"), allow_missing=False):
        issues.append(f"row_{index}_source_window_id_hash_not_hash")
    if not is_hash(row.get("repo_hash"), allow_missing=False):
        issues.append(f"row_{index}_repo_hash_not_hash")
    refs = row.get("source_digest_refs") if isinstance(row.get("source_digest_refs"), dict) else {}
    for key, value in refs.items():
        if not key.endswith("_hash"):
            issues.append(f"row_{index}_source_digest_ref_{key}_not_hash_named")
        if not is_hash(value):
            issues.append(f"row_{index}_source_digest_ref_{key}_not_hash")
    if row.get("candidate_window_type") != row.get("window_type"):
        issues.append(f"row_{index}_candidate_window_type_alias_mismatch")
    ordinals = row.get("window_event_ordinals")
    if not isinstance(ordinals, list) or not ordinals or ordinals != sorted(ordinals) or len(ordinals) != len(set(ordinals)):
        issues.append(f"row_{index}_window_event_ordinals_invalid")
    event_refs = row.get("event_refs")
    if not isinstance(event_refs, list) or not event_refs:
        issues.append(f"row_{index}_event_refs_empty_or_not_list")
        event_refs = []
    if row.get("event_ref_count") != len(event_refs):
        issues.append(f"row_{index}_event_ref_count_mismatch")
    if row.get("event_ref_hashes") != event_refs:
        issues.append(f"row_{index}_event_ref_hashes_alias_mismatch")
    for event_ref in event_refs:
        if not is_hash(event_ref, allow_missing=False):
            issues.append(f"row_{index}_event_ref_not_hash")
    slots = row.get("proof_slots") if isinstance(row.get("proof_slots"), dict) else {}
    for slot, status_code in PROOF_SLOT_STATUS.items():
        status = slots.get(slot) if isinstance(slots.get(slot), dict) else {}
        if status.get("proof_status") != "blocked":
            issues.append(f"row_{index}_proof_slot_{slot}_not_blocked")
        if status.get("status_code") != status_code:
            issues.append(f"row_{index}_proof_slot_{slot}_status_code_mismatch")
    if row.get("all_proof_slots_blocked") is not True:
        issues.append(f"row_{index}_all_proof_slots_blocked_not_true")
    tasks = row.get("required_reconstruction_tasks") if isinstance(row.get("required_reconstruction_tasks"), dict) else {}
    for task in PROOF_SLOT_STATUS:
        if task not in tasks:
            issues.append(f"row_{index}_missing_reconstruction_task_{task}")
    if not row.get("acceptance_criteria_for_later_executor"):
        issues.append(f"row_{index}_acceptance_criteria_empty")
    if row.get("execution_task_types") != list(REQUIRED_RECONSTRUCTION_TASKS):
        issues.append(f"row_{index}_execution_task_types_mismatch")
    if not row.get("blockers"):
        issues.append(f"row_{index}_blockers_empty")
    if row.get("blocker_codes") != row.get("blockers"):
        issues.append(f"row_{index}_blocker_codes_alias_mismatch")
    claim_boundary = row.get("claim_boundary") if isinstance(row.get("claim_boundary"), dict) else {}
    for key, expected in CLAIM_BOUNDARY.items():
        if claim_boundary.get(key) != expected:
            issues.append(f"row_{index}_claim_boundary_{key}_mismatch")
    zero_flags = row.get("zero_admission_flags") if isinstance(row.get("zero_admission_flags"), dict) else {}
    for key, expected in ZERO_ADMISSION_FLAGS.items():
        if zero_flags.get(key) != expected:
            issues.append(f"row_{index}_zero_admission_flags_{key}_mismatch")
        if row.get(key) != expected:
            issues.append(f"row_{index}_{key}_not_zero_or_false")
    return issues


def validate_caps(rows: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    if len(rows) > MAX_REQUESTS:
        issues.append(f"selected_request_count_exceeds_{MAX_REQUESTS}")
    lang_counts = Counter(str(row.get("language") or "unknown") for row in rows)
    for language, count in lang_counts.items():
        if count > MAX_REQUESTS_PER_LANGUAGE:
            issues.append(f"language_{language}_request_count_exceeds_{MAX_REQUESTS_PER_LANGUAGE}")
    repo_counts = Counter(str(row.get("repo_hash") or "missing") for row in rows)
    for repo_hash, count in repo_counts.items():
        if count > MAX_REQUESTS_PER_REPO:
            issues.append(f"repo_{repo_hash}_request_count_exceeds_{MAX_REQUESTS_PER_REPO}")
    return issues


def scan_value(value: Any, artifact: str, issues: list[dict[str, Any]], key_path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{key_path}.{key}" if key_path else str(key)
            if (
                RAW_KEY_RE.search(str(key))
                and not SAFE_KEY_CONTEXT_RE.search(str(key))
                and isinstance(child, str)
                and child
                and not HEX_RE.match(child)
            ):
                issues.append({"artifact": artifact, "issue": "raw_like_key_with_string_value", "key": child_path})
            scan_value(child, artifact, issues, child_path)
        return
    if isinstance(value, list):
        for list_index, child in enumerate(value):
            scan_value(child, artifact, issues, f"{key_path}[{list_index}]")
        return
    if not isinstance(value, str):
        return
    if ABS_PATH_RE.search(value):
        issues.append({"artifact": artifact, "issue": "absolute_path_string", "key": key_path})
    if URL_RE.search(value):
        issues.append({"artifact": artifact, "issue": "url_string", "key": key_path})
    if MULTILINE_RE.search(value):
        issues.append({"artifact": artifact, "issue": "multiline_string", "key": key_path})
    if key_path.endswith("_hash") and not HEX_RE.match(value) and value != "missing":
        issues.append({"artifact": artifact, "issue": "non_hash_value_in_hash_field", "key": key_path})


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
        if path.suffix == ".jsonl":
            for line_number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                scanned_jsonl_rows += 1
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    issues.append({"artifact": path.name, "issue": "invalid_jsonl", "line": line_number})
                    continue
                scan_value(value, path.name, issues, f"line[{line_number}]")
            continue
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


def upstream_zero_ok(summary: dict[str, Any], expected: dict[str, int | bool]) -> bool:
    flags = summary.get("zero_admission_flags") if isinstance(summary.get("zero_admission_flags"), dict) else {}
    return all(summary.get(key, flags.get(key)) == value for key, value in expected.items())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    windows = read_jsonl(STAGE12403_WINDOWS)
    digests = read_jsonl(STAGE12402_DIGESTS)
    preflight_rows = read_jsonl(STAGE12401_PREFLIGHT)
    stage12403_summary = read_json(STAGE12403_SUMMARY)
    stage12402_summary = read_json(STAGE12402_SUMMARY)
    stage12401_summary = read_json(STAGE12401_SUMMARY)

    digest_by_hash = index_digests(digests)
    preflight_by_hash = index_preflight(preflight_rows)
    selected_windows = select_windows(windows)
    request_items = [
        build_request_item(window, rank, digest_by_hash, preflight_by_hash)
        for rank, window in enumerate(selected_windows, 1)
    ]

    row_path = OUT / ROWS_NAME
    request_path = OUT / REQUEST_NAME
    local_summary_path = OUT / LOCAL_SUMMARY_NAME
    guardrail_path = OUT / GUARDRAIL_NAME
    write_jsonl(row_path, request_items)

    schema_issues = [issue for index, row in enumerate(request_items, 1) for issue in validate_item(row, index)]
    schema_issues.extend(validate_caps(request_items))
    selected_language_counts = Counter(str(row.get("language") or "unknown") for row in request_items)
    input_language_counts = Counter(str(row.get("language") or "unknown") for row in windows)
    selected_window_type_counts = Counter(str(row.get("window_type") or "missing") for row in request_items)
    blocker_counts = Counter(blocker for row in request_items for blocker in row.get("blockers", []))
    blocked_slot_counts = Counter(slot for row in request_items for slot in row.get("proof_slots", {}))

    zero_ok = (
        all(row.get(key) == value for row in request_items for key, value in ZERO_ADMISSION_FLAGS.items())
        and upstream_zero_ok(stage12403_summary, {"training_allowed": False, "training_row_count": 0})
        and upstream_zero_ok(stage12402_summary, {"training_allowed": False, "training_row_count": 0})
        and upstream_zero_ok(stage12401_summary, {"training_allowed": False, "training_row_count": 0})
    )

    request = {
        "stage": STAGE,
        "artifact_type": "fail_closed_replay_state_reconstruction_request",
        "decision": "request_capped_safe_reconstruction_subset_no_replay_executed",
        "source_stages": [
            "stage12403_open_swe_event_digest_window_segmenter",
            "stage12402_open_swe_private_event_digest_extractor",
            "stage12401_open_swe_raw_private_hydration_preflight",
        ],
        "execution_policy": {
            "replay_executed_by_this_stage": False,
            "training_allowed": False,
            "raw_content_allowed": False,
            "emit_only_hashes_classes_counts_status_codes": True,
            "cap_request_items": MAX_REQUESTS,
            "cap_per_language": MAX_REQUESTS_PER_LANGUAGE,
            "cap_per_repo": MAX_REQUESTS_PER_REPO,
        },
        "selection_policy": (
            "language_repo_round_robin_over_patch_verifier_co_presence_windows_with_one_request_per_repo"
        ),
        "request_item_count": len(request_items),
        "request_ids": [str(row.get("request_id")) for row in request_items],
        "request_items": request_items,
        "claim_boundary": CLAIM_BOUNDARY,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
        **ZERO_ADMISSION_FLAGS,
    }
    write_json(request_path, request)

    summary: dict[str, Any] = {
        "stage": STAGE,
        "decision": "fail_closed_replay_state_reconstruction_request_ready_no_replay_no_admission",
        "source_stages": [
            "stage12403_open_swe_event_digest_window_segmenter",
            "stage12402_open_swe_private_event_digest_extractor",
            "stage12401_open_swe_raw_private_hydration_preflight",
        ],
        "source_stage_artifact_hashes": {
            "stage12403_windows_hash": stage_file_hash(STAGE12403_WINDOWS),
            "stage12403_summary_hash": stage_file_hash(STAGE12403_SUMMARY),
            "stage12402_digests_hash": stage_file_hash(STAGE12402_DIGESTS),
            "stage12402_summary_hash": stage_file_hash(STAGE12402_SUMMARY),
            "stage12401_preflight_hash": stage_file_hash(STAGE12401_PREFLIGHT),
            "stage12401_summary_hash": stage_file_hash(STAGE12401_SUMMARY),
        },
        "input_windows": len(windows),
        "input_window_count": len(windows),
        "input_digest_item_count": len(digests),
        "input_preflight_item_count": len(preflight_rows),
        "selected_requests": len(request_items),
        "selected_request_count": len(request_items),
        "requested_window_count": len(request_items),
        "caps": {
            "max_requests": MAX_REQUESTS,
            "max_requests_per_language": MAX_REQUESTS_PER_LANGUAGE,
            "max_requests_per_repo": MAX_REQUESTS_PER_REPO,
            "required_window_type": REQUIRED_WINDOW_TYPE,
        },
        "input_language_counts": dict(sorted(input_language_counts.items())),
        "selected_language_counts": dict(sorted(selected_language_counts.items())),
        "language_counts": dict(sorted(selected_language_counts.items())),
        "selected_repo_hash_count": len({row.get("repo_hash") for row in request_items}),
        "unique_repo_hash_count": len({row.get("repo_hash") for row in request_items}),
        "selected_window_type_counts": dict(sorted(selected_window_type_counts.items())),
        "proof_slot_blocked_counts": dict(sorted(blocked_slot_counts.items())),
        "zero_admission": zero_ok,
        "zero_admission_flags": {
            **ZERO_ADMISSION_FLAGS,
            "upstream_stage12403_zero_admission_confirmed": upstream_zero_ok(
                stage12403_summary, {"training_allowed": False, "training_row_count": 0}
            ),
            "upstream_stage12402_zero_admission_confirmed": upstream_zero_ok(
                stage12402_summary, {"training_allowed": False, "training_row_count": 0}
            ),
            "upstream_stage12401_zero_admission_confirmed": upstream_zero_ok(
                stage12401_summary, {"training_allowed": False, "training_row_count": 0}
            ),
            "selected_request_admitted_count": 0,
        },
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "guardrail_scan": None,
        "guardrail_issue_count": None,
        "raw_leak_findings": [],
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "claim_boundary": CLAIM_BOUNDARY,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "generated_artifacts": [ROWS_NAME, REQUEST_NAME, LOCAL_SUMMARY_NAME, GUARDRAIL_NAME],
        **ZERO_ADMISSION_FLAGS,
    }
    write_json(local_summary_path, summary)

    guardrail = guardrail_scan([row_path, request_path, local_summary_path])
    write_json(guardrail_path, guardrail)
    summary["guardrail_scan"] = guardrail
    summary["guardrail_issue_count"] = len(guardrail["issues"])
    summary["raw_leak_findings"] = guardrail["issues"]
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)

    if schema_issues or guardrail["issues"] or not zero_ok:
        raise SystemExit(
            f"{STAGE} validation failed: schema_issues={len(schema_issues)} "
            f"guardrail_issues={len(guardrail['issues'])} zero_ok={zero_ok}"
        )


if __name__ == "__main__":
    main()
