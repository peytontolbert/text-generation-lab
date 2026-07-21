#!/usr/bin/env python3
"""Materialize Stage12503 private semantic extraction returns or block.

Stage12511 is the safe bridge after Stage12510. It reads an optional private
return-candidate file, sanitizes rows to the Stage12503 authoritative return
schema, validates them against Stage12502 requests, and atomically writes the
official Stage12503 input return file only when every candidate is valid.

It does not execute ai_env, inspect raw source, admit rows, emit policy labels,
materialize Level-3 atoms, produce patch traces, or train.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12511_stage12503_private_return_candidate_ingest"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12502 = "stage12502_authoritative_private_semantic_extraction_request_preflight"
STAGE12502_OUT = ROOT / "runs/local/artifacts" / STAGE12502
REQUESTS = STAGE12502_OUT / "private_semantic_extraction_requests.jsonl"
OFFICIAL_RETURN_FILE = STAGE12502_OUT / "private_semantic_extraction_returns.jsonl"

STAGE12510 = "stage12510_ai_env_private_extraction_executor_readiness_audit"
PRIVATE_CANDIDATES = ROOT / "runs/local/artifacts" / STAGE12510 / "private_semantic_extraction_return_candidates.jsonl"
STAGE12503_SCRIPT = ROOT / "scripts/build_stage12503_private_semantic_extraction_return_validator.py"
RETURN_RECORD_TYPE = "stage12503_authoritative_private_semantic_extraction_return_v1"
OPTIONAL_RETURN_FIELDS = ["patch_apply_status_enum", "stop_continue_status_enum"]

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output|commit:)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)
FALSE_GUARDS = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
    "policy_label_materialized": False,
    "level3_atom_materialized": False,
    "patch_trace_materialized": False,
    "raw_source_inspected": False,
    "extraction_run": False,
}
ZERO_GUARDS = {
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level3_atom_count": 0,
    "patch_trace_admitted": 0,
    "patch_trace_rows": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
}


class RawLeakError(ValueError):
    pass


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
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


def atomic_write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    write_jsonl(tmp, rows)
    tmp.replace(path)


def scan_raw_leaks(value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(stable_hash(value))
    elif isinstance(value, dict):
        for child in value.values():
            issues.extend(scan_raw_leaks(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan_raw_leaks(child))
    return issues


def enforce_no_raw_leaks(value: Any) -> None:
    issues = scan_raw_leaks(value)
    if issues:
        raise RawLeakError(f"stage12511 raw leak guard rejected {len(issues)} public field(s)")


def load_stage12503() -> Any:
    spec = importlib.util.spec_from_file_location("stage12503_validator", STAGE12503_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("stage12503 validator import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sanitize_candidate(row: dict[str, Any], required_fields: list[str]) -> dict[str, Any]:
    allowed = set(required_fields) | set(OPTIONAL_RETURN_FIELDS)
    sanitized = {key: row.get(key) for key in sorted(allowed) if key in row}
    sanitized["record_type"] = row.get("record_type")
    sanitized["raw_private_values_revealed"] = False
    sanitized["raw_source_output_included"] = False
    sanitized["local_model_authority"] = False
    sanitized["policy_label_emitted"] = False
    sanitized["training_allowed"] = False
    sanitized["admission_allowed"] = False
    sanitized["training_rows_emitted"] = 0
    sanitized["admitted_rows"] = 0
    return sanitized


def rejection_record(row: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    public = {
        "record_type": "stage12511_rejected_private_semantic_extraction_return_candidate_v1",
        "rejected_candidate_id_hash": stable_hash({"request": row.get("request_id_hash"), "reasons": reasons}),
        "request_id_hash": row.get("request_id_hash"),
        "audit_item_id_hash": row.get("audit_item_id_hash"),
        "work_item_id_hash": row.get("work_item_id_hash"),
        "packet_id_hash": row.get("packet_id_hash"),
        "root_or_window_hash": row.get("root_or_window_hash"),
        "source_stage": row.get("source_stage"),
        "source_kind": row.get("source_kind"),
        "task_family": row.get("task_family"),
        "language_family": row.get("language_family"),
        "rejection_codes": sorted(set(reasons)),
        "public_safe_status_only": True,
        "raw_private_values_revealed": False,
        "raw_source_output_included": False,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(public)
    return public


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    out.mkdir(parents=True, exist_ok=True)
    stage12503 = load_stage12503()
    requests = read_jsonl(root / "runs/local/artifacts" / STAGE12502 / "private_semantic_extraction_requests.jsonl")
    request_by_id = {row.get("request_id_hash"): row for row in requests if row.get("request_id_hash")}
    candidates_path = root / "runs/local/artifacts" / STAGE12510 / "private_semantic_extraction_return_candidates.jsonl"
    candidates = read_jsonl(candidates_path)

    valid_returns: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    blocker_counts: Counter[str] = Counter()
    if not candidates:
        blocker_counts["private_semantic_extraction_return_candidates_missing"] += len(requests) or 1

    for candidate in candidates:
        sanitized = sanitize_candidate(candidate, stage12503.REQUIRED_RETURN_FIELDS)
        request = request_by_id.get(sanitized.get("request_id_hash"))
        reasons = stage12503.validate_return(sanitized, request)
        if reasons:
            blocker_counts.update(reasons)
            rejected.append(rejection_record(sanitized, reasons))
        else:
            enforce_no_raw_leaks(sanitized)
            valid_returns.append(sanitized)

    all_candidates_valid = bool(candidates) and len(valid_returns) == len(candidates) and not rejected
    official_return_file = root / "runs/local/artifacts" / STAGE12502 / "private_semantic_extraction_returns.jsonl"
    records_written = 0
    if all_candidates_valid:
        atomic_write_jsonl(official_return_file, valid_returns)
        records_written = len(valid_returns)

    language_counts = Counter(row.get("language_family") for row in [*valid_returns, *rejected])
    task_counts = Counter(row.get("task_family") for row in [*valid_returns, *rejected])
    contract = {
        "record_type": "stage12511_private_return_candidate_ingest_contract_v1",
        "stage": STAGE,
        "input_stage": STAGE12510,
        "input_candidate_file_role": "private_semantic_extraction_return_candidates.jsonl",
        "official_return_file_stage": STAGE12502,
        "official_return_file_role": "private_semantic_extraction_returns.jsonl",
        "return_record_type": RETURN_RECORD_TYPE,
        "writes_official_return_file_only_when_all_candidates_validate": True,
        "public_artifact_policy": "hashes_enums_status_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        "claim_boundary": "Private return candidate ingest only. Not execution, proof admission, policy labeling, Level-3 materialization, patch trace, or training.",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail = {"stage": STAGE, "scan_passed": True, "raw_leak_count": 0, "raw_leak_issue_hashes": []}
    decision = (
        "stage12503_private_return_file_written_from_validated_private_candidates_training_and_admission_blocked"
        if records_written
        else "blocked_private_semantic_extraction_return_candidates_missing_or_invalid_no_returns_written"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12511_private_return_candidate_ingest_summary_v1",
        "decision": decision,
        "claim_boundary": "Stage12511 only ingests private return candidates. It does not execute ai_env, inspect raw source, admit rows, emit policy labels, materialize Level-3 atoms, produce patch traces, or train.",
        "request_count": len(requests),
        "candidate_return_count": len(candidates),
        "valid_candidate_return_count": len(valid_returns),
        "rejected_candidate_return_count": len(rejected),
        "all_candidates_valid": all_candidates_valid,
        "stage12503_return_file_written": bool(records_written),
        "stage12503_return_records_written": records_written,
        "blocker_code_counts": dict(sorted(blocker_counts.items())),
        "language_counts": dict(sorted((str(k), v) for k, v in language_counts.items())),
        "task_family_counts": dict(sorted((str(k), v) for k, v in task_counts.items())),
        "next_stage": "rerun_stage12503_private_semantic_extraction_return_validator" if records_written else "produce_authoritative_private_return_candidates_from_trusted_ai_env_extractor_then_rerun_stage12511",
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks({"contract": contract, "guardrail": guardrail, "summary": summary, "rejected": rejected})
    write_jsonl(out / "rejected_private_semantic_extraction_return_candidates.jsonl", rejected)
    write_json(out / "private_return_candidate_ingest_contract.json", contract)
    write_json(out / "guardrail_scan.json", guardrail)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()
