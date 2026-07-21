#!/usr/bin/env python3
"""Stage12406 fail-closed source-expansion preflight.

Inventories candidate source adapters for post-Stage12405 scaling. This script
emits only source_adapter_candidate records with hashed source references,
aggregate counts, and fail-closed tier assignments. It creates no training or
eval rows, emits no raw content, runs no replay, and makes no Level-3 claim.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12406_transition_source_expansion_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

CANDIDATES_NAME = "source_adapter_candidates.jsonl"
LOCAL_SUMMARY_NAME = "source_expansion_preflight_summary.json"
FAMILY_COUNTS_NAME = "source_family_counts.json"
GUARDRAIL_NAME = "guardrail_scan.json"

TIERS = [
    "weak_digest_supervision",
    "replay_request_pending",
    "replay_calibrated_supervision",
    "level3_reconstructed_proof",
    "sealed_eval_only",
    "quarantine",
]

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

CLAIM_BOUNDARY: dict[str, bool | str] = {
    "boundary": "source_adapter_candidate_inventory_only",
    "training_rows_created": False,
    "eval_rows_created": False,
    "training_admission_claim_emitted": False,
    "eval_admission_claim_emitted": False,
    "level3_claim_emitted": False,
    "patch_trace_claim_emitted": False,
    "repair_claim_emitted": False,
    "source_heldout_admission_claim_emitted": False,
    "replay_executed": False,
    "proof_assistant_invoked": False,
    "raw_content_emitted": False,
}

ZERO_ADMISSION_FLAGS: dict[str, bool | int] = {
    "admission": False,
    "training_allowed": False,
    "training_row_count": 0,
    "eval_row_count": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level4_admitted": 0,
    "patch_trace_admitted": 0,
    "repair_claim_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
    "level3_reconstructed_proof": 0,
    "external_comparable_patch_trace_countable": 0,
    "external_fail_to_pass_countable": 0,
    "synthetic_fixture_external_repair_countable": 0,
    "selected_test_full_repair_claim_count": 0,
    "sealed_eval_train_overlap_count": 0,
}

PROOF_SLOT_STATUS = {
    "state_before": "blocked_missing_authoritative_state_before",
    "state_after": "blocked_missing_authoritative_state_after",
    "patch_application": "blocked_missing_patch_application_proof",
    "verifier_identity": "blocked_missing_authoritative_verifier_identity",
    "verifier_relevance": "blocked_missing_verifier_relevance_proof",
    "verifier_output_class": "blocked_missing_authoritative_verifier_output_class",
    "causal_linkage": "blocked_missing_causal_verifier_linkage",
    "same_source_ordering": "blocked_same_source_ordering_not_reverified",
    "stop_continue": "blocked_missing_stop_continue_proof",
    "correct_next_action_policy": "blocked_correct_next_action_not_authoritatively_proven",
    "root_split_no_leak": "blocked_root_split_no_leak_not_reverified",
    "option_permutation": "blocked_option_permutation_safety_not_reverified",
    "selected_test_scope": "blocked_selected_test_scope_not_authoritatively_verified",
    "sealed_eval_exclusion": "blocked_sealed_eval_exclusion_not_reverified",
    "synthetic_fixture_externality": "blocked_synthetic_fixture_externality_not_reverified",
}

BASE_BLOCKERS = [
    "blocked_source_adapter_candidate_only",
    "blocked_no_training_rows_created",
    "blocked_no_eval_rows_created",
    "blocked_no_level3_claim",
    "blocked_no_patch_trace_admission",
    "blocked_no_source_heldout_admission",
    "blocked_replay_not_executed_by_stage12406",
    "blocked_raw_content_not_emitted",
    "fail_closed_if_uncertain",
]

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
MULTILINE_RE = re.compile(r"[\r\n]")
HEX_RE = re.compile(r"^[0-9a-f]{12,64}$")
STAGE_RE = re.compile(r"(stage\d+_[A-Za-z0-9_]+)")
RAWISH_NAME_RE = re.compile(r"(raw|private|trajectory|command|output|stdout|stderr|patch_body|diff|line_content|issue_body)", re.I)
LEAK_NAME_RE = re.compile(r"(leak|alias|singleton|schema_collapse|schema-collapse|raw_only|raw-only|overclaim|collapse)", re.I)
COUNT_KEY_RE = re.compile(r"(count|counts|rows|candidates|items|records|total)$", re.I)
LANG_KEY_RE = re.compile(r"(?:^|_)language_counts$", re.I)
REPLAY_REQUEST_RE = re.compile(r"(replay.*request|hydration.*request|reconstruction_request|state_reconstruction_request)", re.I)
REPLAY_CALIBRATED_RE = re.compile(r"(verifier_executor|replay_executor|reexecution|replay_smoke)", re.I)
SEALED_EVAL_RE = re.compile(r"(strict_eval|source_heldout|heldout)", re.I)


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:n]


def rel_label(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def stage_name(path: Path) -> str:
    match = STAGE_RE.search(rel_label(path))
    return match.group(1) if match else "not_stage_scoped"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def count_jsonl(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def discover_inputs() -> list[Path]:
    paths: set[Path] = set()

    explicit = [
        ROOT / "runs/summaries/stage12405_transition_proof_tier_policy.json",
        ROOT
        / "runs/local/artifacts/stage12405_transition_proof_tier_policy"
        / "open_swe_transition_proof_tier_policy_records.jsonl",
    ]
    paths.update(path for path in explicit if path.exists())

    artifact_root = ROOT / "runs/local/artifacts"
    summary_root = ROOT / "runs/summaries"
    artifact_patterns = [
        re.compile(r"stage1226[0-4]_"),
        re.compile(r"stage123[2-9][0-9]_.*(selected_test|v4|open_swe|bears|codex|session|event_local|transition_local)", re.I),
        re.compile(r"stage1240[0-5]_"),
        re.compile(r"strict_long_context", re.I),
        re.compile(r"multitarget|bootstrap", re.I),
    ]
    if artifact_root.exists():
        for child in artifact_root.iterdir():
            label = child.name
            if any(pattern.search(label) for pattern in artifact_patterns):
                paths.add(child)
                for card in child.glob("*card*.json"):
                    paths.add(card)
                for summary in child.glob("*summary*.json"):
                    paths.add(summary)
                for guard in child.glob("*guardrail*.json"):
                    paths.add(guard)

    summary_patterns = [
        re.compile(r"stage1226[0-4]_"),
        re.compile(r"stage123[2-9][0-9]_.*(selected_test|v4|open_swe|bears|codex|session|event_local|transition_local)", re.I),
        re.compile(r"stage1240[0-5]_"),
        re.compile(r"strict_long_context", re.I),
        re.compile(r"multitarget|bootstrap", re.I),
    ]
    if summary_root.exists():
        for child in summary_root.glob("*.json"):
            label = child.name
            if any(pattern.search(label) for pattern in summary_patterns):
                paths.add(child)

    return sorted(paths, key=lambda path: rel_label(path))


def find_json_files(path: Path) -> list[Path]:
    if path.is_file() and path.suffix == ".json":
        return [path]
    if not path.is_dir():
        return []
    return sorted(
        [
            child
            for child in path.rglob("*.json")
            if STAGE not in rel_label(child) and len(child.parts) - len(path.parts) <= 2
        ],
        key=lambda child: rel_label(child),
    )[:25]


def find_jsonl_files(path: Path) -> list[Path]:
    if path.is_file() and path.suffix == ".jsonl":
        return [path]
    if not path.is_dir():
        return []
    return sorted(
        [
            child
            for child in path.rglob("*.jsonl")
            if STAGE not in rel_label(child) and len(child.parts) - len(path.parts) <= 2
        ],
        key=lambda child: rel_label(child),
    )[:25]


def merge_language_counts(left: Counter[str], value: Any) -> None:
    if not isinstance(value, dict):
        return
    for key, count in value.items():
        if isinstance(count, bool):
            continue
        if isinstance(count, int):
            left[str(key)] += count


def walk_safe_counts(value: Any, counts: Counter[str], languages: Counter[str], depth: int = 0) -> None:
    if depth > 5:
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if LANG_KEY_RE.search(str(key)):
                merge_language_counts(languages, child)
            if COUNT_KEY_RE.search(str(key)) and isinstance(child, int) and not isinstance(child, bool):
                counts[str(key)] += max(0, int(child))
            elif isinstance(child, (dict, list)):
                walk_safe_counts(child, counts, languages, depth + 1)
        return
    if isinstance(value, list):
        for child in value[:200]:
            walk_safe_counts(child, counts, languages, depth + 1)


def summarize_source(path: Path) -> dict[str, Any]:
    json_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    jsonl_counts: Counter[str] = Counter()
    json_hashes: list[str] = []

    for json_path in find_json_files(path):
        data = read_json(json_path)
        if data:
            walk_safe_counts(data, json_counts, language_counts)
        json_hashes.append(file_hash(json_path))

    for jsonl_path in find_jsonl_files(path):
        jsonl_counts[jsonl_path.name] += count_jsonl(jsonl_path)

    observed = 0
    candidate_like_keys = [
        key for key in json_counts if re.search(r"(candidate|record|row|item|window|request|profile|family)", key, re.I)
    ]
    if candidate_like_keys:
        observed = max(json_counts[key] for key in candidate_like_keys)
    if jsonl_counts:
        observed = max(observed, max(jsonl_counts.values()))
    if observed == 0 and path.exists():
        observed = 1

    return {
        "observed_count_estimate": int(observed),
        "language_counts": dict(sorted(language_counts.items())),
        "safe_count_keys_seen": sorted(json_counts)[:40],
        "jsonl_file_count": len(jsonl_counts),
        "jsonl_record_count_estimate": int(sum(jsonl_counts.values())),
        "json_artifact_count": len(json_hashes),
        "content_digest_hash": stable_hash(sorted(json_hashes), 24),
    }


def source_family_for(label: str) -> str:
    text = label.lower()
    if "open_swe" in text:
        return "open_swe"
    if "bears" in text:
        return "bears"
    if "selected_test" in text:
        return "selected_test"
    if "v4" in text:
        return "v4_candidates"
    if "codex" in text or "session" in text or "event_local" in text or "transition_local" in text:
        return "codex_session_windows"
    if "strict_long_context" in text:
        return "strict_long_context"
    if "multitarget" in text or "bootstrap" in text:
        return "multitarget_bootstrap"
    if "stage12405" in text:
        return "transition_proof_tier_policy"
    return "other_candidate_source"


def has_authoritative_replay_metadata(path: Path, summary: dict[str, Any]) -> bool:
    label = rel_label(path).lower()
    if not REPLAY_CALIBRATED_RE.search(label):
        return False
    if path.is_dir() and any(child.suffix == ".log" for child in path.rglob("*.log")):
        return True
    safe_keys = json.dumps(sorted(summary.get("safe_count_keys_seen", []))).lower()
    return "verifier" in safe_keys and any(token in safe_keys for token in ["pass", "fail", "status", "result", "log"])


def classify(path: Path, source_family: str, source_summary: dict[str, Any]) -> tuple[str, str, list[str], str]:
    label = rel_label(path)
    blockers = list(BASE_BLOCKERS)
    dominance_risk = "low"

    if LEAK_NAME_RE.search(label):
        blockers.append("blocked_quarantine_name_indicates_leak_alias_singleton_schema_collapse_or_overclaim")
        return "quarantine", "quarantined_metadata_only", sorted(set(blockers)), "high"
    if RAWISH_NAME_RE.search(label) and ("raw_private" in label.lower() or "raw_visible" in label.lower()):
        blockers.append("blocked_quarantine_raw_private_or_raw_visible_source")
        return "quarantine", "quarantined_raw_only_or_raw_private_metadata", sorted(set(blockers)), "high"

    observed = int(source_summary.get("observed_count_estimate") or 0)
    if observed <= 1:
        blockers.append("blocked_singleton_or_missing_lineage_count")
        return "quarantine", "singleton_or_missing_lineage_metadata_only", sorted(set(blockers)), "medium"

    if source_family in {"open_swe", "selected_test", "codex_session_windows"}:
        dominance_risk = "medium"
    if source_family == "open_swe":
        dominance_risk = "high"

    if REPLAY_REQUEST_RE.search(label):
        blockers.append("blocked_replay_request_pending_no_replay_executed")
        return "replay_request_pending", "bounded_replay_or_hydration_request_not_executed", sorted(set(blockers)), dominance_risk

    if has_authoritative_replay_metadata(path, source_summary):
        blockers.extend(
            [
                "blocked_replay_calibrated_metadata_is_not_level3",
                "blocked_missing_full_state_before_action_observation_state_after_proof",
            ]
        )
        return "replay_calibrated_supervision", "authoritative_verifier_or_replay_status_metadata_only", sorted(set(blockers)), dominance_risk

    if SEALED_EVAL_RE.search(label) and ("heldout" in label.lower() or "strict_eval" in label.lower()):
        blockers.append("blocked_sealed_eval_only_never_train")
        return "sealed_eval_only", "sealed_or_heldout_eval_manifest_metadata_only", sorted(set(blockers)), "medium"

    blockers.append("blocked_weak_digest_safe_hashes_classes_counts_refs_only")
    return "weak_digest_supervision", "safe_hash_class_count_window_ref_only", sorted(set(blockers)), dominance_risk


def proof_slots_all_blocked(evidence_class: str) -> dict[str, dict[str, str]]:
    return {
        slot: {
            "proof_status": "blocked",
            "status_code": status_code,
            "evidence_class": evidence_class,
            "proof_ref_hash": "missing",
        }
        for slot, status_code in PROOF_SLOT_STATUS.items()
    }


def build_candidate(path: Path, rank: int) -> dict[str, Any]:
    label = rel_label(path)
    family = source_family_for(label)
    source_summary = summarize_source(path)
    tier, strength, blockers, dominance_risk = classify(path, family, source_summary)
    ref_basis = {
        "rank": rank,
        "stage": stage_name(path),
        "family": family,
        "source_label_hash": stable_hash(label, 24),
        "content_digest_hash": source_summary["content_digest_hash"],
    }
    row = {
        "stage": STAGE,
        "record_type": "source_adapter_candidate",
        "source_adapter_id": f"{STAGE}::{stable_hash(ref_basis, 20)}",
        "adapter_id": f"{STAGE}::{stable_hash({'adapter': family}, 16)}",
        "source_family": family,
        "source_stage": stage_name(path),
        "source_record_type": "source_adapter_artifact_or_summary",
        "source_record_ref_hash": stable_hash(ref_basis, 24),
        "source_artifact_hash": file_hash(path) if path.is_file() else stable_hash([file_hash(child) for child in find_json_files(path) + find_jsonl_files(path)], 24),
        "source_path_hash": stable_hash(label, 24),
        "source_ref_hash": stable_hash(ref_basis, 24),
        "canonical_root_id_hash": stable_hash({'source': label, 'root': 'unknown'}, 24),
        "repo_family_hash": stable_hash({'source': label, 'repo_family': 'unknown'}, 24),
        "repo_family_bucket": "unknown_or_adapter_level",
        "language_family": "mixed_or_unknown",
        "source_pool_id": family,
        "split_group_id": "not_admitted_no_split_assignment",
        "source_root_label": "adapter_inventory_only_no_root_label",
        "root_lineage_key_hash": stable_hash({'source': label, 'lineage': 'unverified'}, 24),
        "adapter_record_rank": rank,
        "observed_count_estimate": source_summary["observed_count_estimate"],
        "language_counts": source_summary["language_counts"],
        "candidate_proof_tier_now": tier,
        "proof_tier_candidate": tier,
        "current_tier": tier,
        "supervision_strength_now": strength,
        "supervision_strength_candidate": strength,
        "candidate_status": "blocked_source_adapter_inventory_only",
        "admission_level_candidate": "none_fail_closed",
        "proof_slots": proof_slots_all_blocked(strength),
        "all_proof_slots_blocked": True,
        "allowed_use": [
            "source_adapter_candidate_inventory",
            "safe_hash_class_count_schema_planning",
            "future_qc_worklist_planning_only",
        ],
        "forbidden_use": [
            "training_row",
            "eval_row",
            "level3_claim",
            "patch_trace_admission",
            "repair_claim",
            "raw_content_hydration",
            "replay_execution",
            "source_heldout_admission",
        ],
        "blocker_codes": blockers,
        "blockers": blockers,
        "dominance_risk": dominance_risk,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
        **ZERO_ADMISSION_FLAGS,
        "safe_metadata_digest": {
            "json_artifact_count": source_summary["json_artifact_count"],
            "jsonl_file_count": source_summary["jsonl_file_count"],
            "jsonl_record_count_estimate": source_summary["jsonl_record_count_estimate"],
            "safe_count_key_hash": stable_hash(source_summary["safe_count_keys_seen"], 24),
            "content_digest_hash": source_summary["content_digest_hash"],
        },
    }
    return row


def validate_row(row: dict[str, Any], index: int) -> list[str]:
    issues: list[str] = []
    required = [
        "source_adapter_id",
        "source_family",
        "source_path_hash",
        "source_ref_hash",
        "observed_count_estimate",
        "language_counts",
        "candidate_proof_tier_now",
        "proof_tier_candidate",
        "current_tier",
        "supervision_strength_now",
        "supervision_strength_candidate",
        "candidate_status",
        "admission_level_candidate",
        "proof_slots",
        "all_proof_slots_blocked",
        "allowed_use",
        "forbidden_use",
        "blocker_codes",
        "dominance_risk",
        "raw_content_policy",
        "claim_boundary",
        "zero_admission_flags",
    ]
    for key in required:
        if key not in row:
            issues.append(f"row_{index}_missing_{key}")
    if row.get("record_type") != "source_adapter_candidate":
        issues.append(f"row_{index}_not_source_adapter_candidate")
    if row.get("candidate_proof_tier_now") not in TIERS:
        issues.append(f"row_{index}_unknown_candidate_tier")
    if row.get("candidate_proof_tier_now") != row.get("proof_tier_candidate") or row.get("current_tier") != row.get("candidate_proof_tier_now"):
        issues.append(f"row_{index}_tier_alias_mismatch")
    if row.get("supervision_strength_now") != row.get("supervision_strength_candidate"):
        issues.append(f"row_{index}_supervision_strength_alias_mismatch")
    if row.get("candidate_proof_tier_now") == "level3_reconstructed_proof":
        issues.append(f"row_{index}_level3_candidate_disallowed_without_full_proof")
    slots = row.get("proof_slots") if isinstance(row.get("proof_slots"), dict) else {}
    for slot, status_code in PROOF_SLOT_STATUS.items():
        slot_status = slots.get(slot) if isinstance(slots.get(slot), dict) else {}
        if slot_status.get("proof_status") != "blocked":
            issues.append(f"row_{index}_proof_slot_{slot}_not_blocked")
        if slot_status.get("status_code") != status_code:
            issues.append(f"row_{index}_proof_slot_{slot}_status_code_mismatch")
        if slot_status.get("proof_ref_hash") != "missing":
            issues.append(f"row_{index}_proof_slot_{slot}_proof_ref_not_missing")
    if row.get("all_proof_slots_blocked") is not True:
        issues.append(f"row_{index}_all_proof_slots_blocked_not_true")
    for key in ["source_path_hash", "source_ref_hash"]:
        if not isinstance(row.get(key), str) or not HEX_RE.match(str(row.get(key))):
            issues.append(f"row_{index}_{key}_not_hash")
    if int(row.get("observed_count_estimate") or 0) < 0:
        issues.append(f"row_{index}_negative_observed_count")
    raw_policy = row.get("raw_content_policy") if isinstance(row.get("raw_content_policy"), dict) else {}
    for key, expected in RAW_CONTENT_POLICY.items():
        if raw_policy.get(key) is not expected:
            issues.append(f"row_{index}_raw_content_policy_{key}_mismatch")
    claim_boundary = row.get("claim_boundary") if isinstance(row.get("claim_boundary"), dict) else {}
    for key, expected in CLAIM_BOUNDARY.items():
        if claim_boundary.get(key) != expected:
            issues.append(f"row_{index}_claim_boundary_{key}_mismatch")
    zero_flags = row.get("zero_admission_flags") if isinstance(row.get("zero_admission_flags"), dict) else {}
    for key, expected in ZERO_ADMISSION_FLAGS.items():
        if zero_flags.get(key) != expected:
            issues.append(f"row_{index}_zero_admission_flags_{key}_mismatch")
        if row.get(key) != expected:
            issues.append(f"row_{index}_{key}_not_false_or_zero")
    forbidden = set(row.get("forbidden_use") or [])
    for needed in ["training_row", "eval_row", "level3_claim", "replay_execution"]:
        if needed not in forbidden:
            issues.append(f"row_{index}_forbidden_use_missing_{needed}")
    if not row.get("blocker_codes"):
        issues.append(f"row_{index}_missing_blockers")
    return issues


def scan_value(value: Any, artifact: str, issues: list[dict[str, Any]], key_path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{key_path}.{key}" if key_path else str(key)
            scan_value(child, artifact, issues, child_path)
        return
    if isinstance(value, list):
        for list_index, child in enumerate(value):
            scan_value(child, artifact, issues, f"{key_path}[{list_index}]")
        return
    if not isinstance(value, str):
        return
    if ABS_PATH_RE.search(value):
        issues.append({"artifact": artifact, "issue": "absolute_path_string", "key_hash": stable_hash(key_path, 16)})
    if URL_RE.search(value):
        issues.append({"artifact": artifact, "issue": "url_string", "key_hash": stable_hash(key_path, 16)})
    if MULTILINE_RE.search(value):
        issues.append({"artifact": artifact, "issue": "multiline_string", "key_hash": stable_hash(key_path, 16)})
    if key_path.endswith("_hash") and not HEX_RE.match(value) and value != "missing":
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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    inputs = discover_inputs()
    rows = [build_candidate(path, rank) for rank, path in enumerate(inputs, 1)]
    schema_issues = [issue for index, row in enumerate(rows, 1) for issue in validate_row(row, index)]

    counts_by_family = Counter(str(row["source_family"]) for row in rows)
    counts_by_tier = Counter(str(row["candidate_proof_tier_now"]) for row in rows)
    counts_by_strength = Counter(str(row["supervision_strength_now"]) for row in rows)
    counts_by_stage = Counter(str(row["source_stage"]) for row in rows)
    adapter_counts = Counter(str(row["adapter_id"]) for row in rows)
    language_family_counts = Counter(str(row["language_family"]) for row in rows)
    source_pool_counts = Counter(str(row["source_pool_id"]) for row in rows)
    split_group_counts = Counter(str(row["split_group_id"]) for row in rows)
    admission_level_counts = Counter(str(row["admission_level_candidate"]) for row in rows)
    allowed_use_counts = Counter(use for row in rows for use in row.get("allowed_use", []))
    blocked_use_counts = Counter(use for row in rows for use in row.get("forbidden_use", []))
    proof_slot_blocked_counts = Counter(slot for row in rows for slot, status in row.get("proof_slots", {}).items() if status.get("proof_status") == "blocked")
    proof_slot_unblocked_counts = Counter(slot for row in rows for slot, status in row.get("proof_slots", {}).items() if status.get("proof_status") != "blocked")
    for tier in TIERS:
        counts_by_tier.setdefault(tier, 0)

    blocker_counts = Counter(blocker for row in rows for blocker in row["blocker_codes"])
    estimated_candidate_records_total = sum(int(row.get("observed_count_estimate") or 0) for row in rows)
    candidate_count = max(1, len(rows))
    repo_family_top_count = max((count for count in counts_by_family.values()), default=0)
    adapter_top_count = max((count for count in adapter_counts.values()), default=0)
    dominance = {
        "repo_family_counts": dict(sorted(counts_by_family.items())),
        "repo_family_top_count": repo_family_top_count,
        "repo_family_top_fraction": repo_family_top_count / candidate_count,
        "adapter_counts": dict(sorted(adapter_counts.items())),
        "adapter_top_count": adapter_top_count,
        "adapter_top_fraction": adapter_top_count / candidate_count,
        "source_pool_counts": dict(sorted(source_pool_counts.items())),
        "language_family_counts": dict(sorted(language_family_counts.items())),
        "task_family_counts": {},
        "semantic_rule_counts": {},
        "split_group_counts": dict(sorted(split_group_counts.items())),
        "dominance_blocked_count": 0,
    }
    cap_policy = {
        "max_rows_per_repo_family": min(10, int(0.20 * candidate_count)),
        "max_rows_per_adapter": int(0.35 * candidate_count),
        "max_rows_per_source_pool": int(0.40 * candidate_count),
        "max_rows_per_language_family": int(0.40 * candidate_count),
        "max_rows_per_task_family": int(0.35 * candidate_count),
        "max_rows_per_template_or_semantic_rule": int(0.25 * candidate_count),
        "max_synthetic_or_fixture_external_repair_rows": 0,
        "max_raw_leak_findings": 0,
        "max_sealed_eval_overlap_rows": 0,
    }
    level3_candidate_count = sum(1 for row in rows if row.get("candidate_proof_tier_now") == "level3_reconstructed_proof")

    candidates_path = OUT / CANDIDATES_NAME
    local_summary_path = OUT / LOCAL_SUMMARY_NAME
    family_counts_path = OUT / FAMILY_COUNTS_NAME
    guardrail_path = OUT / GUARDRAIL_NAME

    write_jsonl(candidates_path, rows)
    write_json(family_counts_path, dict(sorted(counts_by_family.items())))

    pre_guardrail_summary = {
        "stage": STAGE,
        "decision": "pending_guardrail_scan",
        "total_source_candidates": len(rows),
        "total_records": len(rows),
        "counts_by_source_family": dict(sorted(counts_by_family.items())),
        "candidate_counts_by_source_stage": dict(sorted(counts_by_stage.items())),
        "input_counts_by_adapter": dict(sorted(adapter_counts.items())),
        "output_counts_by_adapter": dict(sorted(adapter_counts.items())),
        "counts_by_candidate_proof_tier_now": dict(sorted(counts_by_tier.items())),
        "counts_by_tier": dict(sorted(counts_by_tier.items())),
        "proof_tier_counts": dict(sorted(counts_by_tier.items())),
        "counts_by_supervision_strength_now": dict(sorted(counts_by_strength.items())),
        "supervision_strength_counts": dict(sorted(counts_by_strength.items())),
        "admission_level_candidate_counts": dict(sorted(admission_level_counts.items())),
        "allowed_use_counts": dict(sorted(allowed_use_counts.items())),
        "blocked_use_counts": dict(sorted(blocked_use_counts.items())),
        "proof_slot_blocked_counts": dict(sorted(proof_slot_blocked_counts.items())),
        "proof_slot_unblocked_counts": dict(sorted(proof_slot_unblocked_counts.items())),
        "estimated_candidate_records_total": estimated_candidate_records_total,
        "level3_candidate_count": level3_candidate_count,
        "training_allowed": False,
        "training_row_count": 0,
        "admission": False,
        "admitted_rows": 0,
        "level3_admitted": 0,
        "level4_admitted": 0,
        "patch_trace_admitted": 0,
        "repair_claim_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "external_comparable_patch_trace_countable": 0,
        "external_fail_to_pass_countable": 0,
        "synthetic_fixture_external_repair_countable": 0,
        "selected_test_full_repair_claim_count": 0,
        "sealed_eval_train_overlap_count": 0,
        "raw_leak_count": 0,
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "guardrail_issue_count": 0,
        "raw_leak_findings": [],
        "claim_boundary": CLAIM_BOUNDARY,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
        "input_source_count": len(inputs),
        "input_source_ref_hashes": [row["source_ref_hash"] for row in rows],
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "repo_family_counts": dict(sorted(counts_by_family.items())),
        "language_family_counts": dict(sorted(language_family_counts.items())),
        "source_pool_counts": dict(sorted(source_pool_counts.items())),
        "task_family_counts": {},
        "semantic_rule_counts": {},
        "split_group_counts": dict(sorted(split_group_counts.items())),
        "dominance": dominance,
        "cap_policy": cap_policy,
        "cap_violation_counts": {},
        "sealed_eval_overlap_counts": {"train_overlap": 0},
        "synthetic_fixture_counts": {"external_repair_countable": 0},
        "selected_test_scope_counts": {"full_repair_claim_count": 0},
        "source_stage_artifact_hashes": {},
        "source_artifact_hashes_by_adapter": {},
        "generated_artifacts": [CANDIDATES_NAME, LOCAL_SUMMARY_NAME, FAMILY_COUNTS_NAME, GUARDRAIL_NAME],
    }
    write_json(local_summary_path, pre_guardrail_summary)

    guardrail = guardrail_scan([candidates_path, family_counts_path, local_summary_path])
    write_json(guardrail_path, guardrail)

    decision = "fail_closed_source_expansion_preflight_ready_no_admission"
    if schema_issues or guardrail["issues"] or level3_candidate_count:
        decision = "fail_closed_source_expansion_preflight_blocked_schema_or_guardrail_issue"

    summary = {
        **pre_guardrail_summary,
        "decision": decision,
        "guardrail_scan": guardrail,
        "guardrail_issue_count": len(guardrail["issues"]),
        "raw_leak_findings": guardrail["issues"],
        "level3_candidate_count": level3_candidate_count,
        "training_allowed": False,
        "training_row_count": 0,
        "admission": False,
        "admitted_rows": 0,
        "level3_admitted": 0,
        "level4_admitted": 0,
        "patch_trace_admitted": 0,
        "repair_claim_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "external_comparable_patch_trace_countable": 0,
        "external_fail_to_pass_countable": 0,
        "synthetic_fixture_external_repair_countable": 0,
        "selected_test_full_repair_claim_count": 0,
        "sealed_eval_train_overlap_count": 0,
        "raw_leak_count": len(guardrail["issues"]),
        "zero_admission": not schema_issues and not guardrail["issues"] and level3_candidate_count == 0,
    }
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
