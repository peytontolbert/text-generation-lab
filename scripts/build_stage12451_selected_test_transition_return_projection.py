#!/usr/bin/env python3
"""Bounded projection for the non-web selected-test Stage12445 return slot.

Stage12451 reads only the scouted selected-test artifacts named in the stage
request. It may write Stage12445 return rows only when a scout row already
contains the exact public-safe return schema fields and passes Stage12445's
row_gate. It never fabricates proof slots, never admits rows, and never emits
training rows.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12451_selected_test_transition_return_projection"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

TARGET_REQUEST_HASH = "ac183215a709860587488958"
TARGET_ADAPTER_REQUEST_ID = "selected_test_transition_root_batch_non_web_first"
SCHEMA_NAME = "adapter_executor_return_public_safe_v1"
TARGET_EXPECTED_RETURN = (
    ROOT
    / "runs/local/artifacts/stage12445_adapter_execution_return_ingest_and_level3_gate"
    / "returns/selected_test_transition_root_batch_non_web_first.return.jsonl"
)

STAGE12444_OUT = ROOT / "runs/local/artifacts/stage12444_adapter_execution_request_manifest"
EXECUTOR_RETURN_SCHEMA = STAGE12444_OUT / "executor_return_schema.json"
ADAPTER_REQUESTS = STAGE12444_OUT / "adapter_execution_requests.jsonl"
EXPECTED_RETURN_MANIFEST = STAGE12444_OUT / "expected_return_manifest.jsonl"

SCOUT_INPUTS = {
    "stage12372_git_rust_task_specific_selected_test_rerender": (
        ROOT
        / "runs/local/artifacts/stage12372_git_rust_task_specific_selected_test_rerender"
        / "git_rust_task_specific_selected_test_rows.jsonl"
    ),
    "stage12368_cpp_task_specific_selected_test_admission": (
        ROOT
        / "runs/local/artifacts/stage12368_cpp_task_specific_selected_test_admission"
        / "cpp_task_specific_selected_test_train_support_rows.jsonl"
    ),
    "stage12382_einops_task_specific_selected_test_rerender": (
        ROOT
        / "runs/local/artifacts/stage12382_einops_task_specific_selected_test_rerender"
        / "einops_task_specific_selected_test_rows.jsonl"
    ),
    "stage12374_python_task_specific_selected_test_rerender": (
        ROOT
        / "runs/local/artifacts/stage12374_python_task_specific_selected_test_rerender"
        / "python_task_specific_selected_test_rows.jsonl"
    ),
    "stage12143_no_install_selected_test_expansion": (
        ROOT
        / "runs/local/artifacts/stage12143_no_install_selected_test_expansion"
        / "selected_test_expansion_results.jsonl"
    ),
}
PRIMARY_SCOUT_STAGE_ORDER = [
    "stage12372_git_rust_task_specific_selected_test_rerender",
    "stage12368_cpp_task_specific_selected_test_admission",
    "stage12382_einops_task_specific_selected_test_rerender",
    "stage12374_python_task_specific_selected_test_rerender",
]
FILL_SCOUT_STAGE_ORDER = [
    "stage12143_no_install_selected_test_expansion",
]

MAX_INPUT_ROWS_PER_ARTIFACT = 100
MAX_SCOUTED_CANDIDATES = 5
MAX_PROJECTED_ROWS = 5

ZERO_AUTHORITY = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "execution_performed_by_stage": False,
    "emitted_training_rows": 0,
    "sealed_eval_rows_emitted": 0,
}

FORBIDDEN_PUBLIC_KEYS = {
    "path",
    "paths",
    "url",
    "urls",
    "uri",
    "command",
    "command_text",
    "commands",
    "stdout",
    "stderr",
    "output",
    "outputs",
    "diff",
    "patch",
    "patch_body",
    "source",
    "source_path",
    "source_text",
    "private_locator",
    "raw",
    "raw_text",
    "trace",
    "trace_text",
    "issue_body",
}
ALLOWED_KEY_CONTEXT_RE = re.compile(
    r"(policy|emitted|forbidden|required|slot|slots|schema|hash|hashes|ref|refs|"
    r"class|status|proof|reason|contract|request|count|scan|stage|artifact)",
    re.I,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout:|stderr:|stack trace|"
    r"terminal output:|command output:|git clone\s+\S|git apply\s+\S|"
    r"curl\s+\S|bash -|sh -|python -c)\b",
    re.I | re.M,
)


def read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path, limit: int = MAX_INPUT_ROWS_PER_ARTIFACT) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path.name}:{line_number} is not a JSON object")
            rows.append(value)
            if len(rows) > limit:
                raise ValueError(f"{path.name}:stage12451_input_bound_exceeded")
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_hash(*parts: Any, n: int = 24) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def public_scan(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not ALLOWED_KEY_CONTEXT_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_public_leak:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(public_scan(f"{label}.{key}", child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(public_scan(f"{label}[{index}]", child))
    return issues


def target_request() -> tuple[dict[str, Any] | None, list[str]]:
    issues: list[str] = []
    schema = read_json(EXECUTOR_RETURN_SCHEMA)
    if schema.get("schema_name") != SCHEMA_NAME:
        issues.append("executor_return_schema_name_mismatch")
    requests = read_jsonl(ADAPTER_REQUESTS, limit=500)
    matches = [row for row in requests if row.get("execution_request_id_hash") == TARGET_REQUEST_HASH]
    if len(matches) != 1:
        issues.append("target_request_hash_binding_missing_or_duplicate")
        return None, sorted(set(issues))
    request = matches[0]
    expected_rel = str(TARGET_EXPECTED_RETURN.relative_to(ROOT))
    if request.get("adapter_request_id") != TARGET_ADAPTER_REQUEST_ID:
        issues.append("target_adapter_request_id_mismatch")
    if request.get("expected_return_schema") != SCHEMA_NAME:
        issues.append("target_expected_return_schema_mismatch")
    if request.get("expected_return_path") != expected_rel:
        issues.append("target_expected_return_path_mismatch")
    manifest = read_jsonl(EXPECTED_RETURN_MANIFEST, limit=500)
    manifest_matches = [
        row
        for row in manifest
        if row.get("execution_request_id_hash") == TARGET_REQUEST_HASH
        and row.get("expected_return_path") == expected_rel
    ]
    if len(manifest_matches) != 1:
        issues.append("target_manifest_binding_missing_or_duplicate")
    return request, sorted(set(issues))


def stage12445_row_gate(row: dict[str, Any]) -> tuple[bool, list[str]]:
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import build_stage12445_adapter_execution_return_ingest_and_level3_gate as stage12445

    schema = read_json(EXECUTOR_RETURN_SCHEMA)
    required_slots = [str(slot) for slot in schema.get("required_return_slots", [])]
    admission_slots = [str(slot) for slot in schema.get("admission_required_slots", [])]
    passed, reasons, _statuses = stage12445.row_gate(row, schema, required_slots, admission_slots)
    return passed, reasons


def allowed_return_keys() -> set[str]:
    schema = read_json(EXECUTOR_RETURN_SCHEMA)
    return {str(key) for key in schema.get("allowed_properties") or []}


def sanitize_candidate_return(row: dict[str, Any], request: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    allowed = allowed_return_keys()
    if not allowed:
        return None, ["executor_return_allowed_properties_missing"]
    candidate = {key: row[key] for key in sorted(allowed) if key in row}
    if not candidate:
        return None, ["input_row_has_no_stage12445_return_schema_fields"]
    if set(candidate) != set(row):
        return None, ["input_row_contains_non_return_schema_fields"]
    candidate["source_execution_request_id_hash"] = TARGET_REQUEST_HASH
    candidate["request_kind"] = str(request.get("request_kind") or "source_adapter_materialization")
    passed, reasons = stage12445_row_gate(candidate)
    if not passed:
        return None, reasons
    scan_issues = public_scan("return_row", candidate)
    if scan_issues:
        return None, scan_issues
    return candidate, []


def candidate_identity(row: dict[str, Any], input_stage: str) -> tuple[str, str, str]:
    root = str(row.get("root_id") or row.get("candidate_id") or stable_hash("row", row))
    repo = str(row.get("repo_family") or "unknown")
    language = str(row.get("language_family") or row.get("language") or "unknown")
    return input_stage, language, stable_hash("candidate", input_stage, language, repo, root)


def load_scout_candidates() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    artifact_status: dict[str, Any] = {}
    total_rows = 0
    for input_stage, path in SCOUT_INPUTS.items():
        rows = read_jsonl(path)
        total_rows += len(rows)
        artifact_status[input_stage] = {
            "input_artifact_status": "present" if path.exists() else "missing",
            "input_artifact_sha256_24": file_hash(path),
            "input_row_count": len(rows),
        }
        for row in rows:
            grouped[candidate_identity(row, input_stage)].append(row)

    candidates: list[dict[str, Any]] = []
    for (input_stage, language, candidate_hash), rows in sorted(grouped.items()):
        semantic_counts = Counter(str(row.get("target_semantic_id") or "unknown") for row in rows)
        admission_status_counts = Counter(str(row.get("admission") or "unknown") for row in rows)
        candidates.append(
            {
                "candidate_hash": candidate_hash,
                "input_stage_class": input_stage,
                "language_family_class": language,
                "candidate_row_count": len(rows),
                "target_semantic_status_counts": dict(sorted(semantic_counts.items())),
                "admission_status_counts": dict(sorted(admission_status_counts.items())),
                "rows": rows,
            }
        )
    by_stage: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_stage[str(candidate["input_stage_class"])].append(candidate)
    bounded: list[dict[str, Any]] = []
    for stage_name in PRIMARY_SCOUT_STAGE_ORDER:
        for candidate in by_stage.get(stage_name, []):
            bounded.append(candidate)
            if len(bounded) >= MAX_SCOUTED_CANDIDATES:
                break
        if len(bounded) >= MAX_SCOUTED_CANDIDATES:
            break
    if len(bounded) < MAX_SCOUTED_CANDIDATES:
        for stage_name in FILL_SCOUT_STAGE_ORDER:
            for candidate in by_stage.get(stage_name, []):
                bounded.append(candidate)
                if len(bounded) >= MAX_SCOUTED_CANDIDATES:
                    break
            if len(bounded) >= MAX_SCOUTED_CANDIDATES:
                break
    status = {
        "input_artifact_status": artifact_status,
        "input_row_count": total_rows,
        "scouted_candidate_count": len(candidates),
        "bounded_candidate_count": len(bounded),
        "selection_policy": "primary_scout_artifacts_first_stage12143_fill_only_if_needed",
    }
    return bounded, status


def build_artifacts() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    request, binding_issues = target_request()
    candidates, input_status = load_scout_candidates()
    rows: list[dict[str, Any]] = []
    blocked_records: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter(binding_issues)
    language_counts: Counter[str] = Counter()

    if request:
        for candidate in candidates:
            language_counts[str(candidate["language_family_class"])] += 1
            candidate_rows = candidate.pop("rows")
            projected_for_candidate = False
            candidate_reasons: Counter[str] = Counter()
            for source_row in candidate_rows:
                projected, reasons = sanitize_candidate_return(source_row, request)
                if projected is not None:
                    rows.append(projected)
                    projected_for_candidate = True
                    break
                candidate_reasons.update(reasons)
            if not projected_for_candidate:
                candidate_reasons.update(
                    [
                        "input_artifact_train_support_only_not_level3",
                        "proof_slots_not_present_in_scout_rows",
                        "no_stage12445_row_gate_satisfying_row_without_fabrication",
                    ]
                )
                reason_counts.update(candidate_reasons)
                blocked_records.append(
                    {
                        "candidate_hash": candidate["candidate_hash"],
                        "input_stage_class": candidate["input_stage_class"],
                        "language_family_class": candidate["language_family_class"],
                        "projection_status": "blocked",
                        "candidate_row_count": candidate["candidate_row_count"],
                        "target_semantic_status_counts": candidate["target_semantic_status_counts"],
                        "admission_status_counts": candidate["admission_status_counts"],
                        "reason_codes": sorted(candidate_reasons),
                    }
                )
            if len(rows) >= MAX_PROJECTED_ROWS:
                break
    else:
        for candidate in candidates:
            reason_counts.update(binding_issues)
            blocked_records.append(
                {
                    "candidate_hash": candidate["candidate_hash"],
                    "input_stage_class": candidate["input_stage_class"],
                    "language_family_class": candidate["language_family_class"],
                    "projection_status": "blocked",
                    "candidate_row_count": candidate["candidate_row_count"],
                    "target_semantic_status_counts": candidate["target_semantic_status_counts"],
                    "admission_status_counts": candidate["admission_status_counts"],
                    "reason_codes": binding_issues,
                }
            )

    output_scan_issues = public_scan("projected_return_rows", rows)
    output_scan_issues.extend(public_scan("blocked_records", blocked_records))
    if output_scan_issues:
        reason_counts.update(output_scan_issues)
        rows = []

    if rows and not output_scan_issues:
        decision = "projected_stage12445_satisfying_selected_test_return_rows"
    elif output_scan_issues:
        decision = "blocked_public_safety_scan_failed_no_return_rows"
    else:
        decision = "blocked_no_stage12445_satisfying_selected_test_rows_no_return_rows"

    blocked_artifact = {
        "stage": STAGE,
        "record_type": "stage12451_blocked_projection_records_public_safe_v1",
        "decision": decision,
        **ZERO_AUTHORITY,
        "blocked_record_count": len(blocked_records),
        "blocked_records": blocked_records,
        "reason_code_counts": dict(sorted(reason_counts.items())),
        "guardrail_scan_passed": not output_scan_issues,
        "raw_leak_count": len({item for item in output_scan_issues if "raw_public_leak" in item or "forbidden_public_key" in item}),
    }
    summary = {
        "stage": STAGE,
        "record_type": "selected_test_transition_return_projection_public_safe_v1",
        "decision": decision,
        **ZERO_AUTHORITY,
        "target_request_hash": TARGET_REQUEST_HASH,
        "target_adapter_request_id_hash": stable_hash("adapter_request_id", TARGET_ADAPTER_REQUEST_ID),
        "target_expected_return_file_hash": stable_hash(
            "expected_return_file",
            str(TARGET_EXPECTED_RETURN.relative_to(ROOT)),
        ),
        "bounds": {
            "max_input_rows_per_artifact": MAX_INPUT_ROWS_PER_ARTIFACT,
            "max_scouted_candidates": MAX_SCOUTED_CANDIDATES,
            "max_projected_rows": MAX_PROJECTED_ROWS,
        },
        "input_status": input_status,
        "source_record_count": input_status["input_row_count"],
        "scouted_candidate_count": input_status["scouted_candidate_count"],
        "bounded_candidate_count": input_status["bounded_candidate_count"],
        "bounded_language_family_class_counts": dict(sorted(language_counts.items())),
        "projected_return_row_count": len(rows),
        "blocked_record_count": len(blocked_records),
        "stage12445_request_binding_status": "pass" if request and not binding_issues else "blocked",
        "proof_issue_counts": dict(sorted(reason_counts.items())),
        "return_file_written_status": "written" if rows else "written_empty_blocked",
        "public_value_policy": "hash_status_class_only_no_raw_paths_commands_output_source_diffs_urls",
        "claim_boundary": "Stage12451 only projects already proof-complete scout rows into the Stage12445 return slot; it emits no training rows and grants no admission.",
        "guardrail_scan": {
            "scan_passed": not output_scan_issues,
            "issue_count": len(set(output_scan_issues)),
            "issues": sorted(set(output_scan_issues)),
            "raw_leak_count": len({item for item in output_scan_issues if "raw_public_leak" in item or "forbidden_public_key" in item}),
        },
        "guardrail_scan_passed": not output_scan_issues,
        "raw_leak_count": len({item for item in output_scan_issues if "raw_public_leak" in item or "forbidden_public_key" in item}),
        "schema_issue_count": len(binding_issues),
        "summary_hash": "pending",
    }
    summary["summary_hash"] = stable_hash({key: value for key, value in summary.items() if key != "summary_hash"})
    return summary, rows, blocked_artifact


def main() -> None:
    summary, rows, blocked_artifact = build_artifacts()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", summary)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    write_json(OUT / "blocked_artifact.json", blocked_artifact)
    write_jsonl(TARGET_EXPECTED_RETURN, rows)
    print(
        json.dumps(
            {
                "stage": summary["stage"],
                "decision": summary["decision"],
                "bounded_candidate_count": summary["bounded_candidate_count"],
                "projected_return_row_count": summary["projected_return_row_count"],
                "blocked_record_count": summary["blocked_record_count"],
                "return_file_written_status": summary["return_file_written_status"],
                "training_allowed": summary["training_allowed"],
                "admission_allowed": summary["admission_allowed"],
                "guardrail_scan_passed": summary["guardrail_scan"]["scan_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
