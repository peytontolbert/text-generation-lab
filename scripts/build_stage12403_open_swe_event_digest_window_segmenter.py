#!/usr/bin/env python3
"""Stage12403 Open-SWE event digest window segmenter.

Consumes Stage12402 private event digests and emits only replay-target transition
windows built from safe digest fields: ordinals, classes, counts, and hashes.
No raw commands, outputs, paths, source text, diffs, issue text, or URLs are
admitted. Windows are co-presence/order candidates only, never causality claims.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12403_open_swe_event_digest_window_segmenter"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12402_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12402_open_swe_private_event_digest_extractor/"
    / "open_swe_private_event_digests.jsonl"
)
STAGE12402_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12402_open_swe_private_event_digest_extractor/"
    / "open_swe_private_event_digest_summary.json"
)

ROWS_NAME = "open_swe_event_digest_replay_target_windows.jsonl"
LOCAL_SUMMARY_NAME = "open_swe_event_digest_window_segmenter_summary.json"
GUARDRAIL_NAME = "guardrail_scan.json"

MAX_WINDOWS_PER_DIGEST = 5
WINDOW_RADIUS = 2
CO_PRESENCE_MAX_GAP = 8

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
    "co_presence_order_candidate_only": True,
    "state_before_claim_emitted": False,
    "state_after_claim_emitted": False,
    "patch_application_claim_emitted": False,
    "verifier_relevance_claim_emitted": False,
    "causal_linkage_claim_emitted": False,
    "correct_next_action_policy_claim_emitted": False,
    "training_admission_claim_emitted": False,
    "transition_proof_claim_emitted": False,
}
PROOF_SLOT_STATUS = {
    "authoritative_state_before": "blocked_missing_authoritative_state_before",
    "authoritative_state_after": "blocked_missing_authoritative_state_after",
    "patch_application": "blocked_missing_patch_application_proof",
    "verifier_relevance": "blocked_missing_verifier_relevance_proof",
    "causal_verifier_linkage": "blocked_missing_causal_verifier_linkage",
    "stop_continue": "blocked_missing_stop_continue_proof",
    "next_action_policy": "blocked_correct_next_action_not_authoritatively_proven",
    "replay_recovery": "blocked_replay_recovery_not_executed",
}
BASE_REPLAY_RECOVERY_TASKS = [
    "recover_authoritative_state_before_hash",
    "recover_authoritative_state_after_hash",
    "recover_patch_application_proof_hash",
    "recover_verifier_relevance_proof_hash",
    "recover_causal_linkage_proof_hash",
    "recover_stop_continue_status_hash",
    "rerun_guardrail_scan_before_any_admission",
    "preserve_zero_admission_until_all_proof_slots_unblocked",
]
BASE_BLOCKERS = [
    "blocked_fail_closed_event_digest_window_only",
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
    r"(?:status|code|codes|proof|gate|hash|hashes|class|classes|signal|policy|count|counts|bucket|ref|refs|emitted|allowed|task|tasks|scan|claim|application)",
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


def proof_status_slots() -> dict[str, dict[str, str]]:
    return {
        slot: {
            "proof_status": "blocked",
            "status_code": status_code,
            "evidence_class": "safe_digest_window_only_not_proof",
        }
        for slot, status_code in PROOF_SLOT_STATUS.items()
    }


def patch_present(event: dict[str, Any]) -> bool:
    return str(event.get("patch_signal_class") or "patch_signal_absent") != "patch_signal_absent"


def verifier_present(event: dict[str, Any]) -> bool:
    return str(event.get("verifier_signal_class") or "verifier_signal_absent") != "verifier_signal_absent"


def action_observation_transition(previous: dict[str, Any], current: dict[str, Any]) -> str | None:
    previous_action = str(previous.get("action_class") or "")
    current_action = str(current.get("action_class") or "")
    if previous_action != "tool_observation" and current_action == "tool_observation":
        return "tool_action_to_observation_order_transition"
    if previous_action == "tool_observation" and current_action != "tool_observation":
        return "tool_observation_to_action_order_transition"
    return None


def bounded_ordinals(events: list[dict[str, Any]], start: int, end: int) -> list[int]:
    last = max(0, len(events) - 1)
    left = max(0, start)
    right = min(last, end)
    return list(range(left, right + 1)) if left <= right else []


def co_presence_window_ordinals(events: list[dict[str, Any]], anchor: int, target_ordinals: list[int]) -> list[int] | None:
    nearby = sorted(target_ordinals, key=lambda ordinal: (abs(ordinal - anchor), ordinal))
    for target in nearby:
        if abs(target - anchor) <= CO_PRESENCE_MAX_GAP:
            start = min(anchor, target) - 1
            end = max(anchor, target) + 1
            return bounded_ordinals(events, start, end)
    return None


def anchor_candidates(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    patch_ordinals = [int(event.get("ordinal") or 0) for event in events if patch_present(event)]
    verifier_ordinals = [int(event.get("ordinal") or 0) for event in events if verifier_present(event)]
    candidates: list[dict[str, Any]] = []

    for ordinal in patch_ordinals:
        ordinals = co_presence_window_ordinals(events, ordinal, verifier_ordinals)
        candidates.append(
            {
                "anchor_ordinal": ordinal,
                "anchor_class": "patch_signal_anchor",
                "window_event_ordinals": ordinals or bounded_ordinals(events, ordinal - WINDOW_RADIUS, ordinal + WINDOW_RADIUS),
            }
        )
    for ordinal in verifier_ordinals:
        ordinals = co_presence_window_ordinals(events, ordinal, patch_ordinals)
        candidates.append(
            {
                "anchor_ordinal": ordinal,
                "anchor_class": "verifier_signal_anchor",
                "window_event_ordinals": ordinals or bounded_ordinals(events, ordinal - WINDOW_RADIUS, ordinal + WINDOW_RADIUS),
            }
        )
    for index in range(1, len(events)):
        transition = action_observation_transition(events[index - 1], events[index])
        if not transition:
            continue
        candidates.append(
            {
                "anchor_ordinal": int(events[index].get("ordinal") or index),
                "anchor_class": transition,
                "window_event_ordinals": bounded_ordinals(events, index - WINDOW_RADIUS, index + WINDOW_RADIUS),
            }
        )
    return candidates


def relation_classes_for_window(events_by_ordinal: dict[int, dict[str, Any]], ordinals: list[int]) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    ordinal_set = set(ordinals)
    for previous_ordinal, current_ordinal in zip(ordinals, ordinals[1:]):
        if previous_ordinal not in ordinal_set or current_ordinal not in ordinal_set:
            continue
        previous = events_by_ordinal.get(previous_ordinal, {})
        current = events_by_ordinal.get(current_ordinal, {})
        bits = [
            str(previous.get("role_class") or "role_other"),
            "to",
            str(current.get("role_class") or "role_other"),
        ]
        if patch_present(current):
            bits.append("then_patch_signal")
        if verifier_present(current):
            bits.append("then_verifier_signal")
        transition = action_observation_transition(previous, current)
        if transition:
            bits.append(transition)
        relations.append(
            {
                "from_ordinal": previous_ordinal,
                "to_ordinal": current_ordinal,
                "relation_class": "_".join(bits),
                "safe_order_evidence": "relative_order_only",
            }
        )
    return relations


def window_class_counts(window_events: list[dict[str, Any]], relations: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, Any] = {
        "event_count": len(window_events),
        "relation_count": len(relations),
        "tool_action_observation_transition_count": sum(
            1 for relation in relations if "tool_action_to_observation_order_transition" in str(relation.get("relation_class"))
        ),
        "tool_observation_action_transition_count": sum(
            1 for relation in relations if "tool_observation_to_action_order_transition" in str(relation.get("relation_class"))
        ),
    }
    for field in ["role_class", "action_class", "status_class", "patch_signal_class", "verifier_signal_class"]:
        counts[f"{field}_counts"] = dict(sorted(Counter(str(event.get(field) or "missing") for event in window_events).items()))
    counts["observation_marker_class_counts"] = dict(
        sorted(
            Counter(
                str(marker)
                for event in window_events
                for marker in (event.get("observation_marker_classes") if isinstance(event.get("observation_marker_classes"), list) else [])
            ).items()
        )
    )
    counts["window_relation_class_counts"] = dict(
        sorted(Counter(str(relation.get("relation_class") or "missing") for relation in relations).items())
    )
    return counts


def candidate_window_type(counts: dict[str, Any]) -> str:
    patch_counts = counts.get("patch_signal_class_counts") if isinstance(counts.get("patch_signal_class_counts"), dict) else {}
    verifier_counts = (
        counts.get("verifier_signal_class_counts") if isinstance(counts.get("verifier_signal_class_counts"), dict) else {}
    )
    has_patch = sum(count for klass, count in patch_counts.items() if klass != "patch_signal_absent") > 0
    has_verifier = sum(count for klass, count in verifier_counts.items() if klass != "verifier_signal_absent") > 0
    has_transition = bool(
        counts.get("tool_action_observation_transition_count") or counts.get("tool_observation_action_transition_count")
    )
    if has_patch and has_verifier:
        return "patch_verifier_co_presence_order_candidate_not_causality"
    if has_patch and has_transition:
        return "patch_signal_tool_transition_order_candidate"
    if has_verifier and has_transition:
        return "verifier_signal_tool_transition_order_candidate"
    if has_patch:
        return "patch_signal_context_window_not_apply_proof"
    if has_verifier:
        return "verifier_signal_context_window_not_relevance_proof"
    return "tool_action_observation_transition_window"


def score_window(candidate: dict[str, Any], counts: dict[str, Any]) -> int:
    window_type = candidate_window_type(counts)
    score = 0
    if window_type == "patch_verifier_co_presence_order_candidate_not_causality":
        score += 100
    if "patch_signal" in window_type:
        score += 25
    if "verifier_signal" in window_type or "patch_verifier" in window_type:
        score += 25
    score += int(counts.get("tool_action_observation_transition_count") or 0) * 5
    score += int(counts.get("tool_observation_action_transition_count") or 0) * 5
    score += max(0, 8 - len(candidate.get("window_event_ordinals") or []))
    return score


def build_windows_for_digest(row: dict[str, Any]) -> list[dict[str, Any]]:
    events = row.get("event_order_digest") if isinstance(row.get("event_order_digest"), list) else []
    events_by_ordinal = {int(event.get("ordinal") or 0): event for event in events if isinstance(event, dict)}
    source_digest_item_id_hash = stable_hash(row.get("digest_item_id") or "missing", 24)
    source_event_digest_hash = str(row.get("event_digest_hash") or "missing")
    language = str(row.get("language_family") or row.get("language") or "unknown")
    repo_hash = str(row.get("repo_family_hash") or row.get("repo_hash") or "missing")
    source_rank = int(row.get("selection_rank") or 0)
    blockers = sorted(set(BASE_BLOCKERS) | set(str(blocker) for blocker in row.get("unresolved_blockers", [])))

    deduped: dict[tuple[int, ...], dict[str, Any]] = {}
    for candidate in anchor_candidates(events):
        ordinals = tuple(int(ordinal) for ordinal in candidate.get("window_event_ordinals") or [])
        if not ordinals:
            continue
        window_events = [events_by_ordinal[ordinal] for ordinal in ordinals if ordinal in events_by_ordinal]
        if not window_events:
            continue
        relations = relation_classes_for_window(events_by_ordinal, list(ordinals))
        counts = window_class_counts(window_events, relations)
        candidate["score"] = score_window(candidate, counts)
        candidate["window_class_counts"] = counts
        candidate["window_relation_classes"] = relations
        existing = deduped.get(ordinals)
        if existing is None or int(candidate.get("score") or 0) > int(existing.get("score") or 0):
            deduped[ordinals] = candidate

    selected = sorted(
        deduped.values(),
        key=lambda candidate: (
            -int(candidate.get("score") or 0),
            int(candidate.get("anchor_ordinal") or 999999),
            tuple(candidate.get("window_event_ordinals") or []),
        ),
    )[:MAX_WINDOWS_PER_DIGEST]

    windows: list[dict[str, Any]] = []
    for rank, candidate in enumerate(selected, 1):
        ordinals = [int(ordinal) for ordinal in candidate.get("window_event_ordinals") or []]
        event_ref_hashes = [
            str(events_by_ordinal[ordinal].get("event_ref_hash") or "missing")
            for ordinal in ordinals
            if ordinal in events_by_ordinal
        ]
        counts = candidate["window_class_counts"]
        window_type = candidate_window_type(counts)
        window_basis = {
            "source_digest_item_id_hash": source_digest_item_id_hash,
            "source_event_digest_hash": source_event_digest_hash,
            "rank": rank,
            "ordinals": ordinals,
            "event_ref_hashes": event_ref_hashes,
            "window_type": window_type,
        }
        windows.append(
            {
                "stage": STAGE,
                "record_type": "blocked_open_swe_event_digest_replay_target_window",
                "window_id": f"{STAGE}::{stable_hash(window_basis, 20)}",
                "source_digest_item_id_hash": source_digest_item_id_hash,
                "source_event_digest_hash": source_event_digest_hash,
                "language": language,
                "repo_hash": repo_hash,
                "source_selection_rank": source_rank,
                "selection_rank": rank,
                "window_anchor_ordinal": int(candidate.get("anchor_ordinal") or 0),
                "window_anchor_class": str(candidate.get("anchor_class") or "unknown_anchor"),
                "window_event_ordinals": ordinals,
                "event_ref_hashes": event_ref_hashes,
                "window_class_counts": counts,
                "window_relation_classes": candidate["window_relation_classes"],
                "candidate_window_type": window_type,
                "window_type": window_type,
                "co_presence_only": window_type == "patch_verifier_co_presence_order_candidate_not_causality",
                "causal_linkage_proven": False,
                "observed_action_policy_status": "observed_only_not_policy_gold",
                "correct_policy_label_status": "blocked_not_authoritatively_proven",
                "replay_recovery_tasks": BASE_REPLAY_RECOVERY_TASKS,
                "proof_status_slots": proof_status_slots(),
                "proof_slots": proof_status_slots(),
                "blockers": blockers,
                "blocker_codes": blockers,
                "claim_boundary": CLAIM_BOUNDARY,
                "raw_content_policy": RAW_CONTENT_POLICY,
                "zero_admission_flags": ZERO_ADMISSION_FLAGS,
                **ZERO_ADMISSION_FLAGS,
            }
        )
    return windows


def validate_window(row: dict[str, Any], row_index: int) -> list[str]:
    issues: list[str] = []
    required = [
        "window_id",
        "source_digest_item_id_hash",
        "language",
        "repo_hash",
        "selection_rank",
        "window_event_ordinals",
        "event_ref_hashes",
        "window_class_counts",
        "window_relation_classes",
        "candidate_window_type",
        "window_type",
        "co_presence_only",
        "causal_linkage_proven",
        "observed_action_policy_status",
        "correct_policy_label_status",
        "replay_recovery_tasks",
        "proof_status_slots",
        "proof_slots",
        "blockers",
        "blocker_codes",
        "claim_boundary",
        "zero_admission_flags",
    ]
    for key in required:
        if key not in row:
            issues.append(f"row_{row_index}_missing_{key}")
    if not HEX_RE.match(str(row.get("source_digest_item_id_hash") or "")):
        issues.append(f"row_{row_index}_source_digest_item_id_hash_not_hash")
    if str(row.get("repo_hash") or "missing") != "missing" and not HEX_RE.match(str(row.get("repo_hash") or "")):
        issues.append(f"row_{row_index}_repo_hash_not_hash")
    ordinals = row.get("window_event_ordinals")
    refs = row.get("event_ref_hashes")
    if not isinstance(ordinals, list) or not ordinals:
        issues.append(f"row_{row_index}_window_event_ordinals_empty_or_not_list")
        ordinals = []
    if not isinstance(refs, list) or len(refs) != len(ordinals):
        issues.append(f"row_{row_index}_event_ref_hashes_count_mismatch")
        refs = []
    if len(ordinals) != len(set(ordinals)) or ordinals != sorted(ordinals):
        issues.append(f"row_{row_index}_ordinals_not_unique_sorted")
    for ref in refs:
        if str(ref) != "missing" and not HEX_RE.match(str(ref)):
            issues.append(f"row_{row_index}_event_ref_hash_not_hash")
    if int(row.get("selection_rank") or 0) < 1 or int(row.get("selection_rank") or 0) > MAX_WINDOWS_PER_DIGEST:
        issues.append(f"row_{row_index}_selection_rank_out_of_bounds")
    counts = row.get("window_class_counts") if isinstance(row.get("window_class_counts"), dict) else {}
    if counts.get("event_count") != len(ordinals):
        issues.append(f"row_{row_index}_window_event_count_mismatch")
    if not isinstance(row.get("window_relation_classes"), list):
        issues.append(f"row_{row_index}_window_relation_classes_not_list")
    if not row.get("replay_recovery_tasks"):
        issues.append(f"row_{row_index}_replay_recovery_tasks_empty")
    if row.get("window_type") != row.get("candidate_window_type"):
        issues.append(f"row_{row_index}_window_type_alias_mismatch")
    if row.get("causal_linkage_proven") is not False:
        issues.append(f"row_{row_index}_causal_linkage_proven_not_false")
    if row.get("observed_action_policy_status") != "observed_only_not_policy_gold":
        issues.append(f"row_{row_index}_observed_action_policy_status_invalid")
    if row.get("correct_policy_label_status") != "blocked_not_authoritatively_proven":
        issues.append(f"row_{row_index}_correct_policy_label_status_invalid")
    if row.get("blocker_codes") != row.get("blockers"):
        issues.append(f"row_{row_index}_blocker_codes_alias_mismatch")
    slots = row.get("proof_status_slots") if isinstance(row.get("proof_status_slots"), dict) else {}
    if row.get("proof_slots") != slots:
        issues.append(f"row_{row_index}_proof_slots_alias_mismatch")
    for slot in PROOF_SLOT_STATUS:
        status = slots.get(slot) if isinstance(slots.get(slot), dict) else {}
        if status.get("proof_status") != "blocked" or status.get("status_code") != PROOF_SLOT_STATUS[slot]:
            issues.append(f"row_{row_index}_proof_slot_{slot}_not_blocked")
    if not row.get("blockers"):
        issues.append(f"row_{row_index}_blockers_empty")
    claim_boundary = row.get("claim_boundary") if isinstance(row.get("claim_boundary"), dict) else {}
    for claim, expected in CLAIM_BOUNDARY.items():
        if claim_boundary.get(claim) != expected:
            issues.append(f"row_{row_index}_claim_boundary_{claim}_mismatch")
    zero_flags = row.get("zero_admission_flags") if isinstance(row.get("zero_admission_flags"), dict) else {}
    for key, expected in ZERO_ADMISSION_FLAGS.items():
        if zero_flags.get(key) != expected:
            issues.append(f"row_{row_index}_zero_admission_flags_{key}_mismatch")
        if row.get(key) != expected:
            issues.append(f"row_{row_index}_{key}_not_zero_or_false")
    if "causality" not in str(row.get("candidate_window_type") or ""):
        if row.get("candidate_window_type") == "patch_verifier_co_presence_order_candidate_not_causality":
            pass
    if row.get("candidate_window_type") == "patch_verifier_co_presence_order_candidate_not_causality":
        if claim_boundary.get("causal_linkage_claim_emitted") is not False:
            issues.append(f"row_{row_index}_co_presence_window_emits_causality_claim")
    return issues


def validate_max_windows_per_digest(rows: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    counts = Counter(str(row.get("source_digest_item_id_hash") or "missing") for row in rows)
    for source_hash, count in counts.items():
        if count > MAX_WINDOWS_PER_DIGEST:
            issues.append(f"source_digest_{source_hash}_window_count_exceeds_{MAX_WINDOWS_PER_DIGEST}")
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
        for index, child in enumerate(value):
            scan_value(child, artifact, issues, f"{key_path}[{index}]")
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


def merge_counter_dict(target: defaultdict[str, Counter[str]], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if key.endswith("_counts") and isinstance(value, dict):
            target[key].update({str(inner_key): int(count) for inner_key, count in value.items()})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    digest_rows = sorted(read_jsonl(STAGE12402_ROWS), key=lambda row: int(row.get("selection_rank") or 0))
    stage12402_summary = read_json(STAGE12402_SUMMARY)

    windows: list[dict[str, Any]] = []
    for digest_row in digest_rows:
        windows.extend(build_windows_for_digest(digest_row))

    row_path = OUT / ROWS_NAME
    local_summary_path = OUT / LOCAL_SUMMARY_NAME
    guardrail_path = OUT / GUARDRAIL_NAME
    write_jsonl(row_path, windows)

    schema_issues = [issue for index, row in enumerate(windows, 1) for issue in validate_window(row, index)]
    schema_issues.extend(validate_max_windows_per_digest(windows))

    window_type_counts = Counter(str(row.get("candidate_window_type") or "missing") for row in windows)
    language_counts = Counter(str(row.get("language") or "unknown") for row in windows)
    blocker_counts = Counter(blocker for row in windows for blocker in row.get("blockers", []))
    task_counts = Counter(task for row in windows for task in row.get("replay_recovery_tasks", []))
    per_digest_counts = Counter(str(row.get("source_digest_item_id_hash") or "missing") for row in windows)
    aggregate_window_class_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for row in windows:
        counts = row.get("window_class_counts") if isinstance(row.get("window_class_counts"), dict) else {}
        merge_counter_dict(aggregate_window_class_counts, counts)

    upstream_zero_ok = all(
        stage12402_summary.get(key) == expected
        for key, expected in {
            "training_allowed": False,
            "level3_admitted": 0,
            "patch_trace_admitted": 0,
            "strict_eval_eligible": 0,
            "source_heldout_admissible": 0,
            "repair_claim_admitted": 0,
        }.items()
    )

    summary: dict[str, Any] = {
        "stage": STAGE,
        "decision": "fail_closed_replay_target_event_digest_windows_ready_no_admissions",
        "source_stages": ["stage12402_open_swe_private_event_digest_extractor"],
        "input_digest_item_count": len(digest_rows),
        "output_window_count": len(windows),
        "max_windows_per_digest": MAX_WINDOWS_PER_DIGEST,
        "max_windows_per_digest_observed": max(per_digest_counts.values()) if per_digest_counts else 0,
        "source_digest_items_with_windows": len(per_digest_counts),
        "selection_policy": "ranked_bounded_windows_around_patch_verifier_and_tool_action_observation_transitions",
        "co_presence_label_policy": "patch_and_verifier_windows_are_order_candidates_not_causality",
        "candidate_window_type_counts": dict(sorted(window_type_counts.items())),
        "window_type_counts": dict(sorted(window_type_counts.items())),
        "language_window_counts": dict(sorted(language_counts.items())),
        "unique_repo_hash_count": len({row.get("repo_hash") for row in windows}),
        "window_class_counts": {
            key: dict(sorted(counter.items())) for key, counter in sorted(aggregate_window_class_counts.items())
        },
        "replay_recovery_task_counts": dict(sorted(task_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "source_stage_artifact_hashes": {
            "stage12402_digest_rows_hash": stage_file_hash(STAGE12402_ROWS),
            "stage12402_summary_hash": stage_file_hash(STAGE12402_SUMMARY),
        },
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": {
            **ZERO_ADMISSION_FLAGS,
            "upstream_stage12402_zero_admission_confirmed": upstream_zero_ok,
            "admitted_window_count": 0,
        },
        "generated_artifacts": [ROWS_NAME, LOCAL_SUMMARY_NAME, GUARDRAIL_NAME],
    }
    summary.update(ZERO_ADMISSION_FLAGS)
    write_json(local_summary_path, summary)

    guardrail = guardrail_scan([row_path, local_summary_path])
    write_json(guardrail_path, guardrail)
    summary["raw_leak_scan"] = guardrail
    summary["raw_leak_findings"] = guardrail["issues"]
    summary["guardrail_issue_count"] = len(guardrail["issues"])
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)

    if schema_issues or guardrail["issues"]:
        raise SystemExit(
            f"{STAGE} validation failed: schema_issues={len(schema_issues)} guardrail_issues={len(guardrail['issues'])}"
        )


if __name__ == "__main__":
    main()
