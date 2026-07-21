#!/usr/bin/env python3
"""Stage12401 fail-closed Open-SWE raw-private hydration preflight.

Consumes the Stage12400 selected worklist plus Stage12399 reviewer packets,
Stage12395 semantic packets, and Stage12327 Open-SWE candidates/private refs.
Emitted artifacts contain only hashes, classes, counts, booleans, and status
codes. No raw commands, outputs, paths, URLs, source text, issue bodies, or
diffs are emitted. If hydration proof is not already established by bounded
artifacts, the relevant slot is blocked rather than inferred.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12401_open_swe_raw_private_hydration_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12400_WORKLIST = (
    ROOT
    / "runs/local/artifacts/stage12400_open_swe_replay_hydration_worklist/"
    / "open_swe_replay_hydration_worklist.jsonl"
)
STAGE12400_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12400_open_swe_replay_hydration_worklist/"
    / "open_swe_replay_hydration_worklist_summary.json"
)
STAGE12399_PACKETS = (
    ROOT
    / "runs/local/artifacts/stage12399_open_swe_semantic_transition_reviewer/"
    / "open_swe_semantic_transition_reviewer_packets.jsonl"
)
STAGE12399_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12399_open_swe_semantic_transition_reviewer/"
    / "open_swe_semantic_transition_reviewer_summary.json"
)
STAGE12395_PACKETS = (
    ROOT
    / "runs/local/artifacts/stage12395_open_swe_multilingual_semantic_packet_preflight/"
    / "open_swe_multilingual_semantic_packet_preflight.jsonl"
)
STAGE12327_CANDIDATES = (
    ROOT
    / "runs/local/artifacts/stage12327_external_adapter_preflight/"
    / "open_swe_trace_support_candidates.jsonl"
)

ROWS_NAME = "open_swe_raw_private_hydration_preflight.jsonl"
LOCAL_SUMMARY_NAME = "open_swe_raw_private_hydration_preflight_summary.json"
GUARDRAIL_NAME = "guardrail_scan.json"
EXPECTED_ITEM_COUNT = 15

SLOT_KEYS = (
    "authoritative_state_before",
    "authoritative_state_after",
    "explicit_action_label",
    "verifier_relevance",
    "patch_application",
    "causal_verifier_linkage",
    "stop_continue",
)
PROOF_COUNT_KEYS = (
    "authoritative_state_before",
    "authoritative_state_after",
    "explicit_action_label",
    "verifier_relevance",
    "patch_application",
    "causal_verifier_linkage",
    "stop_continue",
)
ZERO_ADMISSION: dict[str, int | bool] = {
    "training_allowed": False,
    "training_row_count": 0,
    "level3_admitted": 0,
    "patch_trace_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
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

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
MULTILINE_RE = re.compile(r"[\r\n]")
HEX_RE = re.compile(r"^[0-9a-f]{12,64}$")
RAW_KEY_RE = re.compile(
    r"(?:^|_)(trajectory|command|output|patch|diff|source_text|issue_body|line_content|stdout|stderr|url|path)(?:$|_)",
    re.IGNORECASE,
)
SAFE_KEY_CONTEXT_RE = re.compile(
    r"(?:status|code|codes|proof|gate|hash|hashes|class|classes|signal|policy|count|counts|bucket|ref|refs|emitted|allowed|stage|scan)",
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


def index_by_packet_hash(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {stable_hash(row.get("packet_id") or "missing", 24): row for row in rows}


def index_semantic_packet_hash(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {stable_hash(row.get("packet_id") or "missing", 20): row for row in rows}


def index_private_ref_hash(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        ref = row.get("source_record_ref") if isinstance(row.get("source_record_ref"), dict) else {}
        if ref:
            out[stable_hash(ref, 24)] = ref
    return out


def bool_passed(value: Any) -> bool:
    if isinstance(value, dict):
        return value.get("passed") is True
    return False


def bounded_status_for_slot(slot: str, worklist_row: dict[str, Any], reviewer: dict[str, Any]) -> str:
    slots = worklist_row.get("proof_recovery_slots") if isinstance(worklist_row.get("proof_recovery_slots"), dict) else {}
    slot_value = slots.get(slot) if isinstance(slots.get(slot), dict) else {}
    if slot == "authoritative_state_before":
        return str(slot_value.get("status") or reviewer.get("state_before_status") or "missing_authoritative_state_before")
    if slot == "authoritative_state_after":
        return str(slot_value.get("status") or reviewer.get("state_after_status") or "missing_authoritative_state_after")
    if slot == "explicit_action_label":
        return str(slot_value.get("proof_status") or reviewer.get("explicit_action_label_status") or "missing_explicit_action_label")
    if slot == "verifier_relevance":
        return str(slot_value.get("relevance_status") or reviewer.get("verifier_relevance_status") or "missing_verifier_relevance_proof")
    if slot == "patch_application":
        return str(slot_value.get("apply_status") or reviewer.get("patch_application_status") or "missing_patch_application_proof")
    if slot == "causal_verifier_linkage":
        return str(slot_value.get("causal_status") or reviewer.get("causal_linkage_status") or "missing_causal_verifier_linkage")
    if slot == "stop_continue":
        return str(slot_value.get("proof_status") or "missing_stop_continue_proof")
    raise AssertionError(slot)


def blocker_for_slot(slot: str, bounded_status: str) -> str:
    if slot == "authoritative_state_before":
        return "blocked_missing_authoritative_state_before"
    if slot == "authoritative_state_after":
        return "blocked_missing_authoritative_state_after"
    if slot == "explicit_action_label":
        if bounded_status == "explicit_action_class_present":
            return "blocked_explicit_action_label_has_class_signal_not_authoritative_proof"
        return "blocked_missing_explicit_action_label"
    if slot == "verifier_relevance":
        return "blocked_missing_verifier_relevance_proof"
    if slot == "patch_application":
        return "blocked_missing_patch_application_proof"
    if slot == "causal_verifier_linkage":
        return "blocked_missing_causal_verifier_linkage"
    if slot == "stop_continue":
        return "blocked_missing_stop_continue_proof"
    raise AssertionError(slot)


def proof_count_for_slot(slot: str, reviewer: dict[str, Any]) -> int:
    # Stage12399 proof gates are bounded-skeleton diagnostics, not raw-private
    # hydration proof. Even explicit action class must stay blocked until it is
    # linked to one authoritative action-event proof hash.
    return 0


def proof_recovery_slots(worklist_row: dict[str, Any], reviewer: dict[str, Any]) -> dict[str, dict[str, Any]]:
    slots: dict[str, dict[str, Any]] = {}
    for slot in SLOT_KEYS:
        bounded_status = bounded_status_for_slot(slot, worklist_row, reviewer)
        proof_count = proof_count_for_slot(slot, reviewer)
        if proof_count:
            hydration_status = "proof_recovered_from_bounded_artifact"
            blocker_code = None
        else:
            hydration_status = "blocked_real_hydration_not_proven"
            blocker_code = blocker_for_slot(slot, bounded_status)
        slots[slot] = {
            "status": hydration_status,
            "bounded_input_status": bounded_status,
            "recovered_proof_count": proof_count,
            "proof_ref_hash": "missing",
            "blocker_code": blocker_code,
        }
    return slots


def recovered_proof_counts(slots: dict[str, dict[str, Any]]) -> dict[str, int]:
    return {
        key: int(slots.get(key, {}).get("recovered_proof_count") or 0)
        for key in PROOF_COUNT_KEYS
    }


def build_item(
    row: dict[str, Any],
    reviewers_by_hash: dict[str, dict[str, Any]],
    semantic_by_hash: dict[str, dict[str, Any]],
    private_refs_by_hash: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    packet_refs = row.get("packet_refs") if isinstance(row.get("packet_refs"), dict) else {}
    source_refs = row.get("source_ref_hashes") if isinstance(row.get("source_ref_hashes"), dict) else {}
    reviewer_hash = str(packet_refs.get("stage12399_reviewer_packet_hash") or "missing")
    semantic_hash = str(packet_refs.get("stage12395_semantic_packet_hash") or source_refs.get("source_packet_hash") or "missing")
    private_ref_hash = str(source_refs.get("source_record_ref_hash") or "missing")
    reviewer = reviewers_by_hash.get(reviewer_hash, {})
    semantic_packet = semantic_by_hash.get(semantic_hash, {})
    private_ref = private_refs_by_hash.get(private_ref_hash, {})
    slots = proof_recovery_slots(row, reviewer)
    counts = recovered_proof_counts(slots)
    unresolved = sorted(
        {
            str(slot.get("blocker_code"))
            for slot in slots.values()
            if slot.get("blocker_code")
        }
        | {str(blocker) for blocker in row.get("blockers", [])}
        | {
            "blocked_fail_closed_raw_private_hydration_preflight",
            "no_raw_private_proof_material_emitted",
            "training_admission_blocked",
        }
    )
    raw_private_status = str(reviewer.get("raw_private_inspection_status") or "missing")
    semantic_raw_status = str(semantic_packet.get("raw_private_access_status") or "missing")
    if private_ref:
        private_ref_status = "private_ref_hash_joined"
    elif private_ref_hash == "missing":
        private_ref_status = "private_ref_hash_missing"
    else:
        private_ref_status = "private_ref_hash_not_joined"

    return {
        "stage": STAGE,
        "record_type": "blocked_open_swe_raw_private_hydration_preflight_item",
        "preflight_item_id": f"{STAGE}::{stable_hash(row.get('worklist_item_id') or packet_refs, 20)}",
        "source_worklist_item_hash": stable_hash(row.get("worklist_item_id") or "missing", 24),
        "selection_rank": int(row.get("selection_rank") or 0),
        "language_family": str(row.get("language_family") or "unknown"),
        "repo_family_hash": str(row.get("repo_family_hash") or "missing"),
        "source_stage_ref_hashes": {
            "stage12400_item_hash": stable_hash(row.get("worklist_item_id") or "missing", 24),
            "stage12399_reviewer_packet_hash": reviewer_hash,
            "stage12395_semantic_packet_hash": semantic_hash,
            "stage12327_private_ref_hash": private_ref_hash,
            "candidate_transition_window_ref_hash": str(packet_refs.get("candidate_transition_window_ref_hash") or "missing"),
        },
        "hydration_input_status_codes": {
            "stage12400_selected_status": "selected_worklist_item_present" if row.get("selected") is True else "not_selected",
            "stage12399_reviewer_join_status": "reviewer_packet_joined" if reviewer else "reviewer_packet_not_joined",
            "stage12395_semantic_join_status": "semantic_packet_joined" if semantic_packet else "semantic_packet_not_joined",
            "stage12327_private_ref_join_status": private_ref_status,
            "raw_private_inspection_status": raw_private_status,
            "semantic_raw_private_access_status": semantic_raw_status,
        },
        "proof_recovery_slots": slots,
        "recovered_proof_counts": counts,
        "recovered_proof_count": sum(counts.values()),
        "recovered_proof_total": sum(counts.values()),
        "unresolved_blockers": unresolved,
        "admission": False,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": {
            "raw_private_hydration_preflight_only": True,
            "raw_private_content_emitted": False,
            "authoritative_state_claim_emitted": False,
            "verifier_relevance_claim_emitted": False,
            "patch_application_claim_emitted": False,
            "causal_linkage_claim_emitted": False,
            "training_admission_claim_emitted": False,
        },
        **ZERO_ADMISSION,
    }


def validate_item(row: dict[str, Any], index: int) -> list[str]:
    issues: list[str] = []
    required = [
        "proof_recovery_slots",
        "recovered_proof_counts",
        "unresolved_blockers",
        "admission",
        "training_allowed",
        "training_row_count",
        "level3_admitted",
        "patch_trace_admitted",
        "strict_eval_eligible",
        "source_heldout_admissible",
    ]
    for key in required:
        if key not in row:
            issues.append(f"row_{index}_missing_{key}")
    for key in SLOT_KEYS:
        slot = row.get("proof_recovery_slots", {}).get(key) if isinstance(row.get("proof_recovery_slots"), dict) else None
        if not isinstance(slot, dict):
            issues.append(f"row_{index}_missing_slot_{key}")
        elif slot.get("status") not in {"blocked_real_hydration_not_proven", "proof_recovered_from_bounded_artifact"}:
            issues.append(f"row_{index}_slot_{key}_invalid_status")
    counts = row.get("recovered_proof_counts")
    if not isinstance(counts, dict):
        issues.append(f"row_{index}_missing_recovered_proof_counts")
    else:
        for key in PROOF_COUNT_KEYS:
            if counts.get(key) not in {0, 1}:
                issues.append(f"row_{index}_invalid_recovered_count_{key}")
    for key, expected in ZERO_ADMISSION.items():
        if row.get(key) != expected:
            issues.append(f"row_{index}_{key}_not_zero_or_false")
    if row.get("admission") is not False:
        issues.append(f"row_{index}_admission_not_false")
    if not row.get("unresolved_blockers"):
        issues.append(f"row_{index}_unresolved_blockers_empty")
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
        for idx, child in enumerate(value):
            scan_value(child, artifact, issues, f"{key_path}[{idx}]")
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
    worklist = [row for row in read_jsonl(STAGE12400_WORKLIST) if row.get("selected") is True]
    stage12400_summary = read_json(STAGE12400_SUMMARY)
    stage12399_packets = read_jsonl(STAGE12399_PACKETS)
    stage12399_summary = read_json(STAGE12399_SUMMARY)
    stage12395_packets = read_jsonl(STAGE12395_PACKETS)
    stage12327_candidates = read_jsonl(STAGE12327_CANDIDATES)

    reviewers_by_hash = index_by_packet_hash(stage12399_packets)
    semantic_by_hash = index_semantic_packet_hash(stage12395_packets)
    private_refs_by_hash = index_private_ref_hash(stage12327_candidates)
    rows = [
        build_item(row, reviewers_by_hash, semantic_by_hash, private_refs_by_hash)
        for row in sorted(worklist, key=lambda item: int(item.get("selection_rank") or 0))
    ]

    row_path = OUT / ROWS_NAME
    local_summary_path = OUT / LOCAL_SUMMARY_NAME
    guardrail_path = OUT / GUARDRAIL_NAME
    write_jsonl(row_path, rows)

    schema_issues = [issue for idx, row in enumerate(rows, 1) for issue in validate_item(row, idx)]
    slot_status_counts: dict[str, dict[str, int]] = {}
    for key in SLOT_KEYS:
        slot_status_counts[key] = dict(
            sorted(Counter(str(row["proof_recovery_slots"][key]["status"]) for row in rows).items())
        )
    recovered_totals = Counter()
    for row in rows:
        recovered_totals.update({key: int(value) for key, value in row["recovered_proof_counts"].items()})
    blocker_counts = Counter(blocker for row in rows for blocker in row.get("unresolved_blockers", []))
    language_counts = Counter(str(row.get("language_family") or "unknown") for row in rows)
    hydration_status_counts = Counter(
        str(row.get("hydration_input_status_codes", {}).get("raw_private_inspection_status") or "missing")
        for row in rows
    )

    upstream_zero_ok = all(
        stage12400_summary.get(key) == expected and stage12399_summary.get(key) == expected
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
        "decision": "fail_closed_raw_private_hydration_preflight_blocked_no_admissions",
        "source_stages": [
            "stage12400_open_swe_replay_hydration_worklist",
            "stage12399_open_swe_semantic_transition_reviewer",
            "stage12395_open_swe_multilingual_semantic_packet_preflight",
            "stage12327_external_adapter_preflight",
        ],
        "source_stage_artifact_hashes": {
            "stage12400_worklist_hash": stage_file_hash(STAGE12400_WORKLIST),
            "stage12399_packets_hash": stage_file_hash(STAGE12399_PACKETS),
            "stage12395_packets_hash": stage_file_hash(STAGE12395_PACKETS),
            "stage12327_candidates_hash": stage_file_hash(STAGE12327_CANDIDATES),
        },
        "input_counts": {
            "stage12400_selected_worklist_count": len(worklist),
            "stage12399_review_packet_count": len(stage12399_packets),
            "stage12395_semantic_packet_count": len(stage12395_packets),
            "stage12327_open_swe_candidate_count": len(stage12327_candidates),
        },
        "expected_item_count": EXPECTED_ITEM_COUNT,
        "input_worklist_count": len(worklist),
        "output_preflight_row_count": len(rows),
        "preflight_item_count": len(rows),
        "admitted_packet_count": 0,
        "training_row_count": 0,
        "language_distribution": dict(sorted(language_counts.items())),
        "raw_private_inspection_status_counts": dict(sorted(hydration_status_counts.items())),
        "proof_recovery_slot_status_counts": slot_status_counts,
        "proof_slot_status_counts": slot_status_counts,
        "recovered_proof_counts": dict(sorted(recovered_totals.items())),
        "recovered_proof_total": sum(recovered_totals.values()),
        "unresolved_blocker_counts": dict(sorted(blocker_counts.items())),
        "zero_admission_flags": {
            **ZERO_ADMISSION,
            "admitted_preflight_item_count": 0,
            "upstream_zero_admission_confirmed": upstream_zero_ok,
        },
        "claim_boundary": {
            "raw_private_hydration_preflight_only": True,
            "all_items_blocked_until_real_hydration_proof": True,
            "raw_private_content_emitted": False,
            "raw_commands_emitted": False,
            "raw_outputs_emitted": False,
            "raw_paths_emitted": False,
            "raw_urls_emitted": False,
            "source_text_emitted": False,
            "issue_bodies_emitted": False,
            "patch_diffs_emitted": False,
            "training_admission_claim_emitted": False,
        },
        "raw_content_policy": RAW_CONTENT_POLICY,
        "raw_leak_scan": None,
        "raw_leak_findings": [],
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
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

    if schema_issues or guardrail["issues"] or len(rows) != EXPECTED_ITEM_COUNT:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
