#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12534_fresh_hydratable_verifier_observation_admission_gate"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12533_SUMMARY = ROOT / "runs/summaries/stage12533_legacy_collapse_group_countable_repair.json"
STAGE12533_REPAIRED_ROWS = ROOT / "runs/local/artifacts/stage12533_legacy_collapse_group_countable_repair/train_support_only_repaired_countable_rows.jsonl"
STAGE12421_ROWS = ROOT / "runs/local/artifacts/stage12421_new_direct_real_verifier_observation_miner/new_direct_verifier_observation_train_support_rows.jsonl"
STAGE12421_SUMMARY = ROOT / "runs/summaries/stage12421_new_direct_real_verifier_observation_miner.json"
STAGE12216_ROWS = ROOT / "runs/local/artifacts/stage12216_normalized_verifier_observation_dataset/normalized_verifier_observation_records.jsonl"
STAGE12216_SUMMARY = ROOT / "runs/local/artifacts/stage12216_normalized_verifier_observation_dataset/summary.json"
STAGE12418_ROWS = ROOT / "runs/local/artifacts/stage12418_normalized_verifier_observation_sanitized_canonicalizer/sanitized_normalized_verifier_observation_projection_rows.jsonl"
STAGE12418_MANIFEST = ROOT / "runs/local/artifacts/stage12418_normalized_verifier_observation_sanitized_canonicalizer/sanitized_normalized_verifier_observation_manifest.json"
STAGE12457_ROWS = ROOT / "runs/local/artifacts/stage12457_selected_test_transition_support_package_control/support_package_row_index.jsonl"
STAGE12457_SUMMARY = ROOT / "runs/local/artifacts/stage12457_selected_test_transition_support_package_control/package_manifest.json"

TARGET_TRAIN_SUPPORT_FLOOR = 500
SCHEMA_NAME = "public_local_verifier_observation_supply_schema.json"
RULES_NAME = "public_local_verifier_observation_rejection_rules.json"
COMMANDS_NAME = "deterministic_supply_gate_commands.json"

RAW_KEY_RE = re.compile(
    r"^(input_text|prompt_text|decoder_text|command|cmd|argv|cwd|stdout|stderr|"
    r"stdout_tail|stderr_tail|stdout_excerpt|stderr_excerpt|output|path|url|diff|patch|"
    r"patch_body|patch_diff|source_text|content|raw_.*)$",
    re.IGNORECASE,
)
RAW_VALUE_RE = re.compile(
    r"https?://|www\.|(^|\n)(diff --git|@@ |\+{3} |--- )|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){1,}[A-Za-z0-9._-]+|"
    r"\b(python|pytest|cargo|npm|yarn|pnpm|bash|sh|git|ctest|cmake)\b.+"
    r"\s(-m|-q|test|run|build|--test-dir|checkout|diff)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE,
)
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
COMMAND_OUTPUT_PROVENANCE_FIELDS = (
    "verifier_command_ref_hash",
    "command_result_id_hash",
    "verifier_exit_status_class",
    "verifier_stdout_hash",
    "verifier_stderr_hash",
    "verifier_output_hash",
    "verifier_observation_hash",
    "target_binding_class",
    "target_binding_rule_id_hash",
    "actual_verifier_command_output_observation_provenance",
)
ALLOWED_EXIT_STATUS_CLASSES = {"exit_zero", "exit_nonzero"}
ALLOWED_TARGET_BINDING_CLASSES = {"target_semantic_value_from_observed_verifier_result_status"}


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
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                value["__line_no"] = line_no
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
        "scan_scope": "stage12534_sanitized_hash_class_and_gate_outputs",
    }


def target_value(row: dict[str, Any]) -> str:
    if row.get("target_semantic_value"):
        return str(row["target_semantic_value"])
    if row.get("target_or_status_class"):
        return str(row["target_or_status_class"])
    if row.get("verifier_transition"):
        return str(row["verifier_transition"])
    if row.get("verifier_status"):
        return str(row["verifier_status"])
    return "unknown"


def projection(row: dict[str, Any]) -> str:
    return str(row.get("task_projection") or row.get("task_family") or row.get("record_type") or "unknown")


def duplicate_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("root_lineage_key_hash") or row.get("root_id_hash") or ""),
        projection(row),
        target_value(row),
        str(row.get("source_stage") or row.get("rollup_source_stage") or row.get("stage") or ""),
    )


def existing_duplicate_keys(rows: list[dict[str, Any]]) -> set[tuple[str, str, str, str]]:
    return {duplicate_key(row) for row in rows}


def collapse_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_root[str(row.get("root_lineage_key_hash") or "unknown")].append(row)
    collapsed_groups = []
    for root, group in by_root.items():
        targets = {target_value(row) for row in group}
        projections = {projection(row) for row in group}
        if len(group) >= 3 and len(targets) == 1:
            collapsed_groups.append(
                {
                    "root_hash": root,
                    "reason": "single_target_across_3_plus_rows",
                    "row_count": len(group),
                    "task_projections": sorted(projections),
                    "target_values": sorted(targets),
                }
            )
    target_counts = Counter(target_value(row) for row in rows)
    max_target_share = (max(target_counts.values()) / len(rows)) if rows else 0.0
    return {
        "collapse_group_count": len(collapsed_groups),
        "collapsed_groups": collapsed_groups[:20],
        "max_target_share": round(max_target_share, 6),
        "target_counts": dict(sorted(target_counts.items())),
        "target_dominance_passed": max_target_share <= 0.35 if rows else True,
    }


def stage12418_candidate(row: dict[str, Any], duplicate_keys: set[tuple[str, str, str, str]]) -> dict[str, Any]:
    reasons = [
        "derived_stage12216_stage12418_projection_not_fresh_source_supply",
        "already_projected_by_stage12418_dedupe_lane",
    ]
    if duplicate_key(row) in duplicate_keys:
        reasons.append("duplicate_of_stage12533_repaired_train_support_key")
    reasons.extend(risky_claims(row))
    return {
        "stage": STAGE,
        "candidate_ref_hash": stable_hash(row.get("row_id") or row),
        "source_lane": "stage12216_stage12418_sanitized_projection",
        "source_stage": row.get("source_stage") or "unknown",
        "rollup_source_stage_hash": stable_hash(row.get("rollup_source_stage") or "unknown"),
        "source_line_hash": row.get("stage12216_source_line_hash") or stable_hash(row.get("__line_no")),
        "root_lineage_key_hash": row.get("root_lineage_key_hash") or row.get("root_id_hash") or stable_hash(row.get("root_id_hash")),
        "repo_family_hash": row.get("repo_family_hash") or stable_hash(row.get("source_stage") or "unknown"),
        "language_family": row.get("language_family") or "unknown",
        "task_projection": projection(row),
        "target_semantic_value": target_value(row),
        "verifier_status": row.get("verifier_transition") or row.get("verifier_status"),
        "source_lineage_checked": bool(row.get("source_key_audit_hash") and row.get("lineage_dedupe_key_hashes")),
        "hydratable_verifier_observation_candidate": True,
        "fresh_public_local_source_supply": False,
        "countable_train_support": False,
        "training_allowed": False,
        "blocked_reasons": sorted(set(reasons)),
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
    }


def stage12421_candidate(row: dict[str, Any], duplicate_keys: set[tuple[str, str, str, str]]) -> dict[str, Any]:
    reasons = []
    if duplicate_key(row) in duplicate_keys:
        reasons.append("already_in_stage12533_repaired_train_support")
    if truthy(row.get("controlled_fixture_like")):
        reasons.append("controlled_fixture_like_excluded_from_500_counter")
    reasons.extend(risky_claims(row))
    return {
        "stage": STAGE,
        "candidate_ref_hash": stable_hash(row.get("row_id") or row),
        "source_lane": "stage12421_direct_public_local_verifier_observation",
        "source_stage": row.get("source_stage") or "unknown",
        "source_line_hash": row.get("source_line_hash") or stable_hash(row.get("__line_no")),
        "root_lineage_key_hash": row.get("root_lineage_key_hash") or row.get("root_id_hash") or stable_hash(row.get("root_id_hash")),
        "repo_family_hash": row.get("repo_family_hash") or stable_hash(row.get("source_stage") or "unknown"),
        "language_family": row.get("language_family") or "unknown",
        "task_projection": projection(row),
        "target_semantic_value": target_value(row),
        "verifier_status": row.get("verifier_status"),
        "source_lineage_checked": bool(row.get("stable_real_log_record_id") and row.get("source_line_hash")),
        "hydratable_verifier_observation_candidate": True,
        "fresh_public_local_source_supply": not reasons,
        "countable_train_support": False,
        "training_allowed": False,
        "blocked_reasons": sorted(set(reasons or ["pending_stage12534_count_floor_batch_admission"])),
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
    }


def selected_test_gate_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "candidate_ref_hash": stable_hash(row.get("row_ref_hash") or row.get("package_row_ref_hash") or row),
        "source_lane": "stage12457_selected_test_transition_support_control",
        "source_stage": row.get("source_stage") or row.get("stage") or "unknown",
        "source_line_hash": stable_hash(row.get("__line_no")),
        "root_lineage_key_hash": row.get("root_lineage_key_hash") or row.get("root_id_hash") or stable_hash(row.get("root_id") or row),
        "language_family": row.get("language_family") or "unknown",
        "task_projection": projection(row),
        "target_semantic_value": target_value(row),
        "source_lineage_checked": bool(row.get("source_match_class") or row.get("source_record_ref_hash")),
        "hydratable_verifier_observation_candidate": False,
        "fresh_public_local_source_supply": False,
        "countable_train_support": False,
        "training_allowed": False,
        "blocked_reasons": ["selected_test_control_support_not_fresh_hydratable_verifier_observation_supply"],
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
    }


def count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field) or "unknown") for row in rows).items()))



def supply_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Stage12534 public/local verifier-observation supply row",
        "type": "object",
        "additionalProperties": True,
        "required": [
            "source_stage",
            "source_line_hash",
            "root_lineage_key_hash",
            "repo_family_hash",
            "language_family",
            "task_projection",
            "target_semantic_value",
            "verifier_status",
            "source_lineage_checked",
            "hydratable_verifier_observation_candidate",
            "controlled_fixture_like",
            "actual_verifier_command_output_observation_provenance",
            "verifier_command_ref_hash",
            "command_result_id_hash",
            "verifier_exit_status_class",
            "verifier_stdout_hash",
            "verifier_stderr_hash",
            "verifier_output_hash",
            "verifier_observation_hash",
            "target_binding_class",
            "target_binding_rule_id_hash",
        ],
        "properties": {
            "source_stage": {"type": "string", "minLength": 1},
            "source_line_hash": {"type": "string", "pattern": "^[0-9a-f]{16,64}$"},
            "root_lineage_key_hash": {"type": "string", "pattern": "^[0-9a-f]{16,64}$"},
            "repo_family_hash": {"type": "string", "pattern": "^[0-9a-f]{16,64}$"},
            "language_family": {"type": "string", "enum": ["python", "rust", "c_cpp", "web_js_ts_html", "unknown"]},
            "task_projection": {"type": "string", "enum": ["transition_verifier_transition", "transition_continue_or_stop"]},
            "target_semantic_value": {"type": "string", "minLength": 1},
            "verifier_status": {"type": "string", "minLength": 1},
            "source_lineage_checked": {"type": "boolean", "const": True},
            "hydratable_verifier_observation_candidate": {"type": "boolean", "const": True},
            "controlled_fixture_like": {"type": "boolean", "const": False},
            "actual_verifier_command_output_observation_provenance": {"type": "boolean", "const": True},
            "verifier_command_ref_hash": {"type": "string", "pattern": "^[0-9a-f]{16,64}$"},
            "command_result_id_hash": {"type": "string", "pattern": "^[0-9a-f]{16,64}$"},
            "verifier_exit_status_class": {"type": "string", "enum": sorted(ALLOWED_EXIT_STATUS_CLASSES)},
            "verifier_stdout_hash": {"type": "string", "pattern": "^[0-9a-f]{16,64}$"},
            "verifier_stderr_hash": {"type": "string", "pattern": "^[0-9a-f]{16,64}$"},
            "verifier_output_hash": {"type": "string", "pattern": "^[0-9a-f]{16,64}$"},
            "verifier_observation_hash": {"type": "string", "pattern": "^[0-9a-f]{16,64}$"},
            "target_binding_class": {"type": "string", "enum": sorted(ALLOWED_TARGET_BINDING_CLASSES)},
            "target_binding_rule_id_hash": {"type": "string", "pattern": "^[0-9a-f]{16,64}$"},
            "derived_projection_lane": {"type": "boolean", "const": False},
            "private_or_status_return": {"type": "boolean", "const": False},
            "generic_selected_test_collapsed": {"type": "boolean", "const": False},
            "strict_eval_eligible": {"type": "boolean", "const": False},
            "source_heldout_admissible": {"type": "boolean", "const": False},
            "level3_admitted": {"type": "boolean", "const": False},
            "patch_trace_admitted": {"type": "boolean", "const": False},
            "repair_claim_admitted": {"type": "boolean", "const": False},
            "fail_to_pass_claim_admitted": {"type": "boolean", "const": False},
            "training_allowed": {"type": "boolean", "const": False},
        },
    }


def rejection_rules() -> dict[str, Any]:
    return {
        "stage": STAGE,
        "rule_set": "stage12534_public_local_verifier_observation_supply_gate_v1",
        "reject_if": [
            "raw_key_or_raw_value_guardrail_fails",
            "source_lineage_checked_is_not_true",
            "hydratable_verifier_observation_candidate_is_not_true",
            "controlled_fixture_like_is_true",
            "derived_projection_lane_is_true",
            "private_or_status_return_is_true",
            "generic_selected_test_collapsed_is_true",
            "duplicate_key_matches_stage12533_or_within_candidate_batch",
            "task_projection_not_in_allowed_projection_set",
            "target_semantic_value_missing_or_generic_candidate_selected_test_backed",
            "missing_actual_command_output_verifier_observation_provenance",
            "target_not_bound_to_observed_verifier_status",
            "same_command_or_observation_hash_reused_with_different_target",
            "any_level3_patch_trace_repair_fail_to_pass_strict_eval_source_heldout_or_training_claim_true",
            "candidate_batch_introduces_collapse_group",
        ],
        "allowed_task_projections": ["transition_verifier_transition", "transition_continue_or_stop"],
        "countable_only_after_all_rules_pass": True,
        "training_allowed_only_if_countable_total_reaches_500_and_all_rules_pass": True,
    }


def deterministic_commands() -> dict[str, Any]:
    return {
        "stage": STAGE,
        "commands": [
            {
                "name": "build_gate",
                "argv": ["python", "scripts/build_stage12534_fresh_hydratable_verifier_observation_admission_gate.py"],
                "writes": [
                    f"runs/local/artifacts/{STAGE}/{SCHEMA_NAME}",
                    f"runs/local/artifacts/{STAGE}/{RULES_NAME}",
                    f"runs/local/artifacts/{STAGE}/{COMMANDS_NAME}",
                    f"runs/summaries/{STAGE}.json",
                ],
            },
            {
                "name": "validate_sanitized_supply_jsonl",
                "argv": [
                    "python",
                    "scripts/build_stage12534_fresh_hydratable_verifier_observation_admission_gate.py",
                    "--validate-supply",
                    "runs/local/artifacts/stage12534_candidate_supply/sanitized_public_local_verifier_observation_rows.jsonl",
                ],
                "input_contract": f"runs/local/artifacts/{STAGE}/{SCHEMA_NAME}",
                "rejection_rules": f"runs/local/artifacts/{STAGE}/{RULES_NAME}",
            },
            {
                "name": "contract_tests",
                "argv": ["pytest", "-q", "tests/test_stage12534_fresh_hydratable_verifier_observation_admission_gate.py"],
            },
        ],
        "raw_content_policy": "commands reference only repo-local scripts and sanitized JSONL contracts; candidate rows must contain hashes/classes only",
    }


def schema_issues(row: dict[str, Any]) -> list[str]:
    issues = []
    for field in supply_schema()["required"]:
        if field not in row:
            issues.append(f"missing_{field}")
    for field in ("source_lineage_checked", "hydratable_verifier_observation_candidate"):
        if row.get(field) is not True:
            issues.append(f"{field}_not_true")
    if row.get("controlled_fixture_like") is not False:
        issues.append("controlled_fixture_like_not_false")
    if projection(row) not in {"transition_verifier_transition", "transition_continue_or_stop"}:
        issues.append("unsupported_task_projection")
    for field in ("source_line_hash", "root_lineage_key_hash", "repo_family_hash"):
        value = str(row.get(field) or "")
        if not re.fullmatch(r"[0-9a-f]{16,64}", value):
            issues.append(f"{field}_not_hash")
    for field in (
        "verifier_command_ref_hash",
        "command_result_id_hash",
        "verifier_stdout_hash",
        "verifier_stderr_hash",
        "verifier_output_hash",
        "verifier_observation_hash",
        "target_binding_rule_id_hash",
    ):
        value = str(row.get(field) or "")
        if not re.fullmatch(r"[0-9a-f]{16,64}", value):
            issues.append(f"{field}_not_hash")
    if row.get("actual_verifier_command_output_observation_provenance") is not True:
        issues.append("actual_verifier_command_output_observation_provenance_not_true")
    if row.get("verifier_exit_status_class") not in ALLOWED_EXIT_STATUS_CLASSES:
        issues.append("unsupported_verifier_exit_status_class")
    if row.get("target_binding_class") not in ALLOWED_TARGET_BINDING_CLASSES:
        issues.append("unsupported_target_binding_class")
    if row.get("target_semantic_value") != row.get("verifier_status"):
        issues.append("target_not_bound_to_observed_verifier_status")
    return issues


def row_rejection_reasons(row: dict[str, Any], duplicate_keys: set[tuple[str, str, str, str]]) -> list[str]:
    reasons = schema_issues(row)
    if row.get("derived_projection_lane") is True:
        reasons.append("derived_projection_lane")
    if row.get("private_or_status_return") is True:
        reasons.append("private_or_status_return")
    if row.get("generic_selected_test_collapsed") is True:
        reasons.append("generic_selected_test_collapsed")
    if target_value(row) in {"candidate_0", "candidate_selected_test_backed"}:
        reasons.append("generic_selected_test_target")
    if duplicate_key(row) in duplicate_keys:
        reasons.append("duplicate_key_matches_existing")
    reasons.extend(risky_claims(row))
    return sorted(set(reasons))


def validate_supply_rows(rows: list[dict[str, Any]], repaired_rows: list[dict[str, Any]]) -> dict[str, Any]:
    duplicate_keys = existing_duplicate_keys(repaired_rows)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_batch: set[tuple[str, str, str, str]] = set()
    seen_observation: dict[str, str] = {}
    seen_command: dict[str, str] = {}
    for row in rows:
        reasons = row_rejection_reasons(row, duplicate_keys)
        key = duplicate_key(row)
        if key in seen_batch:
            reasons.append("duplicate_key_within_candidate_batch")
        observation_hash = str(row.get("verifier_observation_hash") or "")
        command_hash = str(row.get("command_result_id_hash") or "")
        target = target_value(row)
        if observation_hash:
            prior_target = seen_observation.get(observation_hash)
            if prior_target is not None and prior_target != target:
                reasons.append("same_verifier_observation_hash_reused_with_different_target")
            seen_observation.setdefault(observation_hash, target)
        if command_hash:
            prior_target = seen_command.get(command_hash)
            if prior_target is not None and prior_target != target:
                reasons.append("same_command_result_hash_reused_with_different_target")
            seen_command.setdefault(command_hash, target)
        if reasons:
            rejected.append({"candidate_ref_hash": stable_hash(row), "blocked_reasons": sorted(set(reasons))})
        else:
            sanitized = {
                "stage": STAGE,
                "candidate_ref_hash": stable_hash(row),
                "source_stage": row["source_stage"],
                "source_line_hash": row["source_line_hash"],
                "root_lineage_key_hash": row["root_lineage_key_hash"],
                "repo_family_hash": row["repo_family_hash"],
                "language_family": row["language_family"],
                "task_projection": row["task_projection"],
                "target_semantic_value": row["target_semantic_value"],
                "verifier_status": row["verifier_status"],
                "actual_verifier_command_output_observation_provenance": True,
                "verifier_command_ref_hash": row["verifier_command_ref_hash"],
                "command_result_id_hash": row["command_result_id_hash"],
                "verifier_exit_status_class": row["verifier_exit_status_class"],
                "verifier_stdout_hash": row["verifier_stdout_hash"],
                "verifier_stderr_hash": row["verifier_stderr_hash"],
                "verifier_output_hash": row["verifier_output_hash"],
                "verifier_observation_hash": row["verifier_observation_hash"],
                "target_binding_class": row["target_binding_class"],
                "target_binding_rule_id_hash": row["target_binding_rule_id_hash"],
                "source_lineage_checked": True,
                "hydratable_verifier_observation_candidate": True,
                "countable_train_support": True,
                "training_allowed": False,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "level3_admitted": False,
                "patch_trace_admitted": False,
                "repair_claim_admitted": False,
                "fail_to_pass_claim_admitted": False,
            }
            accepted.append(sanitized)
            duplicate_keys.add(key)
            seen_batch.add(key)
    scan = guardrail_scan(accepted, rejected)
    collapse = collapse_audit(accepted)
    if not scan["scan_passed"] or collapse["collapse_group_count"]:
        rejected.extend({"candidate_ref_hash": row["candidate_ref_hash"], "blocked_reasons": ["batch_guardrail_or_collapse_gate_failed"]} for row in accepted)
        accepted = []
    return {"accepted_rows": accepted, "rejected_rows": rejected, "guardrail_scan": scan, "anti_collapse": collapse}


def validate_supply_file(path: Path) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    repaired_rows = read_jsonl(STAGE12533_REPAIRED_ROWS)
    rows = read_jsonl(path)
    result = validate_supply_rows(rows, repaired_rows)
    report = {
        "stage": STAGE,
        "input_row_count": len(rows),
        "accepted_countable_rows": len(result["accepted_rows"]),
        "rejected_rows": len(result["rejected_rows"]),
        "guardrail_scan_passed": result["guardrail_scan"]["scan_passed"],
        "raw_leak_count": result["guardrail_scan"]["raw_leak_count"],
        "collapse_group_count": result["anti_collapse"]["collapse_group_count"],
        "training_allowed": False,
        "countable_only_language_counts": count_by(result["accepted_rows"], "language_family"),
        "countable_only_projection_counts": count_by(result["accepted_rows"], "task_projection"),
    }
    write_jsonl(OUT / "validated_supply_accepted_rows.jsonl", result["accepted_rows"])
    write_jsonl(OUT / "validated_supply_rejected_rows.jsonl", result["rejected_rows"])
    write_json(OUT / "validated_supply_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if result["guardrail_scan"]["scan_passed"] else 1


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s12533 = read_json(STAGE12533_SUMMARY)
    s12421 = read_json(STAGE12421_SUMMARY)
    s12216 = read_json(STAGE12216_SUMMARY)
    s12418 = read_json(STAGE12418_MANIFEST)
    s12457 = read_json(STAGE12457_SUMMARY)

    repaired_rows = read_jsonl(STAGE12533_REPAIRED_ROWS)
    duplicate_keys = existing_duplicate_keys(repaired_rows)
    stage12418_rows = read_jsonl(STAGE12418_ROWS)
    stage12421_rows = read_jsonl(STAGE12421_ROWS)
    stage12457_rows = read_jsonl(STAGE12457_ROWS)

    projected_candidates = [stage12418_candidate(row, duplicate_keys) for row in stage12418_rows]
    direct_candidates = [stage12421_candidate(row, duplicate_keys) for row in stage12421_rows]
    selected_test_gate = [selected_test_gate_row(row) for row in stage12457_rows]
    all_candidates = projected_candidates + direct_candidates + selected_test_gate

    adoption_candidates = [
        row for row in all_candidates
        if row["fresh_public_local_source_supply"]
        and row["source_lineage_checked"]
        and not row["blocked_reasons"]
    ]
    candidate_collapse = collapse_audit(adoption_candidates)
    scan = guardrail_scan(all_candidates)

    additional_admitted_rows = 0
    current_total = int(s12533.get("countable_train_support_count") or 0) + additional_admitted_rows
    remaining_gap = max(0, TARGET_TRAIN_SUPPORT_FLOOR - current_total)

    checks = {
        "stage12533_guardrail_passed": bool(s12533.get("guardrail_scan_passed")),
        "stage12421_guardrail_passed": bool(s12421.get("guardrail_scan_passed")),
        "stage12418_guardrail_passed": bool(s12418.get("guardrail_scan_passed")),
        "stage12216_training_disallowed": s12216.get("training_allowed") is False,
        "no_raw_leak": scan["scan_passed"],
        "no_duplicate_train_rows": len(adoption_candidates) == len({duplicate_key(row) for row in adoption_candidates}),
        "no_candidate_collapse_groups": candidate_collapse["collapse_group_count"] == 0,
        "source_lineage_checked_for_candidates": all(row["source_lineage_checked"] for row in all_candidates),
        "derived_stage12216_rows_not_counted_as_fresh": all(not row["countable_train_support"] for row in projected_candidates),
        "selected_test_control_rows_not_counted_as_fresh": all(not row["countable_train_support"] for row in selected_test_gate),
        "zero_level3_patch_trace_repair_credit": all(
            not truthy(row.get(field))
            for row in all_candidates
            for field in ("level3_admitted", "patch_trace_admitted", "repair_claim_admitted", "fail_to_pass_claim_admitted")
        ),
    }

    blockers = []
    if not adoption_candidates:
        blockers.append("no_fresh_non_derivative_public_local_hydratable_verifier_observation_rows_identified")
    if current_total < TARGET_TRAIN_SUPPORT_FLOOR:
        blockers.append("500_countable_train_support_floor_not_reached")
    if not all(checks.values()):
        blockers.append("separate_training_gate_not_passed")

    candidates_path = OUT / "fresh_hydratable_verifier_observation_candidate_gate_rows.jsonl"
    admitted_path = OUT / "admitted_fresh_hydratable_train_support_rows.jsonl"
    guardrail_path = OUT / "guardrail_scan.json"
    collapse_path = OUT / "candidate_anti_collapse_audit.json"
    schema_path = OUT / SCHEMA_NAME
    rules_path = OUT / RULES_NAME
    commands_path = OUT / COMMANDS_NAME
    write_jsonl(candidates_path, all_candidates)
    write_jsonl(admitted_path, [])
    write_json(guardrail_path, scan)
    write_json(collapse_path, {"adoption_candidates": candidate_collapse})
    write_json(schema_path, supply_schema())
    write_json(rules_path, rejection_rules())
    write_json(commands_path, deterministic_commands())

    blocked_reasons = Counter(reason for row in all_candidates for reason in row.get("blocked_reasons", []))
    summary = {
        "stage": STAGE,
        "record_type": "fresh_hydratable_verifier_observation_admission_gate_v1",
        "decision": "fresh_hydratable_verifier_observation_supply_gate_prepared_no_rows_admitted",
        "claim_boundary": (
            "Hash/class-only admission gate after Stage12533 repair. Stage12216/Stage12418 rows are treated as "
            "derived verifier-observation projections and selected-test control rows remain noncountable; no "
            "Level3, patch-trace, repair, fail-to-pass, strict-eval, source-heldout, or external repair credit is granted."
        ),
        "source_inventory": {
            "stage12533_repaired_rows": len(repaired_rows),
            "stage12216_normalized_source_rows": int(s12216.get("row_count") or len(read_jsonl(STAGE12216_ROWS))),
            "stage12418_sanitized_projection_rows": len(stage12418_rows),
            "stage12421_direct_projection_rows": len(stage12421_rows),
            "stage12457_selected_test_control_rows": len(stage12457_rows),
        },
        "candidate_counts": {
            "stage12216_stage12418_projected_candidates": len(projected_candidates),
            "stage12421_direct_candidates": len(direct_candidates),
            "stage12457_selected_test_gate_rows": len(selected_test_gate),
            "fresh_public_local_adoption_candidates": len(adoption_candidates),
            "admitted_additional_train_support_rows": additional_admitted_rows,
        },
        "gate_type": "executable_public_local_verifier_observation_supply_validator",
        "fresh_supply_input_present": False,
        "fresh_supply_candidate_count": len(adoption_candidates),
        "fresh_supply_admitted_count": additional_admitted_rows,
        "new_countable_train_support_count": additional_admitted_rows,
        "countable_train_support": {
            "stage12533_repaired_countable_total": int(s12533.get("countable_train_support_count") or 0),
            "admitted_additional_fresh_hydratable_rows": additional_admitted_rows,
            "current_countable_total": current_total,
            "target_floor": TARGET_TRAIN_SUPPORT_FLOOR,
            "remaining_gap_to_500": remaining_gap,
        },
        "countable_train_support_count": current_total,
        "remaining_gap_to_500": remaining_gap,
        "blocked_reason_counts": dict(sorted(blocked_reasons.items())),
        "candidate_language_counts": count_by(all_candidates, "language_family"),
        "candidate_projection_counts": count_by(all_candidates, "task_projection"),
        "countable_only_language_counts": {},
        "countable_only_projection_counts": {},
        "checks": checks,
        "anti_collapse": {
            "adoption_candidates": {
                "collapse_group_count": candidate_collapse["collapse_group_count"],
                "max_target_share": candidate_collapse["max_target_share"],
                "target_dominance_passed": candidate_collapse["target_dominance_passed"],
            }
        },
        "post_admission_collapse_group_count": candidate_collapse["collapse_group_count"],
        "guardrail_scan_passed": scan["scan_passed"],
        "raw_leak_count": scan["raw_leak_count"],
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
        "training_allowed": False,
        "training_blockers": blockers,
        "next_stage": "supply_fresh_public_local_verifier_observation_rows_then_run_stage12534_validate_supply",
        "next_admission_gate": {
            "gate_is_executable": True,
            "required_input": "new direct public/local verifier-observation source rows not already normalized into Stage12418 or counted by Stage12533",
            "minimum_batch_size_to_unblock_training": remaining_gap,
            "schema_ref": str(schema_path.relative_to(ROOT)),
            "rejection_rules_ref": str(rules_path.relative_to(ROOT)),
            "deterministic_commands_ref": str(commands_path.relative_to(ROOT)),
            "required_checks": [
                "raw_guardrail_scan_passed",
                "source_lineage_checked",
                "not_duplicate_of_stage12533_or_stage12418",
                "not_controlled_fixture_like",
                "not_derived_projection_lane",
                "anti_collapse_passed",
                "zero_level3_patch_trace_repair_fail_to_pass_strict_eval_source_heldout_claims",
            ],
        },
        "artifact_refs": {
            "candidate_gate_rows": str(candidates_path.relative_to(ROOT)),
            "admitted_rows": str(admitted_path.relative_to(ROOT)),
            "guardrail_scan": str(guardrail_path.relative_to(ROOT)),
            "candidate_anti_collapse_audit": str(collapse_path.relative_to(ROOT)),
            "supply_schema": str(schema_path.relative_to(ROOT)),
            "rejection_rules": str(rules_path.relative_to(ROOT)),
            "deterministic_commands": str(commands_path.relative_to(ROOT)),
        },
        "input_hashes": {
            "stage12533_summary": file_hash(STAGE12533_SUMMARY),
            "stage12533_repaired_rows": file_hash(STAGE12533_REPAIRED_ROWS),
            "stage12421_summary": file_hash(STAGE12421_SUMMARY),
            "stage12421_rows": file_hash(STAGE12421_ROWS),
            "stage12216_summary": file_hash(STAGE12216_SUMMARY),
            "stage12216_rows": file_hash(STAGE12216_ROWS),
            "stage12418_manifest": file_hash(STAGE12418_MANIFEST),
            "stage12418_rows": file_hash(STAGE12418_ROWS),
            "stage12457_summary": file_hash(STAGE12457_SUMMARY),
            "stage12457_rows": file_hash(STAGE12457_ROWS),
        },
        "upstream_decisions": {
            "stage12533": s12533.get("decision"),
            "stage12421": s12421.get("decision"),
            "stage12216": s12216.get("decision"),
            "stage12418": s12418.get("decision"),
            "stage12457": s12457.get("decision"),
        },
    }
    write_json(OUT / "fresh_hydratable_verifier_observation_admission_gate.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--validate-supply":
        raise SystemExit(validate_supply_file(Path(sys.argv[2])))
    if len(sys.argv) != 1:
        raise SystemExit("usage: build_stage12534_fresh_hydratable_verifier_observation_admission_gate.py [--validate-supply JSONL]")
    main()
