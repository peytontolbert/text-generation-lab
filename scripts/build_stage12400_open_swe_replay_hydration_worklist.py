#!/usr/bin/env python3
"""Stage12400 fail-closed Open-SWE replay/hydration worklist.

Consumes Stage12395 semantic packet preflight, Stage12398 ordered skeletons,
and Stage12399 semantic transition reviewer packets. Emits only bounded hashes,
classes, counts, statuses, and booleans. The worklist is for external
replay/hydration only: no training admissions, no raw commands, no raw outputs,
no raw paths, no URLs, no source text, no issue bodies, and no patches/diffs.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12400_open_swe_replay_hydration_worklist"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12395_PACKETS = (
    ROOT
    / "runs/local/artifacts/stage12395_open_swe_multilingual_semantic_packet_preflight/"
    / "open_swe_multilingual_semantic_packet_preflight.jsonl"
)
STAGE12398_SKELETONS = (
    ROOT
    / "runs/local/artifacts/stage12398_open_swe_ordered_event_skeleton_35_preflight/"
    / "open_swe_ordered_event_skeleton_35_preflight.jsonl"
)
STAGE12399_REVIEW_PACKETS = (
    ROOT
    / "runs/local/artifacts/stage12399_open_swe_semantic_transition_reviewer/"
    / "open_swe_semantic_transition_reviewer_packets.jsonl"
)
STAGE12399_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12399_open_swe_semantic_transition_reviewer/"
    / "open_swe_semantic_transition_reviewer_summary.json"
)

ROWS_NAME = "open_swe_replay_hydration_worklist.jsonl"
LOCAL_SUMMARY_NAME = "open_swe_replay_hydration_worklist_summary.json"
GUARDRAIL_NAME = "guardrail_scan.json"

EXPECTED_MAX_SELECTED = 15
LANGUAGE_ORDER = ("python", "go", "typescript", "javascript", "rust", "php", "java")
PROOF_GATES = (
    "authoritative_state_before",
    "authoritative_state_after",
    "explicit_action_label",
    "verifier_relevance_proof",
    "patch_application_proof",
    "causal_verifier_linkage",
)
PROOF_TO_HYDRATION_TASK = {
    "missing_authoritative_state_before": "hydrate_authoritative_state_before_hash_and_status_class",
    "missing_authoritative_state_after": "hydrate_authoritative_state_after_hash_and_status_class",
    "missing_verifier_relevance_proof": "hydrate_selected_verifier_relevance_proof_hashes",
    "missing_patch_application_proof": "hydrate_patch_application_and_effect_hash",
    "missing_causal_verifier_linkage": "hydrate_before_after_verifier_causal_linkage",
    "missing_explicit_action_label": "hydrate_explicit_bounded_action_label",
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
ZERO_ADMISSION: dict[str, int | bool] = {
    "training_allowed": False,
    "level3_admitted": 0,
    "patch_trace_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
    "repair_claim_admitted": 0,
    "training_row_count": 0,
}

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
MULTILINE_RE = re.compile(r"[\r\n]")
HEX_RE = re.compile(r"^[0-9a-f]{12,64}$")
RAW_KEY_RE = re.compile(
    r"(?:^|_)(trajectory|command|output|patch|diff|source_text|issue_body|line_content|stdout|stderr|url|path)(?:$|_)",
    re.IGNORECASE,
)
SAFE_KEY_CONTEXT_RE = re.compile(
    r"(?:status|code|codes|proof|gate|hash|hashes|class|classes|signal|policy|count|counts|bucket|ref|refs|emitted|allowed|task|tasks|scan)",
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


def source_packet_index(packets: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {stable_hash(packet.get("packet_id") or "missing", 20): packet for packet in packets}


def skeleton_index(skeletons: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("packet_id") or ""): row for row in skeletons}


def event_bucket_score(bucket: str) -> int:
    return {
        "none": 0,
        "one": 1,
        "two_to_three": 2,
        "four_to_eight": 3,
        "many": 5,
        "lt_75": 2,
        "75_99": 3,
        "100_124": 4,
        "125_149": 5,
        "150_174": 6,
        "175_199": 7,
        "gte_200": 8,
    }.get(bucket, 0)


def requested_hydration_tasks(missing_proofs: list[str]) -> list[str]:
    tasks = [PROOF_TO_HYDRATION_TASK[code] for code in missing_proofs if code in PROOF_TO_HYDRATION_TASK]
    tasks.extend(
        [
            "return_only_hashes_classes_counts_statuses",
            "preserve_zero_admission_until_all_proof_gates_pass",
            "rerun_raw_leak_scan_on_hydrated_packet",
        ]
    )
    return sorted(set(tasks))


def proof_recovery_slots(reviewer: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source_refs = reviewer.get("source_ref_hashes") if isinstance(reviewer.get("source_ref_hashes"), dict) else {}
    bounded_packet = (
        reviewer.get("bounded_transition_review_packet")
        if isinstance(reviewer.get("bounded_transition_review_packet"), dict)
        else {}
    )
    proof_hashes = (
        bounded_packet.get("proof_artifact_hashes")
        if isinstance(bounded_packet.get("proof_artifact_hashes"), dict)
        else {}
    )
    common_basis = [
        "ordered_skeleton_available_not_proof",
        "raw_private_replay_required",
        "safe_hash_only_worklist",
    ]
    return {
        "authoritative_state_before": {
            "status": str(reviewer.get("authoritative_state_before_status") or reviewer.get("state_before_status") or "missing_authoritative_state_before"),
            "proof_ref_hash": None,
            "state_snapshot_ref_hash": None,
            "basis_codes": common_basis + ["state_before_must_be_recovered_from_replay"],
        },
        "authoritative_state_after": {
            "status": str(reviewer.get("authoritative_state_after_status") or reviewer.get("state_after_status") or "missing_authoritative_state_after"),
            "proof_ref_hash": None,
            "state_snapshot_ref_hash": None,
            "basis_codes": common_basis + ["state_after_must_be_recovered_from_replay"],
        },
        "explicit_action_label": {
            "action_label_enum": str(reviewer.get("explicit_action_label") or reviewer.get("action_label_candidate") or "missing_explicit_action_label"),
            "action_event_ref_hash": str(reviewer.get("candidate_transition_window_ref_hash") or proof_hashes.get("window_basis_hash") or "missing"),
            "proof_status": str(reviewer.get("explicit_action_label_status") or "missing_explicit_action_label"),
            "basis_codes": common_basis + ["bounded_action_class_only_not_correctness_proof"],
        },
        "verifier_relevance": {
            "verifier_ref_hash": None,
            "selected_verifier_scope_hash": None,
            "relevance_status": str(reviewer.get("verifier_relevance_status") or "missing_verifier_relevance_proof"),
            "basis_codes": common_basis + ["verifier_marker_is_not_relevance_proof"],
        },
        "patch_application": {
            "patch_ref_hash": None,
            "apply_proof_ref_hash": None,
            "changed_surface_hash": str(source_refs.get("source_packet_hash") or proof_hashes.get("source_packet_hash") or "missing"),
            "apply_status": str(reviewer.get("patch_application_status") or "missing_patch_application_proof"),
            "basis_codes": common_basis + ["patch_signal_is_not_apply_proof"],
        },
        "causal_verifier_linkage": {
            "action_or_patch_ref_hash": str(reviewer.get("candidate_transition_window_ref_hash") or proof_hashes.get("window_basis_hash") or "missing"),
            "verifier_after_ref_hash": None,
            "state_delta_ref_hash": None,
            "causal_status": str(reviewer.get("causal_verifier_before_after_status") or reviewer.get("causal_linkage_status") or "missing_causal_verifier_linkage"),
            "basis_codes": common_basis + ["co_presence_is_not_causal_linkage"],
        },
        "stop_continue": {
            "label_enum": "missing_stop_continue_proof",
            "terminal_or_continuation_state_ref_hash": None,
            "proof_status": "missing_stop_continue_proof",
            "basis_codes": common_basis + ["stop_continue_must_be_recovered_from_state_after"],
        },
    }


def score_components(
    reviewer: dict[str, Any],
    skeleton: dict[str, Any],
    source_packet: dict[str, Any],
) -> dict[str, int]:
    missing = reviewer.get("missing_proof_codes") if isinstance(reviewer.get("missing_proof_codes"), list) else []
    bounded_counts = reviewer.get("bounded_counts") if isinstance(reviewer.get("bounded_counts"), dict) else {}
    event_bucket = str(skeleton.get("event_count_bucket") or bounded_counts.get("event_count_bucket") or "none")
    action_present = int(str(reviewer.get("explicit_action_label_status") or "") == "explicit_action_class_present")
    private_inspected = int(str(reviewer.get("raw_private_inspection_status") or "") == "raw_ref_private_inspected")
    source_signal = int(bool(source_packet.get("patch_signal_class") or source_packet.get("test_signal_class")))
    verifier_signal_count = len(bounded_counts.get("verifier_signal_codes") or [])
    patch_signal_count = len(bounded_counts.get("patch_signal_codes") or [])
    blocker_count = len(reviewer.get("blockers") or [])
    return {
        "missing_proof_count": len(missing),
        "missing_proof_weight": len(missing) * 12,
        "explicit_action_signal": action_present * 8,
        "private_inspection_signal": private_inspected * 5,
        "ordered_event_bucket_signal": event_bucket_score(event_bucket),
        "source_metadata_signal": source_signal * 4,
        "verifier_signal_diversity": min(verifier_signal_count, 6),
        "patch_signal_diversity": min(patch_signal_count, 4),
        "hard_blocker_penalty": blocker_count,
    }


def total_score(components: dict[str, int]) -> int:
    return (
        components["missing_proof_weight"]
        + components["explicit_action_signal"]
        + components["private_inspection_signal"]
        + components["ordered_event_bucket_signal"]
        + components["source_metadata_signal"]
        + components["verifier_signal_diversity"]
        + components["patch_signal_diversity"]
        - components["hard_blocker_penalty"]
    )


def build_candidate(
    reviewer: dict[str, Any],
    skeletons_by_id: dict[str, dict[str, Any]],
    source_packets_by_hash: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    skeleton = skeletons_by_id.get(str(reviewer.get("source_skeleton_packet_id") or ""), {})
    source_hash = str(skeleton.get("source_packet_hash") or reviewer.get("source_ref_hashes", {}).get("source_packet_hash") or "")
    source_packet = source_packets_by_hash.get(source_hash, {})
    missing = [str(code) for code in reviewer.get("missing_proof_codes") or []]
    if "missing_stop_continue_proof" not in missing:
        missing.append("missing_stop_continue_proof")
    hydration_tasks = requested_hydration_tasks(missing)
    if "hydrate_stop_continue_label_and_proof_hash" not in hydration_tasks:
        hydration_tasks.append("hydrate_stop_continue_label_and_proof_hash")
    hydration_tasks = sorted(set(hydration_tasks))
    blockers = sorted(set(str(blocker) for blocker in reviewer.get("blockers") or []))
    if "missing_stop_continue_proof" not in blockers:
        blockers.append("missing_stop_continue_proof")
    blockers = sorted(set(blockers))
    components = score_components(reviewer, skeleton, source_packet)
    source_refs = reviewer.get("source_ref_hashes") if isinstance(reviewer.get("source_ref_hashes"), dict) else {}
    bounded_packet = (
        reviewer.get("bounded_transition_review_packet")
        if isinstance(reviewer.get("bounded_transition_review_packet"), dict)
        else {}
    )
    proof_hashes = (
        bounded_packet.get("proof_artifact_hashes")
        if isinstance(bounded_packet.get("proof_artifact_hashes"), dict)
        else {}
    )
    refs = {
        "stage12399_reviewer_packet_hash": stable_hash(reviewer.get("packet_id") or "missing", 24),
        "stage12398_skeleton_packet_hash": stable_hash(reviewer.get("source_skeleton_packet_id") or "missing", 24),
        "stage12395_semantic_packet_hash": source_hash or str(source_refs.get("source_packet_hash") or "missing"),
        "candidate_transition_window_ref_hash": str(reviewer.get("candidate_transition_window_ref_hash") or "missing"),
    }
    return {
        "stage": STAGE,
        "record_type": "blocked_open_swe_external_replay_hydration_worklist_item",
        "worklist_item_id": f"{STAGE}::{stable_hash(refs, 20)}",
        "selected": False,
        "selection_rank": None,
        "source_rank": int(source_packet.get("rank") or skeleton.get("rank") or 0),
        "packet_refs": refs,
        "language_family": str(reviewer.get("language_family") or skeleton.get("language_family") or "unknown"),
        "repo_family_hash": str(reviewer.get("repo_family_hash") or source_packet.get("repo_family_hash") or "missing"),
        "source_ref_hashes": {
            "source_record_ref_hash": str(source_refs.get("source_record_ref_hash") or proof_hashes.get("source_record_ref_hash") or "missing"),
            "source_packet_hash": str(source_refs.get("source_packet_hash") or proof_hashes.get("source_packet_hash") or "missing"),
            "skeleton_packet_hash": str(source_refs.get("skeleton_packet_hash") or "missing"),
            "window_basis_hash": str(proof_hashes.get("window_basis_hash") or reviewer.get("candidate_transition_window_ref_hash") or "missing"),
        },
        "rank_score_components": components,
        "rank_score_total": total_score(components),
        "missing_proof_fields_to_recover": missing,
        "missing_proof_codes": missing,
        "proof_recovery_slots": proof_recovery_slots(reviewer),
        "requested_hydration_tasks": hydration_tasks,
        "hydration_tasks": hydration_tasks,
        "hard_blockers": blockers,
        "blockers": blockers,
        "bounded_status_context": {
            "action_label_candidate": str(reviewer.get("action_label_candidate") or "missing"),
            "state_before_status": str(reviewer.get("state_before_status") or "missing"),
            "state_after_status": str(reviewer.get("state_after_status") or "missing"),
            "verifier_relevance_status": str(reviewer.get("verifier_relevance_status") or "missing"),
            "patch_application_status": str(reviewer.get("patch_application_status") or "missing"),
            "causal_linkage_status": str(reviewer.get("causal_linkage_status") or "missing"),
            "raw_private_inspection_status": str(reviewer.get("raw_private_inspection_status") or "missing"),
        },
        "bounded_counts": reviewer.get("bounded_counts") if isinstance(reviewer.get("bounded_counts"), dict) else {},
        "claim_boundary": {
            "external_replay_request_only": True,
            "training_admission_claim_emitted": False,
            "authoritative_state_claim_emitted": False,
            "verifier_relevance_claim_emitted": False,
            "patch_application_claim_emitted": False,
            "causal_linkage_claim_emitted": False,
            "raw_content_request_emitted": False,
        },
        "raw_content_policy": RAW_CONTENT_POLICY,
        "admission": False,
        **ZERO_ADMISSION,
    }


def select_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending = sorted(
        candidates,
        key=lambda row: (
            -int(row.get("rank_score_total") or 0),
            int(row.get("source_rank") or 999999),
            str(row.get("language_family") or ""),
            str(row.get("repo_family_hash") or ""),
        ),
    )
    selected: list[dict[str, Any]] = []
    per_language: Counter[str] = Counter()
    per_repo: Counter[str] = Counter()

    # First pass: two per language when available, preserving score order.
    for candidate in pending:
        language = str(candidate.get("language_family") or "unknown")
        repo_hash = str(candidate.get("repo_family_hash") or "missing")
        if len(selected) >= EXPECTED_MAX_SELECTED:
            break
        if per_language[language] >= 2 or per_repo[repo_hash] >= 1:
            continue
        selected.append(candidate)
        per_language[language] += 1
        per_repo[repo_hash] += 1

    # Second pass: fill remaining slots with highest-scoring unique repos.
    selected_ids = {str(row.get("worklist_item_id")) for row in selected}
    for candidate in pending:
        repo_hash = str(candidate.get("repo_family_hash") or "missing")
        if len(selected) >= EXPECTED_MAX_SELECTED:
            break
        if str(candidate.get("worklist_item_id")) in selected_ids or per_repo[repo_hash] >= 1:
            continue
        selected.append(candidate)
        selected_ids.add(str(candidate.get("worklist_item_id")))
        per_repo[repo_hash] += 1

    for rank, row in enumerate(selected, 1):
        row["selected"] = True
        row["selection_rank"] = rank
    return sorted(selected, key=lambda row: int(row.get("selection_rank") or 0))


def validate_item(row: dict[str, Any], row_index: int) -> list[str]:
    issues: list[str] = []
    required = [
        "worklist_item_id",
        "packet_refs",
        "language_family",
        "repo_family_hash",
        "source_ref_hashes",
        "rank_score_components",
        "rank_score_total",
        "missing_proof_fields_to_recover",
        "missing_proof_codes",
        "proof_recovery_slots",
        "requested_hydration_tasks",
        "hydration_tasks",
        "hard_blockers",
        "blockers",
        "claim_boundary",
        "raw_content_policy",
        "admission",
    ]
    for key in required:
        if key not in row:
            issues.append(f"row_{row_index}_missing_{key}")
    for key, expected in ZERO_ADMISSION.items():
        if row.get(key) != expected:
            issues.append(f"row_{row_index}_{key}_not_zero_or_false")
    if row.get("admission") is not False:
        issues.append(f"row_{row_index}_admission_not_false")
    if not row.get("hard_blockers") or not row.get("blockers"):
        issues.append(f"row_{row_index}_missing_hard_blockers")
    slots = row.get("proof_recovery_slots") if isinstance(row.get("proof_recovery_slots"), dict) else {}
    for slot_key in [
        "authoritative_state_before",
        "authoritative_state_after",
        "explicit_action_label",
        "verifier_relevance",
        "patch_application",
        "causal_verifier_linkage",
        "stop_continue",
    ]:
        if slot_key not in slots:
            issues.append(f"row_{row_index}_missing_proof_recovery_slot_{slot_key}")
    missing = row.get("missing_proof_fields_to_recover")
    if not isinstance(missing, list) or not missing:
        issues.append(f"row_{row_index}_missing_proof_recovery_list_empty")
    refs = row.get("packet_refs") if isinstance(row.get("packet_refs"), dict) else {}
    source_refs = row.get("source_ref_hashes") if isinstance(row.get("source_ref_hashes"), dict) else {}
    for ref_key, ref_value in {**refs, **source_refs}.items():
        if ref_value in {None, ""}:
            issues.append(f"row_{row_index}_{ref_key}_empty_ref")
    claim_boundary = row.get("claim_boundary") if isinstance(row.get("claim_boundary"), dict) else {}
    for forbidden_claim in [
        "training_admission_claim_emitted",
        "authoritative_state_claim_emitted",
        "verifier_relevance_claim_emitted",
        "patch_application_claim_emitted",
        "causal_linkage_claim_emitted",
        "raw_content_request_emitted",
    ]:
        if claim_boundary.get(forbidden_claim) is not False:
            issues.append(f"row_{row_index}_{forbidden_claim}_not_false")
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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12395_packets = read_jsonl(STAGE12395_PACKETS)
    stage12398_skeletons = read_jsonl(STAGE12398_SKELETONS)
    stage12399_review_packets = read_jsonl(STAGE12399_REVIEW_PACKETS)
    stage12399_summary = read_json(STAGE12399_SUMMARY)

    source_packets_by_hash = source_packet_index(stage12395_packets)
    skeletons_by_id = skeleton_index(stage12398_skeletons)
    candidates = [
        build_candidate(row, skeletons_by_id, source_packets_by_hash)
        for row in stage12399_review_packets
        if isinstance(row, dict)
    ]
    selected = select_candidates(candidates)

    row_path = OUT / ROWS_NAME
    local_summary_path = OUT / LOCAL_SUMMARY_NAME
    guardrail_path = OUT / GUARDRAIL_NAME
    write_jsonl(row_path, selected)

    schema_issues = [issue for idx, row in enumerate(selected, 1) for issue in validate_item(row, idx)]
    selected_language_counts = Counter(str(row.get("language_family") or "unknown") for row in selected)
    input_language_counts = Counter(str(row.get("language_family") or "unknown") for row in candidates)
    blocker_counts = Counter(blocker for row in selected for blocker in row.get("hard_blockers", []))
    missing_proof_counts = Counter(code for row in selected for code in row.get("missing_proof_fields_to_recover", []))
    task_counts = Counter(task for row in selected for task in row.get("requested_hydration_tasks", []))
    score_totals = [int(row.get("rank_score_total") or 0) for row in selected]

    upstream_zero_ok = all(
        stage12399_summary.get(key) == expected
        for key, expected in {
            "training_allowed": False,
            "level3_admitted": 0,
            "patch_trace_admitted": 0,
            "strict_eval_eligible": 0,
            "source_heldout_admissible": 0,
        }.items()
    )

    summary: dict[str, Any] = {
        "stage": STAGE,
        "decision": "fail_closed_external_replay_hydration_worklist_ready_no_admissions",
        "source_stages": [
            "stage12395_open_swe_multilingual_semantic_packet_preflight",
            "stage12398_open_swe_ordered_event_skeleton_35_preflight",
            "stage12399_open_swe_semantic_transition_reviewer",
        ],
        "input_counts": {
            "stage12395_semantic_packet_count": len(stage12395_packets),
            "stage12398_ordered_skeleton_count": len(stage12398_skeletons),
            "stage12399_review_packet_count": len(stage12399_review_packets),
            "candidate_count": len(candidates),
        },
        "expected_max_selected": EXPECTED_MAX_SELECTED,
        "input_packet_count": len(stage12399_review_packets),
        "selected_count": len(selected),
        "selected_worklist_count": len(selected),
        "selection_policy": "score_ordered_language_balanced_unique_repo_cap_15",
        "language_distribution": {
            "input": dict(sorted(input_language_counts.items())),
            "selected": dict(sorted(selected_language_counts.items())),
        },
        "repo_family_hash_counts": {
            "input_unique_repo_family_hash_count": len({row.get("repo_family_hash") for row in candidates}),
            "selected_unique_repo_family_hash_count": len({row.get("repo_family_hash") for row in selected}),
        },
        "unique_selected_repo_hashes": len({row.get("repo_family_hash") for row in selected}),
        "admitted_packet_count": 0,
        "rank_score_summary": {
            "min": min(score_totals) if score_totals else 0,
            "max": max(score_totals) if score_totals else 0,
            "selected_score_total_sum": sum(score_totals),
        },
        "missing_proof_field_counts": dict(sorted(missing_proof_counts.items())),
        "requested_hydration_task_counts": dict(sorted(task_counts.items())),
        "hard_blocker_counts": dict(sorted(blocker_counts.items())),
        "zero_admission_flags": {
            **ZERO_ADMISSION,
            "admitted_worklist_item_count": 0,
            "upstream_stage12399_zero_admission_confirmed": upstream_zero_ok,
        },
        "raw_content_policy": RAW_CONTENT_POLICY,
        "raw_leak_scan": None,
        "raw_leak_findings": [],
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "claim_boundary": {
            "external_replay_request_only": True,
            "hydration_required_before_any_training": True,
            "all_selected_records_blocked": True,
            "training_admission_claim_emitted": False,
            "authoritative_state_claim_emitted": False,
            "verifier_relevance_claim_emitted": False,
            "patch_application_claim_emitted": False,
            "causal_linkage_claim_emitted": False,
            "raw_content_request_emitted": False,
        },
        "generated_artifacts": [ROWS_NAME, LOCAL_SUMMARY_NAME, GUARDRAIL_NAME],
        **ZERO_ADMISSION,
    }
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)

    guardrail = guardrail_scan([row_path, local_summary_path, SUMMARY])
    write_json(guardrail_path, guardrail)
    summary["raw_leak_scan"] = guardrail
    summary["raw_leak_findings"] = guardrail["issues"]
    summary["guardrail_issue_count"] = len(guardrail["issues"])
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)

    if schema_issues or guardrail["issues"] or len(selected) > EXPECTED_MAX_SELECTED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
