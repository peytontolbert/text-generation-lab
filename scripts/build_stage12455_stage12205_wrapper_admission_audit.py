#!/usr/bin/env python3
"""Audit Stage12454 appended Stage12205 return rows.

This stage is deterministic QC. It does not remove rows or train; it classifies
which admitted Stage12445 candidates are clean verifier observations, controlled
FAIL_TO_PASS support, or require quarantine before packaging.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12455_stage12205_wrapper_admission_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
RETURN_FILE = ROOT / "runs/local/artifacts/stage12445_adapter_execution_return_ingest_and_level3_gate/returns/selected_test_transition_root_batch_non_web_first.return.jsonl"
S54 = ROOT / "runs/summaries/stage12454_stage12205_nonweb_authoritative_log_return_append.json"
S45 = ROOT / "runs/summaries/stage12445_adapter_execution_return_ingest_and_level3_gate.json"
S50 = ROOT / "runs/summaries/stage12450_post_stage12449_level3_supply_control_board.json"

ZERO = {"training_allowed": False, "admission_allowed": False, "execution_allowed": False, "emitted_training_rows": 0, "sealed_eval_rows_emitted": 0}
FORBIDDEN_PUBLIC_KEYS = {"path", "paths", "url", "urls", "uri", "command", "command_text", "commands", "stdout", "stderr", "output", "outputs", "diff", "patch", "patch_body", "source", "source_path", "source_text", "private_locator", "raw", "raw_text", "trace", "trace_text", "issue_body"}
ALLOWED_KEY_CONTEXT_RE = re.compile(r"(policy|emitted|forbidden|required|slot|slots|schema|hash|hashes|ref|refs|class|status|proof|reason|contract|request|count|scan|supply|stage|artifact|lane)", re.I)
RAW_LEAK_RE = re.compile(r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|\b(?:stdout:|stderr:|terminal output:|command output:|git clone\s+\S|git apply\s+\S|python -c|bash -)\b", re.I | re.M)
PLACEHOLDER_PROOFS = {"proven", "pass", "passed", "clear", "valid"}
CONTROLLED_FTP_REASONS = {
    "controlled_fixture_fail_to_pass_transition_train_support_only_not_general_repair_claim",
    "no_patch_authoritative_fail_to_pass_transition_observation_no_repair_claim",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode()).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def scan(label: str, value: Any) -> list[str]:
    issues = []
    leaf = label.rsplit('.', 1)[-1].split('[', 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not ALLOWED_KEY_CONTEXT_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_public_leak:{stable_hash(value)}")
    elif isinstance(value, dict):
        for k, v in value.items():
            issues.extend(scan(f"{label}.{k}", v))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            issues.extend(scan(f"{label}[{i}]", v))
    return issues


def classify(row: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    source = row.get("source_stage")
    status = row.get("observation_status_class")
    patch_reason = row.get("patch_application_or_no_patch_reason")
    if row.get("training_eligible") is not False or row.get("strict_eval_eligible") is not False:
        reasons.append("training_or_eval_flag_not_false")
    if row.get("source_execution_request_id_hash") != "ac183215a709860587488958":
        reasons.append("wrong_request_binding")
    if row.get("language_family") == "web_js_ts_html":
        reasons.append("web_row_in_nonweb_return")
    if source == "stage12205_authoritative_verifier_log_level3_joiner" and row.get("language_family") not in {"python", "rust", "c_cpp"}:
        reasons.append("stage12205_nonweb_language_violation")
    if status == "FAIL_TO_PASS":
        if patch_reason not in CONTROLLED_FTP_REASONS:
            reasons.append("fail_to_pass_reason_not_controlled_or_no_repair_claim")
        reason_text = str(patch_reason).lower()
        allowed_no_claim_markers = ("no_repair_claim", "not_general_repair_claim")
        if "external" in reason_text or ("repair_claim" in reason_text and not any(marker in reason_text for marker in allowed_no_claim_markers)):
            reasons.append("fail_to_pass_external_or_repair_overclaim")
        return ("controlled_or_mutation_fail_to_pass_transition_support", reasons)
    if status in {"PASS_CURRENT_STATE", "PASS_TO_PASS", "PASS_CURRENT_BUILD_AND_RUN", "PASS_CURRENT_BUILD", "FAIL_CURRENT_STATE", "ENV_BLOCKED"}:
        return ("verifier_observation_transition_support", reasons)
    reasons.append("unknown_observation_status")
    return ("quarantine_unknown_status", reasons)


def main() -> None:
    rows = read_jsonl(RETURN_FILE)
    s54 = read_json(S54)
    s45 = read_json(S45)
    s50 = read_json(S50)
    records = []
    class_counts = Counter()
    issue_counts = Counter()
    source_counts = Counter()
    lang_counts = Counter()
    status_counts = Counter()
    proof_placeholder_counts = Counter()
    seen_hashes = set()
    duplicate_count = 0
    for idx, row in enumerate(rows, 1):
        row_hash = row.get("return_row_hash") or stable_hash(row)
        if row_hash in seen_hashes:
            duplicate_count += 1
        seen_hashes.add(row_hash)
        cls, issues = classify(row)
        class_counts[cls] += 1
        issue_counts.update(issues)
        source_counts[str(row.get("source_stage"))] += 1
        lang_counts[str(row.get("language_family"))] += 1
        status_counts[str(row.get("observation_status_class"))] += 1
        for proof_key in ["same_source_lineage_proof", "verifier_relevance_proof", "causal_verifier_linkage", "policy_label_independence_proof"]:
            if str(row.get(proof_key)).strip().lower() in PLACEHOLDER_PROOFS:
                proof_placeholder_counts[proof_key] += 1
        records.append({
            "row_ref_hash": stable_hash([idx, row_hash]),
            "source_stage": row.get("source_stage"),
            "language_family": row.get("language_family"),
            "observation_status_class": row.get("observation_status_class"),
            "classification": cls,
            "issue_codes": sorted(issues),
        })
    # Placeholder proof strings are allowed for Stage12445 schema admission, but block packaging until expanded.
    packaging_blockers = Counter(issue_counts)
    if proof_placeholder_counts:
        packaging_blockers["placeholder_style_proof_strings_require_stage12456_or_raw_private_audit_before_training_packaging"] = sum(proof_placeholder_counts.values())
    if duplicate_count:
        packaging_blockers["duplicate_return_row_hash"] = duplicate_count
    if int(s50.get("external_fail_to_pass_validated_delta") or 0) != 0:
        packaging_blockers["external_fail_to_pass_delta_should_remain_zero"] += 1
    clean_for_stage12445_only = not issue_counts and duplicate_count == 0 and s45.get("level3_candidate_count") == len(rows)
    packaging_allowed = False
    artifact = {
        "stage": STAGE,
        "record_type": "stage12205_wrapper_admission_audit_v1",
        "decision": "stage12445_schema_admission_preserved_but_training_packaging_blocked_pending_proof_depth_audit" if clean_for_stage12445_only else "stage12445_return_rows_require_quarantine_or_repair_before_further_use",
        **ZERO,
        "return_row_count": len(rows),
        "stage12452_prior_rows_expected": 15,
        "stage12454_appended_rows_reported": s54.get("appended_return_row_count"),
        "stage12445_level3_candidate_count": s45.get("level3_candidate_count"),
        "stage12450_external_fail_to_pass_validated_delta": s50.get("external_fail_to_pass_validated_delta"),
        "classification_counts": dict(sorted(class_counts.items())),
        "source_stage_counts": dict(sorted(source_counts.items())),
        "language_counts": dict(sorted(lang_counts.items())),
        "observation_status_counts": dict(sorted(status_counts.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        "proof_placeholder_counts": dict(sorted(proof_placeholder_counts.items())),
        "packaging_blocker_counts": dict(sorted(packaging_blockers.items())),
        "training_packaging_allowed": packaging_allowed,
        "external_repair_credit_allowed": False,
        "claim_boundary": "Rows may remain Stage12445 Level-3 verifier-observation candidates only. They are not training rows, not strict eval rows, and not external comparable repair/FAIL_TO_PASS floor credit.",
        "row_audit_records_path": "runs/local/artifacts/stage12455_stage12205_wrapper_admission_audit/row_audit_records.jsonl",
        "source_fingerprints": {
            "return_file_sha256_24": file_hash(RETURN_FILE),
            "stage12454_summary_sha256_24": file_hash(S54),
            "stage12445_summary_sha256_24": file_hash(S45),
            "stage12450_summary_sha256_24": file_hash(S50),
        },
        "guardrail_scan": {},
        "guardrail_scan_passed": False,
        "raw_leak_count": 0,
        "schema_issue_count": 0,
        "summary_hash": "pending",
    }
    issues = scan("artifact", artifact) + scan("row_audit_records", records)
    artifact["guardrail_scan"] = {
        "scan_passed": not issues,
        "issue_count": len(set(issues)),
        "issues": sorted(set(issues)),
        "raw_leak_count": len({i for i in issues if "raw_public_leak" in i or "forbidden_public_key" in i}),
        "scan_scope": "stage12455_public_safe_audit_artifacts",
    }
    artifact["guardrail_scan_passed"] = artifact["guardrail_scan"]["scan_passed"]
    artifact["raw_leak_count"] = artifact["guardrail_scan"]["raw_leak_count"]
    artifact["summary_hash"] = stable_hash({k: v for k, v in artifact.items() if k != "summary_hash"})
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    write_jsonl(OUT / "row_audit_records.jsonl", records)
    print(json.dumps({
        "stage": artifact["stage"],
        "decision": artifact["decision"],
        "return_row_count": artifact["return_row_count"],
        "classification_counts": artifact["classification_counts"],
        "packaging_blocker_counts": artifact["packaging_blocker_counts"],
        "training_packaging_allowed": artifact["training_packaging_allowed"],
        "external_repair_credit_allowed": artifact["external_repair_credit_allowed"],
        "guardrail_scan_passed": artifact["guardrail_scan_passed"],
        "raw_leak_count": artifact["raw_leak_count"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
