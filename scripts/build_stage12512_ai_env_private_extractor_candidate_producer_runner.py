#!/usr/bin/env python3
"""Run or block a trusted ai_env private semantic extraction candidate producer.

Stage12512 is the execution boundary after Stage12510/12511. It may invoke an
explicitly configured local extractor script that writes Stage12511 candidate
returns. It never writes the official Stage12503 return file, never admits rows,
and never persists raw extractor output.

Default production state is fail-closed because no trusted extractor script is
configured.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12512_ai_env_private_extractor_candidate_producer_runner"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12502 = "stage12502_authoritative_private_semantic_extraction_request_preflight"
REQUESTS = ROOT / "runs/local/artifacts" / STAGE12502 / "private_semantic_extraction_requests.jsonl"
STAGE12509 = "stage12509_ai_env_private_extraction_return_work_order"
WORK_ORDERS = ROOT / "runs/local/artifacts" / STAGE12509 / "ai_env_private_extraction_return_work_orders.jsonl"
STAGE12510 = "stage12510_ai_env_private_extraction_executor_readiness_audit"
CANDIDATE_OUTPUT = ROOT / "runs/local/artifacts" / STAGE12510 / "private_semantic_extraction_return_candidates.jsonl"
OFFICIAL_RETURN_FILE = ROOT / "runs/local/artifacts" / STAGE12502 / "private_semantic_extraction_returns.jsonl"

EXTRACTOR_SCRIPT_ENV = "STAGE12512_AI_ENV_PRIVATE_EXTRACTOR_SCRIPT"
RETURN_RECORD_TYPE = "stage12503_authoritative_private_semantic_extraction_return_v1"

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
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
    "policy_label_materialized": False,
    "level3_atom_materialized": False,
    "patch_trace_materialized": False,
    "raw_source_inspected_by_stage": False,
    "stage12503_return_file_written": False,
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
    "stage12503_return_records_written": 0,
}


class RawLeakError(ValueError):
    pass


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


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
        raise RawLeakError(f"stage12512 raw leak guard rejected {len(issues)} public field(s)")


def configured_extractor(root: Path) -> dict[str, Any]:
    configured = os.environ.get(EXTRACTOR_SCRIPT_ENV, "").strip()
    if not configured:
        return {
            "configured": False,
            "script_ref_hash": None,
            "script_present": False,
            "blocker_codes": ["trusted_ai_env_private_extractor_script_missing"],
        }
    path = Path(configured)
    if not path.is_absolute():
        path = root / path
    return {
        "configured": True,
        "script_ref_hash": stable_hash(str(path)),
        "script_present": path.exists() and path.is_file(),
        "script_path_private": str(path),
        "blocker_codes": [] if path.exists() and path.is_file() else ["configured_extractor_script_file_missing"],
    }


def candidate_file_status(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    record_types = Counter(str(row.get("record_type")) for row in rows)
    return {
        "candidate_output_file_present": path.exists(),
        "candidate_output_row_count": len(rows),
        "candidate_output_sha256_24": file_hash(path),
        "candidate_output_record_type_counts": dict(sorted(record_types.items())),
    }


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    out.mkdir(parents=True, exist_ok=True)
    work_orders = read_jsonl(root / "runs/local/artifacts" / STAGE12509 / "ai_env_private_extraction_return_work_orders.jsonl")
    requests = read_jsonl(root / "runs/local/artifacts" / STAGE12502 / "private_semantic_extraction_requests.jsonl")
    extractor = configured_extractor(root)
    blocker_counts: Counter[str] = Counter()
    blocker_rows: list[dict[str, Any]] = []
    execution_performed = False
    candidate_records_written = 0
    subprocess_returncode: int | None = None

    if not work_orders:
        blocker_counts["stage12509_work_orders_missing"] += 1
    if not requests:
        blocker_counts["stage12502_requests_missing"] += 1
    for code in extractor["blocker_codes"]:
        blocker_counts[code] += len(work_orders) or 1

    if work_orders and requests and extractor["configured"] and extractor["script_present"]:
        candidate_output = root / "runs/local/artifacts" / STAGE12510 / "private_semantic_extraction_return_candidates.jsonl"
        candidate_output.parent.mkdir(parents=True, exist_ok=True)
        if candidate_output.exists():
            candidate_output.unlink()
        tmp_output = candidate_output.with_suffix(candidate_output.suffix + ".tmp")
        if tmp_output.exists():
            tmp_output.unlink()
        cmd = [
            sys.executable,
            extractor["script_path_private"],
            "--work-orders-jsonl",
            str(root / "runs/local/artifacts" / STAGE12509 / "ai_env_private_extraction_return_work_orders.jsonl"),
            "--requests-jsonl",
            str(root / "runs/local/artifacts" / STAGE12502 / "private_semantic_extraction_requests.jsonl"),
            "--candidate-output-jsonl",
            str(tmp_output),
        ]
        result = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        execution_performed = True
        subprocess_returncode = result.returncode
        if result.returncode != 0:
            blocker_counts["trusted_extractor_script_nonzero_exit"] += len(work_orders)
        elif not tmp_output.exists():
            blocker_counts["trusted_extractor_candidate_output_missing"] += len(work_orders)
        else:
            rows = read_jsonl(tmp_output)
            if not rows:
                blocker_counts["trusted_extractor_candidate_output_empty"] += len(work_orders)
            elif any(row.get("record_type") != RETURN_RECORD_TYPE for row in rows):
                blocker_counts["trusted_extractor_candidate_record_type_invalid"] += len(rows)
            else:
                candidate_output.parent.mkdir(parents=True, exist_ok=True)
                tmp_output.replace(candidate_output)
                candidate_records_written = len(rows)
            if tmp_output.exists():
                tmp_output.unlink()

    if blocker_counts:
        for work_order in work_orders or [{}]:
            row = {
                "record_type": "stage12512_private_extractor_candidate_producer_blocker_v1",
                "blocker_id_hash": stable_hash({"work_order": work_order.get("work_order_id_hash"), "blockers": sorted(blocker_counts)}),
                "work_order_id_hash": work_order.get("work_order_id_hash"),
                "request_id_hash": work_order.get("request_id_hash"),
                "source_stage": work_order.get("source_stage"),
                "task_family": work_order.get("task_family"),
                "language_family": work_order.get("language_family"),
                "blocker_codes": sorted(blocker_counts),
                "public_safe_status_only": True,
                "raw_private_values_revealed": False,
                "raw_source_output_included": False,
                **FALSE_GUARDS,
                **ZERO_GUARDS,
            }
            enforce_no_raw_leaks(row)
            blocker_rows.append(row)

    cand_path = root / "runs/local/artifacts" / STAGE12510 / "private_semantic_extraction_return_candidates.jsonl"
    cand_status = candidate_file_status(cand_path)
    contract = {
        "record_type": "stage12512_private_extractor_candidate_producer_runner_contract_v1",
        "stage": STAGE,
        "input_stage": STAGE12509,
        "candidate_output_stage": STAGE12510,
        "candidate_output_file_role": "private_semantic_extraction_return_candidates.jsonl",
        "extractor_script_env": EXTRACTOR_SCRIPT_ENV,
        "extractor_invocation_argv_contract": [
            "python",
            "<extractor_script>",
            "--work-orders-jsonl",
            "<stage12509_work_orders>",
            "--requests-jsonl",
            "<stage12502_requests>",
            "--candidate-output-jsonl",
            "<stage12510_candidate_output_tmp>",
        ],
        "stage12512_never_writes_official_stage12503_return_file": True,
        "next_validator_stage": "stage12511_stage12503_private_return_candidate_ingest",
        "public_artifact_policy": "hashes_enums_status_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    decision = (
        "trusted_ai_env_private_extractor_candidate_file_written_rerun_stage12511"
        if candidate_records_written and not blocker_counts
        else "blocked_trusted_ai_env_private_extractor_not_ready_no_candidate_returns_written"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12512_private_extractor_candidate_producer_runner_summary_v1",
        "decision": decision,
        "claim_boundary": "Candidate producer runner only. Stage12512 never writes Stage12503 official returns, never admits rows, never emits policy labels or Level-3 atoms, and never trains.",
        "input_work_order_count": len(work_orders),
        "input_request_count": len(requests),
        "extractor_configured": extractor["configured"],
        "extractor_script_present": extractor["script_present"],
        "extractor_script_ref_hash": extractor["script_ref_hash"],
        "execution_performed_by_stage": execution_performed,
        "subprocess_returncode": subprocess_returncode,
        "candidate_return_records_written": candidate_records_written,
        "candidate_output_file_present": cand_status["candidate_output_file_present"],
        "candidate_output_row_count": cand_status["candidate_output_row_count"],
        "candidate_output_sha256_24": cand_status["candidate_output_sha256_24"],
        "candidate_output_record_type_counts": cand_status["candidate_output_record_type_counts"],
        "stage12503_return_file_present": (root / "runs/local/artifacts" / STAGE12502 / "private_semantic_extraction_returns.jsonl").exists(),
        "stage12503_return_file_written": False,
        "stage12503_return_records_written": 0,
        "blocker_code_counts": dict(sorted(blocker_counts.items())),
        "next_stage": "rerun_stage12511_then_stage12503" if candidate_records_written and not blocker_counts else "configure_trusted_ai_env_private_extractor_script_then_rerun_stage12512",
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        **{k: v for k, v in FALSE_GUARDS.items() if k != "execution_performed_by_stage"},
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks({"contract": contract, "summary": summary, "blockers": blocker_rows})
    write_jsonl(out / "private_extractor_candidate_producer_blockers.jsonl", blocker_rows)
    write_json(out / "private_extractor_candidate_producer_runner_contract.json", contract)
    write_json(out / "guardrail_scan.json", {"stage": STAGE, "scan_passed": True, "raw_leak_count": 0, "raw_leak_issue_hashes": []})
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()
