#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12532_public_source_lane_expansion_and_train_support_admission_gate"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12417_LEDGER = ROOT / "runs/local/artifacts/stage12417_combined_train_support_ledger_v16/combined_train_support_ledger_v16.json"
STAGE12417_ROWS = ROOT / "runs/local/artifacts/stage12417_combined_train_support_ledger_v16/combined_train_support_rows_v16.jsonl"
STAGE12421_SUMMARY = ROOT / "runs/summaries/stage12421_new_direct_real_verifier_observation_miner.json"
STAGE12421_ROWS = ROOT / "runs/local/artifacts/stage12421_new_direct_real_verifier_observation_miner/new_direct_verifier_observation_train_support_rows.jsonl"
STAGE12457_SUMMARY = ROOT / "runs/local/artifacts/stage12457_selected_test_transition_support_package_control/package_manifest.json"
STAGE12457_ROWS = ROOT / "runs/local/artifacts/stage12457_selected_test_transition_support_package_control/support_package_row_index.jsonl"
STAGE12459_SUMMARY = ROOT / "runs/summaries/stage12459_external_comparable_patch_effect_source_preflight.json"
STAGE12459_WORKLIST = ROOT / "runs/local/artifacts/stage12459_external_comparable_patch_effect_source_preflight/public_lane_ref_worklist.jsonl"

TARGET_TRAIN_SUPPORT_FLOOR = 500
STAGE12417_NON_SELECTED_BASE_ROWS = 91

RISKY_FIELDS = (
    "strict_eval_eligible",
    "source_heldout_admissible",
    "level3_admitted",
    "level4_admitted",
    "patch_trace_admitted",
    "repair_claim_admitted",
    "fail_to_pass_claim_admitted",
    "counts_toward_unbounded_patch_trace_floor",
    "counts_toward_strict_eval_floor",
    "counts_toward_source_heldout_floor",
)

RAW_KEY_RE = re.compile(
    r"^(input_text|prompt_text|decoder_text|command|cmd|argv|cwd|stdout|stderr|"
    r"stdout_tail|stderr_tail|output|path|url|diff|source_text|content|raw_.*)$",
    re.IGNORECASE,
)
RAW_VALUE_RE = re.compile(
    r"https?://|www\.|(^|\n)(diff --git|@@ |\+{3} |--- )|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){1,}[A-Za-z0-9._-]+|"
    r"\b(python|pytest|cargo|npm|yarn|pnpm|bash|sh|git)\b.+\s(-m|-q|test|run|checkout|diff)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE,
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
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
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return False


def risky_claims(row: dict[str, Any]) -> list[str]:
    admission = row.get("admission") if isinstance(row.get("admission"), dict) else {}
    claims = []
    for field in RISKY_FIELDS:
        if truthy(row.get(field)) or truthy(admission.get(field)):
            claims.append(field)
    return claims


def target_value(row: dict[str, Any]) -> str:
    if row.get("target_semantic_value"):
        return str(row["target_semantic_value"])
    if row.get("target_semantic_id"):
        return str(row["target_semantic_id"])
    target_label = row.get("bounded_choice_target_label") or row.get("target_label")
    for option in row.get("opaque_options") or []:
        if isinstance(option, dict) and option.get("label") == target_label:
            return str(option.get("semantic_id") or option.get("value") or "")
    return ""


def projection(row: dict[str, Any]) -> str:
    return str(row.get("task_projection") or row.get("task_family") or row.get("record_type") or "unknown")


def row_hash_ref(row: dict[str, Any]) -> str:
    keys = {
        "row_id": row.get("row_id"),
        "source_stage": row.get("source_stage") or row.get("stage"),
        "root": row.get("root_lineage_key_hash") or row.get("root_id_hash") or row.get("root_id"),
        "projection": projection(row),
        "target": target_value(row),
    }
    return stable_hash(keys)


def sanitized_train_row(row: dict[str, Any], source_bucket: str, countable: bool) -> dict[str, Any]:
    risks = risky_claims(row)
    root_hash = row.get("root_lineage_key_hash") or row.get("root_id_hash") or stable_hash(row.get("root_id") or row_hash_ref(row))
    source_stage = str(row.get("source_stage") or row.get("stage") or "unknown")
    controlled = truthy(row.get("controlled_fixture_like"))
    return {
        "stage": STAGE,
        "bucket": "train_support_only",
        "source_bucket": source_bucket,
        "row_ref_hash": row_hash_ref(row),
        "source_row_id_hash": stable_hash(row.get("row_id") or row_hash_ref(row)),
        "source_stage": source_stage,
        "root_lineage_key_hash": str(root_hash),
        "repo_family_hash": row.get("repo_family_hash") or stable_hash(row.get("repo_family") or source_stage),
        "language_family": row.get("language_family") or "unknown",
        "task_projection": projection(row),
        "target_semantic_value": target_value(row),
        "verifier_status": row.get("verifier_status"),
        "verifier_output_class": row.get("verifier_output_class"),
        "source_lineage_checked": bool(row.get("stable_real_log_record_id") or row.get("source_key_audit_hash") or row.get("source_refs")),
        "anti_collapse_checked": True,
        "countable_train_support": bool(countable and not controlled and not risks),
        "train_support_only": True,
        "fixture_curriculum_only": False,
        "proof_candidate_only": False,
        "controlled_fixture_like": controlled,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
        "training_allowed": False,
        "blocked_reasons": risks,
    }


def sanitized_fixture_row(row: dict[str, Any], source_bucket: str) -> dict[str, Any]:
    status = row.get("verifier_status") or row.get("observation_status_class")
    root_hash = row.get("root_lineage_key_hash") or row.get("root_id_hash") or stable_hash(row.get("root_id") or row.get("return_row_hash") or row_hash_ref(row))
    source_stage = str(row.get("source_stage") or row.get("stage") or "unknown")
    return {
        "stage": STAGE,
        "bucket": "fixture_curriculum_only",
        "source_bucket": source_bucket,
        "row_ref_hash": row.get("row_ref_hash") or row.get("package_row_ref_hash") or row_hash_ref(row),
        "source_record_ref_hash": row.get("source_record_ref_hash") or row.get("stable_real_log_record_id") or stable_hash(row.get("row_id") or row_hash_ref(row)),
        "source_stage": source_stage,
        "root_lineage_key_hash": str(root_hash),
        "language_family": row.get("language_family") or "unknown",
        "task_projection": projection(row),
        "target_or_status_class": target_value(row) or status,
        "support_use_class": row.get("support_use_class") or "fixture_or_selected_verifier_curriculum_support",
        "source_match_class": row.get("source_match_class") or "source_lineage_checked_from_upstream",
        "proof_depth_class": row.get("proof_depth_class") or "not_proof_credit",
        "external_repair_credit_class": row.get("external_repair_credit_class") or "not_applicable",
        "train_support_only": False,
        "fixture_curriculum_only": True,
        "proof_candidate_only": False,
        "countable_train_support": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
        "external_repair_credit_allowed": False,
        "training_allowed": False,
    }


def sanitized_proof_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "bucket": "proof_candidate_only",
        "lane_ref_hash": stable_hash(row.get("lane_id") or row),
        "rank": row.get("rank"),
        "candidate_count_bucket": row.get("candidate_count_bucket"),
        "required_proof_slots_ref": row.get("required_proof_slots_ref") or "stage12459_required_repair_proof_slots_v1",
        "source_stage_refs": row.get("source_stage_refs") or [],
        "train_support_only": False,
        "fixture_curriculum_only": False,
        "proof_candidate_only": True,
        "countable_train_support": False,
        "external_repair_credit_count": 0,
        "level3_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
        "training_allowed": False,
    }


def duplicate_audit(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seen: dict[tuple[str, str, str, str], str] = {}
    kept: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for row in rows:
        key = (
            str(row.get("root_lineage_key_hash") or ""),
            str(row.get("task_projection") or ""),
            str(row.get("target_semantic_value") or row.get("target_or_status_class") or ""),
            str(row.get("source_stage") or ""),
        )
        if key in seen:
            dup = dict(row)
            dup["duplicate_of_row_ref_hash"] = seen[key]
            duplicates.append(dup)
            continue
        seen[key] = str(row.get("row_ref_hash") or row.get("source_row_id_hash") or "")
        kept.append(row)
    return kept, duplicates


def collapse_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_root[str(row.get("root_lineage_key_hash") or "unknown")].append(row)
    collapsed_groups = []
    for root, group in by_root.items():
        projections = {str(row.get("task_projection") or "") for row in group}
        targets = {str(row.get("target_semantic_value") or row.get("target_or_status_class") or "") for row in group}
        generic_targets = {target for target in targets if target in {"candidate_0", "candidate_selected_test_backed"}}
        if len(group) >= 3 and len(targets) == 1:
            collapsed_groups.append({"root_hash": root, "reason": "single_target_across_3_plus_rows", "row_count": len(group)})
        elif generic_targets and projections - {"transition_candidate_selection"}:
            collapsed_groups.append({"root_hash": root, "reason": "generic_candidate_target_used_outside_candidate_selection", "row_count": len(group)})
    target_counts = Counter(str(row.get("target_semantic_value") or row.get("target_or_status_class") or "unknown") for row in rows)
    max_target_share = (max(target_counts.values()) / len(rows)) if rows else 0.0
    return {
        "collapse_group_count": len(collapsed_groups),
        "collapsed_groups": collapsed_groups[:20],
        "max_target_share": round(max_target_share, 6),
        "target_counts": dict(sorted(target_counts.items())),
        "target_dominance_passed": max_target_share <= 0.35 if rows else True,
    }


def iter_strings(value: Any, key: str = ""):
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from iter_strings(child, str(child_key))
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child, key)
    elif isinstance(value, str):
        yield key, value


def guardrail_scan(*objects: Any) -> dict[str, Any]:
    issues = []
    for obj in objects:
        for key, text in iter_strings(obj):
            if RAW_KEY_RE.search(key):
                issues.append({"kind": "raw_key", "key": key})
            elif RAW_VALUE_RE.search(text):
                issues.append({"kind": "raw_value", "key": key, "value_hash": stable_hash(text)})
    return {
        "scan_passed": not issues,
        "raw_leak_count": len(issues),
        "issues": issues[:50],
        "scan_scope": "stage12532_sanitized_public_source_lane_indexes",
    }


def count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field) or "unknown") for row in rows).items()))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    stage12417_ledger = read_json(STAGE12417_LEDGER)
    stage12421_summary = read_json(STAGE12421_SUMMARY)
    stage12457_summary = read_json(STAGE12457_SUMMARY)
    stage12459_summary = read_json(STAGE12459_SUMMARY)

    existing_rows = [
        sanitized_train_row(row, "stage12417_existing_countable_inventory", countable=True)
        for row in read_jsonl(STAGE12417_ROWS)
    ]
    stage12421_rows = read_jsonl(STAGE12421_ROWS)
    new_train_rows = [
        sanitized_train_row(row, "stage12421_new_direct_public_local_verifier_observation", countable=True)
        for row in stage12421_rows
        if not truthy(row.get("controlled_fixture_like")) and not risky_claims(row)
    ]
    stage12421_fixture_rows = [
        sanitized_fixture_row(row, "stage12421_controlled_fixture_projection")
        for row in stage12421_rows
        if truthy(row.get("controlled_fixture_like")) or risky_claims(row)
    ]
    stage12457_fixture_rows = [
        sanitized_fixture_row(row, "stage12457_selected_test_transition_support_control")
        for row in read_jsonl(STAGE12457_ROWS)
    ]
    proof_candidate_rows = [sanitized_proof_candidate(row) for row in read_jsonl(STAGE12459_WORKLIST)]

    train_rows_before_dedupe = existing_rows + new_train_rows
    train_rows, duplicate_train_rows = duplicate_audit(train_rows_before_dedupe)
    fixture_rows = stage12421_fixture_rows + stage12457_fixture_rows

    train_collapse = collapse_audit(train_rows)
    fixture_collapse = collapse_audit(fixture_rows)
    proof_duplicate_lane_count = len(proof_candidate_rows) - len({row["lane_ref_hash"] for row in proof_candidate_rows})
    scan = guardrail_scan(train_rows, fixture_rows, proof_candidate_rows)

    countable_existing_total = int(stage12417_ledger.get("current_admitted_train_support_tasks") or (STAGE12417_NON_SELECTED_BASE_ROWS + len(existing_rows)))
    countable_new_delta = sum(1 for row in new_train_rows if row["countable_train_support"])
    countable_total = countable_existing_total + countable_new_delta - len(duplicate_train_rows)
    remaining_gap = max(0, TARGET_TRAIN_SUPPORT_FLOOR - countable_total)

    checks = {
        "no_raw_leak": scan["scan_passed"],
        "no_duplicate_train_rows": len(duplicate_train_rows) == 0,
        "no_train_collapse_groups": train_collapse["collapse_group_count"] == 0,
        "train_target_dominance_passed": train_collapse["target_dominance_passed"],
        "proof_candidate_lane_dedupe_passed": proof_duplicate_lane_count == 0,
        "fixture_rows_excluded_from_500": all(not row["countable_train_support"] for row in fixture_rows),
        "proof_candidates_excluded_from_500": all(not row["countable_train_support"] for row in proof_candidate_rows),
        "zero_level3_patch_trace_repair_credit": all(
            not truthy(row.get(field))
            for row in (train_rows + fixture_rows + proof_candidate_rows)
            for field in ("level3_admitted", "patch_trace_admitted", "repair_claim_admitted", "fail_to_pass_claim_admitted")
        ),
    }
    separate_training_gate_passed = (
        countable_total >= TARGET_TRAIN_SUPPORT_FLOOR
        and all(checks.values())
        and stage12417_ledger.get("training_allowed") is True
    )

    train_support_path = OUT / "train_support_only_public_source_lane_rows.jsonl"
    fixture_path = OUT / "fixture_curriculum_only_rows.jsonl"
    proof_path = OUT / "proof_candidate_only_lanes.jsonl"
    dup_path = OUT / "duplicate_train_support_rows.jsonl"
    guardrail_path = OUT / "guardrail_scan.json"
    collapse_path = OUT / "anti_collapse_audit.json"

    write_jsonl(train_support_path, train_rows)
    write_jsonl(fixture_path, fixture_rows)
    write_jsonl(proof_path, proof_candidate_rows)
    write_jsonl(dup_path, duplicate_train_rows)
    write_json(guardrail_path, scan)
    write_json(collapse_path, {"train_support_only": train_collapse, "fixture_curriculum_only": fixture_collapse})

    training_blockers = []
    if countable_total < TARGET_TRAIN_SUPPORT_FLOOR:
        training_blockers.append("500_countable_train_support_floor_not_reached")
    if not checks["no_train_collapse_groups"]:
        training_blockers.append("legacy_train_support_collapse_groups_present")
    if not all(checks.values()):
        training_blockers.append("separate_training_gate_not_passed")

    summary = {
        "stage": STAGE,
        "record_type": "public_source_lane_expansion_and_train_support_admission_gate_v1",
        "decision": "public_source_lane_expanded_training_blocked_500_floor_and_collapse_gate_not_passed",
        "claim_boundary": (
            "Metadata-only public/local source-lane consolidation. Adds only Stage12421 non-fixture direct verifier-observation "
            "rows to train-support accounting; keeps selected-test/verifier observations and controlled fixtures out of "
            "Level3, patch-trace, repair-proof, source-heldout, strict-eval, and external repair credit accounting."
        ),
        "required_buckets": {
            "train_support_only": len(train_rows),
            "fixture_curriculum_only": len(fixture_rows),
            "proof_candidate_only": len(proof_candidate_rows),
        },
        "countable_train_support": {
            "previous_countable_total_from_stage12417": countable_existing_total,
            "new_countable_public_local_rows_from_stage12421": countable_new_delta,
            "duplicate_train_rows_removed": len(duplicate_train_rows),
            "current_countable_total": countable_total,
            "target_floor": TARGET_TRAIN_SUPPORT_FLOOR,
            "remaining_gap_to_500": remaining_gap,
        },
        "baseline_countable_train_support_count": countable_existing_total,
        "new_countable_train_support_count": countable_new_delta,
        "countable_train_support_count": countable_total,
        "remaining_gap_to_500": remaining_gap,
        "bucket_counts": {
            "train_support_only": len(train_rows),
            "fixture_curriculum_only": len(fixture_rows),
            "proof_candidate_only": len(proof_candidate_rows),
        },
        "source_inventory": {
            "stage12417_row_index_rows": len(existing_rows),
            "stage12421_emitted_rows": len(stage12421_rows),
            "stage12421_countable_summary": stage12421_summary.get("countable_as_new_train_support_rows"),
            "stage12457_fixture_control_rows": len(stage12457_fixture_rows),
            "stage12459_proof_candidate_lanes": len(proof_candidate_rows),
        },
        "bucket_language_counts": {
            "train_support_only": count_by(train_rows, "language_family"),
            "fixture_curriculum_only": count_by(fixture_rows, "language_family"),
        },
        "bucket_projection_counts": {
            "train_support_only": count_by(train_rows, "task_projection"),
            "fixture_curriculum_only": count_by(fixture_rows, "task_projection"),
        },
        "checks": checks,
        "anti_collapse": {
            "train_support_only": {
                "collapse_group_count": train_collapse["collapse_group_count"],
                "max_target_share": train_collapse["max_target_share"],
                "target_dominance_passed": train_collapse["target_dominance_passed"],
            },
            "fixture_curriculum_only": {
                "collapse_group_count": fixture_collapse["collapse_group_count"],
                "max_target_share": fixture_collapse["max_target_share"],
                "target_dominance_passed": fixture_collapse["target_dominance_passed"],
            },
        },
        "guardrail_scan_passed": scan["scan_passed"],
        "raw_leak_count": scan["raw_leak_count"],
        "duplicate_train_row_count": len(duplicate_train_rows),
        "collapse_group_count": train_collapse["collapse_group_count"],
        "proof_candidate_external_credit_count": 0,
        "level3_admitted": 0,
        "level3_admitted_rows": 0,
        "patch_trace_admitted": 0,
        "patch_trace_admitted_rows": 0,
        "patch_trace_rows": 0,
        "repair_claim_admitted_rows": 0,
        "external_repair_credit_count": 0,
        "fail_to_pass_claim_admitted_rows": 0,
        "strict_eval_eligible_count": 0,
        "strict_eval_rows": 0,
        "source_heldout_admissible_count": 0,
        "source_heldout_rows": 0,
        "training_allowed": bool(separate_training_gate_passed),
        "training_blockers": training_blockers,
        "next_stage": "expand_public_local_train_support_and_repair_legacy_collapse_groups_before_training",
        "artifact_refs": {
            "train_support_only": str(train_support_path.relative_to(ROOT)),
            "fixture_curriculum_only": str(fixture_path.relative_to(ROOT)),
            "proof_candidate_only": str(proof_path.relative_to(ROOT)),
            "duplicates": str(dup_path.relative_to(ROOT)),
            "guardrail_scan": str(guardrail_path.relative_to(ROOT)),
            "anti_collapse_audit": str(collapse_path.relative_to(ROOT)),
        },
        "input_hashes": {
            "stage12417_ledger": file_hash(STAGE12417_LEDGER),
            "stage12417_rows": file_hash(STAGE12417_ROWS),
            "stage12421_summary": file_hash(STAGE12421_SUMMARY),
            "stage12421_rows": file_hash(STAGE12421_ROWS),
            "stage12457_summary": file_hash(STAGE12457_SUMMARY),
            "stage12457_rows": file_hash(STAGE12457_ROWS),
            "stage12459_summary": file_hash(STAGE12459_SUMMARY),
            "stage12459_worklist": file_hash(STAGE12459_WORKLIST),
        },
        "upstream_guardrails": {
            "stage12421_guardrail_scan_passed": bool(stage12421_summary.get("guardrail_scan_passed")),
            "stage12457_guardrail_scan_passed": bool(stage12457_summary.get("guardrail_scan_passed")),
            "stage12459_guardrail_scan_passed": bool(stage12459_summary.get("guardrail_scan_passed")),
        },
    }

    write_json(OUT / "public_source_lane_expansion_and_train_support_admission_gate.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
