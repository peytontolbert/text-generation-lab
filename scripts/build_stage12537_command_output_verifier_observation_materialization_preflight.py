#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12537_command_output_verifier_observation_materialization_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12536_REPAIR = (
    ROOT
    / "runs/local/artifacts/stage12536_stage12535_semantic_risk_audit"
    / "stage12535_exact_repair_requirements.json"
)
STAGE12534_SCHEMA = (
    ROOT
    / "runs/local/artifacts/stage12534_fresh_hydratable_verifier_observation_admission_gate"
    / "public_local_verifier_observation_supply_schema.json"
)
STAGE12216_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12216_normalized_verifier_observation_dataset"
    / "normalized_verifier_observation_records.jsonl"
)
STAGE12418_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12418_normalized_verifier_observation_sanitized_canonicalizer"
    / "sanitized_normalized_verifier_observation_projection_rows.jsonl"
)
STAGE12421_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12421_new_direct_real_verifier_observation_miner"
    / "new_direct_verifier_observation_train_support_rows.jsonl"
)

CANDIDATE_ROWS_NAME = "real_command_output_verifier_observation_candidate_rows.jsonl"
BLOCKER_WORKLIST_NAME = "real_command_output_verifier_observation_blocker_worklist.jsonl"
PROVENANCE_AUDIT_NAME = "command_output_observation_provenance_audit.json"

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
ALLOWED_LANGUAGE_FAMILIES = {"python", "rust", "c_cpp", "web_js_ts_html", "unknown"}
ALLOWED_TASK_PROJECTIONS = {"transition_verifier_transition", "transition_continue_or_stop"}
DIRECT_VERIFIER_STATUSES = {"PASS_CURRENT_STATE", "FAIL_CURRENT_STATE", "INSUFFICIENT_EVIDENCE"}


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
        "scan_scope": "stage12537_hash_class_only_candidate_and_blocker_outputs",
    }


def risky_claims(row: dict[str, Any]) -> list[str]:
    admission = row.get("admission") if isinstance(row.get("admission"), dict) else {}
    claims = []
    for field in RISKY_FIELDS:
        if truthy(row.get(field)) or truthy(admission.get(field)):
            claims.append(field)
    return claims


def exit_status_class(returncode: Any) -> str:
    if returncode is None:
        return "exit_unknown"
    try:
        code = int(returncode)
    except (TypeError, ValueError):
        return "exit_unknown"
    if code == 0:
        return "exit_zero"
    return "exit_nonzero"


def verifier_status(row: dict[str, Any]) -> str:
    verifier_result = row.get("verifier_result") if isinstance(row.get("verifier_result"), dict) else {}
    observation = row.get("observation") if isinstance(row.get("observation"), dict) else {}
    state_after = row.get("state_after") if isinstance(row.get("state_after"), dict) else {}
    return str(
        verifier_result.get("verifier_status")
        or row.get("verifier_status")
        or row.get("verifier_transition")
        or observation.get("verifier_status")
        or state_after.get("verifier_transition")
        or ""
    )


def command_result(row: dict[str, Any]) -> dict[str, Any]:
    direct = row.get("command_result")
    if isinstance(direct, dict):
        return direct
    events = row.get("events") if isinstance(row.get("events"), list) else []
    for event in events:
        if isinstance(event, dict) and isinstance(event.get("command_result"), dict):
            return event["command_result"]
    return {}


def has_real_command_output_provenance(row: dict[str, Any]) -> bool:
    result = command_result(row)
    return bool(
        result.get("command_result_id")
        and result.get("command")
        and "returncode" in result
        and result.get("stdout_sha256")
        and result.get("stderr_sha256")
        and verifier_status(row)
    )


def blocker_ref(source_stage: str, line_no: Any, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "source_stage_hash": stable_hash(source_stage),
        "source_line_hash": stable_hash({"source_stage": source_stage, "line": line_no}),
        "source_record_hash": stable_hash(row),
    }


def stage12216_blocker(row: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    source_stage = str(row.get("stage") or "stage12216_normalized_verifier_observation_dataset")
    out = blocker_ref(source_stage, row.get("__line_no"), row)
    out.update(
        {
            "record_type": "stage12537_materialization_blocker_v1",
            "source_lane_class": "stage12216_raw_command_observation_scan",
            "blocked_reasons": sorted(set(reasons)),
            "candidate_row_emitted": False,
            "training_allowed": False,
            "countable_train_support": False,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "level3_admitted": False,
            "patch_trace_admitted": False,
            "repair_claim_admitted": False,
            "fail_to_pass_claim_admitted": False,
        }
    )
    return out


def stage12216_candidate(row: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    reasons = []
    result = command_result(row)
    status = verifier_status(row)
    if not has_real_command_output_provenance(row):
        reasons.append("missing_actual_verifier_command_output_observation_provenance")
    if status not in DIRECT_VERIFIER_STATUSES:
        reasons.append("unsupported_or_forbidden_target_status_for_stage12537_preflight")
    if truthy(row.get("controlled_fixture_like")):
        reasons.append("controlled_fixture_like_not_materialized")
    reasons.extend(risky_claims(row))
    if reasons:
        return None, stage12216_blocker(row, reasons)

    command_hash = stable_hash(
        {
            "command": result.get("command"),
            "cwd": result.get("cwd"),
            "command_result_id": result.get("command_result_id"),
        }
    )
    stdout_hash = str(result.get("stdout_sha256"))
    stderr_hash = str(result.get("stderr_sha256"))
    combined_output_hash = stable_hash(
        {
            "returncode": result.get("returncode"),
            "stdout_sha256": stdout_hash,
            "stderr_sha256": stderr_hash,
        }
    )
    source_stage = str(row.get("source_stage") or row.get("rollup_source_stage") or row.get("stage") or "unknown")
    root_lineage_hash = stable_hash(
        {
            "source_stage": source_stage,
            "command_result_id": result.get("command_result_id"),
            "status": status,
            "root": row.get("root_id"),
        }
    )
    repo_hash = stable_hash({"repo_family": row.get("repo_family"), "root": row.get("root_id")})
    source_line_hash = stable_hash(
        {
            "source_stage": source_stage,
            "stage12216_source_line": row.get("stage12216_source_line") or row.get("__line_no"),
            "command_result_id": result.get("command_result_id"),
        }
    )
    observation = row.get("observation") if isinstance(row.get("observation"), dict) else {}
    candidate = {
        "stage": STAGE,
        "record_type": "real_command_output_verifier_observation_materialization_candidate_v1",
        "candidate_ref_hash": stable_hash({"line": row.get("__line_no"), "result": result.get("command_result_id"), "status": status}),
        "source_stage": source_stage,
        "source_line_hash": source_line_hash,
        "root_lineage_key_hash": root_lineage_hash,
        "repo_family_hash": repo_hash,
        "language_family": str(row.get("language_family") or row.get("language") or "unknown")
        if str(row.get("language_family") or row.get("language") or "unknown") in ALLOWED_LANGUAGE_FAMILIES
        else "unknown",
        "task_projection": "transition_verifier_transition",
        "target_semantic_value": status,
        "verifier_status": status,
        "source_lineage_checked": True,
        "hydratable_verifier_observation_candidate": True,
        "controlled_fixture_like": False,
        "derived_projection_lane": False,
        "private_or_status_return": False,
        "generic_selected_test_collapsed": False,
        "actual_verifier_command_output_observation_provenance": True,
        "provenance_source_artifact_hash": file_hash(STAGE12216_ROWS),
        "provenance_source_line_hash": stable_hash({"stage12216_line": row.get("__line_no")}),
        "verifier_command_ref_hash": command_hash,
        "command_result_id_hash": stable_hash(result.get("command_result_id")),
        "verifier_exit_status_class": exit_status_class(result.get("returncode")),
        "verifier_stdout_hash": stdout_hash,
        "verifier_stderr_hash": stderr_hash,
        "verifier_output_hash": combined_output_hash,
        "verifier_observation_hash": stable_hash(
            {
                "observation_id": observation.get("observation_id"),
                "status": status,
                "command_result_id": result.get("command_result_id"),
            }
        ),
        "target_binding_class": "target_semantic_value_from_observed_verifier_result_status",
        "target_binding_rule_id_hash": stable_hash({"rule": "observed_verifier_result_status", "status": status}),
        "stage12534_constraint_preflight_passed": True,
        "countable_train_support": False,
        "training_allowed": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
    }
    return candidate, None


def stage12534_constraint_issues(row: dict[str, Any]) -> list[str]:
    issues = []
    required = (
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
    )
    for field in required:
        if field not in row:
            issues.append(f"missing_{field}")
    if row.get("source_lineage_checked") is not True:
        issues.append("source_lineage_checked_not_true")
    if row.get("hydratable_verifier_observation_candidate") is not True:
        issues.append("hydratable_verifier_observation_candidate_not_true")
    if row.get("controlled_fixture_like") is not False:
        issues.append("controlled_fixture_like_not_false")
    if row.get("derived_projection_lane") is True:
        issues.append("derived_projection_lane")
    if row.get("private_or_status_return") is True:
        issues.append("private_or_status_return")
    if row.get("generic_selected_test_collapsed") is True:
        issues.append("generic_selected_test_collapsed")
    if row.get("task_projection") not in ALLOWED_TASK_PROJECTIONS:
        issues.append("unsupported_task_projection")
    for field in ("source_line_hash", "root_lineage_key_hash", "repo_family_hash"):
        value = str(row.get(field) or "")
        if not re.fullmatch(r"[0-9a-f]{16,64}", value):
            issues.append(f"{field}_not_hash")
    issues.extend(risky_claims(row))
    return sorted(set(issues))


def dedupe_candidates(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted = []
    blocked = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        key = (
            str(row.get("root_lineage_key_hash") or ""),
            str(row.get("task_projection") or ""),
            str(row.get("target_semantic_value") or ""),
            str(row.get("verifier_command_ref_hash") or ""),
        )
        issues = stage12534_constraint_issues(row)
        if key in seen:
            issues.append("duplicate_command_target_within_stage12537_batch")
        if issues:
            blocked.append(
                {
                    "stage": STAGE,
                    "record_type": "stage12537_materialization_blocker_v1",
                    "candidate_ref_hash": row.get("candidate_ref_hash") or stable_hash(row),
                    "source_record_hash": stable_hash(row),
                    "blocked_reasons": sorted(set(issues)),
                    "candidate_row_emitted": False,
                    "training_allowed": False,
                    "countable_train_support": False,
                    "strict_eval_eligible": False,
                    "source_heldout_admissible": False,
                    "level3_admitted": False,
                    "patch_trace_admitted": False,
                    "repair_claim_admitted": False,
                    "fail_to_pass_claim_admitted": False,
                }
            )
        else:
            accepted.append(row)
            seen.add(key)
    return accepted, blocked


def hashed_source_inventory(rows: list[dict[str, Any]], source_name: str, path: Path) -> dict[str, Any]:
    return {
        "source_name": source_name,
        "source_artifact_hash": file_hash(path),
        "row_count": len(rows),
    }


def derivative_source_blockers(rows: list[dict[str, Any]], source_name: str, path: Path, reason: str) -> list[dict[str, Any]]:
    blockers = []
    for row in rows:
        out = blocker_ref(str(row.get("stage") or source_name), row.get("__line_no"), row)
        out.update(
            {
                "record_type": "stage12537_materialization_blocker_v1",
                "source_lane_class": source_name,
                "source_artifact_hash": file_hash(path),
                "blocked_reasons": [reason],
                "candidate_row_emitted": False,
                "training_allowed": False,
                "countable_train_support": False,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "level3_admitted": False,
                "patch_trace_admitted": False,
                "repair_claim_admitted": False,
                "fail_to_pass_claim_admitted": False,
            }
        )
        blockers.append(out)
    return blockers


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    repair = read_json(STAGE12536_REPAIR)
    schema = read_json(STAGE12534_SCHEMA)
    stage12216_rows = read_jsonl(STAGE12216_ROWS)
    stage12418_rows = read_jsonl(STAGE12418_ROWS)
    stage12421_rows = read_jsonl(STAGE12421_ROWS)

    raw_candidates = []
    blockers = []
    provenance_rows = 0
    for row in stage12216_rows:
        if has_real_command_output_provenance(row):
            provenance_rows += 1
        candidate, blocker = stage12216_candidate(row)
        if candidate is not None:
            raw_candidates.append(candidate)
        if blocker is not None:
            blockers.append(blocker)

    candidates, candidate_blockers = dedupe_candidates(raw_candidates)
    blockers.extend(candidate_blockers)
    blockers.extend(
        derivative_source_blockers(
            stage12418_rows,
            "stage12418_sanitized_projection_scan",
            STAGE12418_ROWS,
            "derived_sanitized_projection_lacks_independent_command_output_hash_provenance",
        )
    )
    blockers.extend(
        derivative_source_blockers(
            stage12421_rows,
            "stage12421_direct_projection_scan",
            STAGE12421_ROWS,
            "projection_rows_lack_stdout_stderr_digest_fields_required_by_stage12537",
        )
    )

    scan = guardrail_scan(candidates, blockers)
    if not scan["scan_passed"]:
        blockers.extend(
            {
                "stage": STAGE,
                "record_type": "stage12537_materialization_blocker_v1",
                "candidate_ref_hash": row.get("candidate_ref_hash") or stable_hash(row),
                "source_record_hash": stable_hash(row),
                "blocked_reasons": ["raw_leak_guard_failed_for_candidate_batch"],
                "candidate_row_emitted": False,
                "training_allowed": False,
                "countable_train_support": False,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "level3_admitted": False,
                "patch_trace_admitted": False,
                "repair_claim_admitted": False,
                "fail_to_pass_claim_admitted": False,
            }
            for row in candidates
        )
        candidates = []
        scan = guardrail_scan(candidates, blockers)

    candidate_path = OUT / CANDIDATE_ROWS_NAME
    blocker_path = OUT / BLOCKER_WORKLIST_NAME
    audit_path = OUT / PROVENANCE_AUDIT_NAME
    write_jsonl(candidate_path, candidates)
    write_jsonl(blocker_path, blockers)

    status_counts = Counter(str(row.get("target_semantic_value") or "unknown") for row in candidates)
    language_counts = Counter(str(row.get("language_family") or "unknown") for row in candidates)
    blocker_counts = Counter(reason for row in blockers for reason in row.get("blocked_reasons", []))
    provenance_audit = {
        "stage": STAGE,
        "record_type": "stage12537_command_output_provenance_audit_v1",
        "repair_requirements_hash": file_hash(STAGE12536_REPAIR),
        "stage12534_schema_hash": file_hash(STAGE12534_SCHEMA),
        "source_inventory": [
            hashed_source_inventory(stage12216_rows, "stage12216_normalized_verifier_observation_dataset", STAGE12216_ROWS),
            hashed_source_inventory(stage12418_rows, "stage12418_sanitized_projection_scan", STAGE12418_ROWS),
            hashed_source_inventory(stage12421_rows, "stage12421_direct_projection_scan", STAGE12421_ROWS),
        ],
        "stage12216_rows_with_actual_command_output_observation_provenance": provenance_rows,
        "candidate_rows_with_required_provenance": len(candidates),
        "blocked_or_worklist_rows": len(blockers),
        "guardrail_scan_passed": scan["scan_passed"],
        "raw_leak_count": scan["raw_leak_count"],
        "allowed_candidate_statuses": sorted(DIRECT_VERIFIER_STATUSES),
        "stage12536_requirements_checked": bool(repair.get("required_before_any_training_claim")),
        "stage12534_required_fields_checked": schema.get("required", []),
    }
    write_json(audit_path, provenance_audit)

    decision = (
        "real_command_output_verifier_observation_candidates_materialized_preflight_only"
        if candidates
        else "fail_closed_no_real_command_output_verifier_observation_candidates_materialized"
    )
    summary = {
        "stage": STAGE,
        "record_type": "real_command_output_verifier_observation_materialization_preflight_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12537 only materializes sanitized command-output verifier-observation candidate rows from "
            "existing local artifacts. It grants no training admission, no repair credit, no patch-trace credit, "
            "no strict-eval/source-heldout eligibility, no Level3/Level4 admission, and no product-progress claim."
        ),
        "candidate_row_count": len(candidates),
        "blocker_worklist_row_count": len(blockers),
        "stage12216_rows_scanned": len(stage12216_rows),
        "stage12216_rows_with_actual_command_output_observation_provenance": provenance_rows,
        "candidate_status_counts": dict(sorted(status_counts.items())),
        "candidate_language_counts": dict(sorted(language_counts.items())),
        "blocked_reason_counts": dict(sorted(blocker_counts.items())),
        "guardrail_scan_passed": scan["scan_passed"],
        "raw_leak_count": scan["raw_leak_count"],
        "training_allowed": False,
        "countable_train_support": False,
        "new_countable_train_support_count": 0,
        "level3_admitted_rows": 0,
        "patch_trace_admitted_rows": 0,
        "repair_claim_admitted_rows": 0,
        "fail_to_pass_claim_admitted_rows": 0,
        "strict_eval_eligible_count": 0,
        "source_heldout_admissible_count": 0,
        "training_blockers": [
            "stage12537_is_materialization_preflight_only",
            "stage12534_cli_validation_not_run_to_preserve_stage12537_file_ownership",
            "separate_semantic_review_not_passed",
            "500_countable_train_support_floor_not_reached",
        ],
        "artifact_refs": {
            "candidate_rows": str(candidate_path.relative_to(ROOT)),
            "blocker_worklist": str(blocker_path.relative_to(ROOT)),
            "provenance_audit": str(audit_path.relative_to(ROOT)),
            "summary": str(SUMMARY.relative_to(ROOT)),
        },
        "input_hashes": {
            "stage12536_repair_requirements": file_hash(STAGE12536_REPAIR),
            "stage12534_schema": file_hash(STAGE12534_SCHEMA),
            "stage12216_rows": file_hash(STAGE12216_ROWS),
            "stage12418_rows": file_hash(STAGE12418_ROWS),
            "stage12421_rows": file_hash(STAGE12421_ROWS),
        },
        "next_stage": "run_stage12534_validate_supply_on_stage12537_candidate_rows_then_separate_semantic_review",
    }
    write_json(SUMMARY, summary)
    return summary


def main() -> None:
    build()


if __name__ == "__main__":
    main()
