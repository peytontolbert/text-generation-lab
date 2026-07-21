#!/usr/bin/env python3
"""Build Stage12461 fail-closed private proof-slot return validator.

This is a control/validator stage for future Stage12460 private returns. It
does not run tests, apply patches, admit rows, emit training rows, or train.
Missing returns are a blocked zero-credit state, not an execution error.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12461_external_patch_effect_return_validator"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12460 = "stage12460_external_comparable_patch_effect_private_proof_slot_materialization_request"
REQUEST_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12460}.json"
RETURN_SCHEMA = ROOT / "runs/local/artifacts" / STAGE12460 / "private_proof_slot_return_schema.json"
RETURN_FILE = ROOT / "runs/local/artifacts" / STAGE12460 / "private_proof_slot_returns.jsonl"

ACCEPTED_INDEX = OUT_DIR / "accepted_return_ref_index.jsonl"
CONTRACT_OUT = OUT_DIR / "validator_contract.json"

EXPECTED_GAP = 15
PASS_SLOT_VALUES = {"present"}
FAIL_STATUS_VALUES = {"fail", "failed", "failing"}
PASS_STATUS_VALUES = {"pass", "passed", "passing"}

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:stdout|stderr|traceback|command output|terminal output|git clone|"
    r"git apply|pytest\s|python -c|bash -|sh -|curl\s)\b",
    re.IGNORECASE | re.MULTILINE,
)
FORBIDDEN_PUBLIC_KEYS = {
    "path",
    "paths",
    "url",
    "urls",
    "uri",
    "command",
    "commands",
    "stdout",
    "stderr",
    "diff",
    "patch",
    "patch_body",
    "raw_text",
    "source",
    "source_text",
    "file_content",
    "content",
}
KEY_ALLOW_RE = re.compile(r"(hash|hashes|lineage|policy|slot|slots|blocker|scan)", re.IGNORECASE)


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


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def read_jsonl_lenient(path: Path) -> tuple[list[tuple[int, dict[str, Any]]], Counter[str]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    rejected: Counter[str] = Counter()
    if not path.exists():
        return rows, rejected
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                rejected["schema_invalid_json"] += 1
                continue
            if not isinstance(value, dict):
                rejected["schema_invalid_not_object"] += 1
                continue
            rows.append((line_no, value))
    return rows, rejected


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def normalized(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value or "").strip().lower().replace("-", "_")


def status_value(row: dict[str, Any], names: list[str]) -> str:
    statuses = row.get("slot_statuses") if isinstance(row.get("slot_statuses"), dict) else {}
    for name in names:
        direct = row.get(name)
        if direct is not None:
            return normalized(direct)
        slot = statuses.get(name)
        if slot is not None:
            return normalized(slot)
    return ""


def public_scan(value: Any, label: str = "return_row") -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not KEY_ALLOW_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_content_pattern:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(public_scan(child, f"{label}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(public_scan(child, f"{label}[{index}]"))
    return issues


def slot_passes(slot_statuses: dict[str, Any], slot: str) -> bool:
    return normalized(slot_statuses.get(slot)) in PASS_SLOT_VALUES


def any_slot_passes(slot_statuses: dict[str, Any], slots: list[str]) -> bool:
    return any(slot_passes(slot_statuses, slot) for slot in slots)


def validate_return_row(
    row: dict[str, Any],
    required_fields: list[str],
    required_slots: list[str],
) -> tuple[bool, list[str], list[str]]:
    reasons: list[str] = []
    scan_issues = public_scan(row)

    for field in required_fields:
        if field not in row:
            reasons.append(f"missing_required_field:{field}")

    if row.get("proof_complete") is not True:
        reasons.append("proof_complete_not_true")

    blocker_codes = row.get("blocker_codes")
    if not isinstance(blocker_codes, list):
        reasons.append("blocker_codes_not_list")
    elif blocker_codes:
        reasons.append("blocker_codes_present")

    if row.get("anti_leak_pass") is not True:
        reasons.append("anti_leak_pass_not_true")

    for flag in [
        "external_repair_credit_after_return_allowed",
        "training_after_return_allowed",
        "admission_after_return_allowed",
    ]:
        if row.get(flag) is not False:
            reasons.append(f"{flag}_not_false")

    slot_statuses = row.get("slot_statuses")
    if not isinstance(slot_statuses, dict):
        reasons.append("slot_statuses_not_object")
        slot_statuses = {}

    slot_hashes = row.get("slot_hashes")
    if not isinstance(slot_hashes, dict):
        reasons.append("slot_hashes_not_object")
        slot_hashes = {}

    for slot in required_slots:
        if slot not in slot_statuses:
            reasons.append(f"required_slot_missing:{slot}")
        elif not slot_passes(slot_statuses, slot):
            reasons.append(f"required_slot_not_present:{slot}")
        slot_hash = slot_hashes.get(slot)
        if not isinstance(slot_hash, str) or not slot_hash.strip():
            reasons.append(f"required_slot_hash_missing:{slot}")
        elif normalized(slot_hash) in {"unknown", "claimed", "claimed_only", "n/a", "none", "placeholder", "todo", "tbd", "true", "yes", "pass", "ok"}:
            reasons.append(f"required_slot_hash_placeholder:{slot}")

    buggy_status = status_value(
        row,
        [
            "buggy_verifier_status",
            "before_verifier_status",
            "buggy_verifier_fail",
            "before_verifier_fail",
        ],
    )
    fixed_status = status_value(
        row,
        [
            "fixed_verifier_status",
            "after_verifier_status",
            "before_plus_patch_verifier_status",
            "fixed_or_before_plus_patch_verifier_pass",
            "after_or_before_plus_patch_verifier_pass",
        ],
    )
    buggy_fail_slots = ["buggy_verifier_fail", "before_verifier_fail"]
    fixed_pass_slots = [
        "fixed_or_before_plus_patch_verifier_pass",
        "after_or_before_plus_patch_verifier_pass",
    ]
    if buggy_status not in FAIL_STATUS_VALUES and not any_slot_passes(slot_statuses, buggy_fail_slots):
        reasons.append("buggy_verifier_status_not_fail")
    if fixed_status not in PASS_STATUS_VALUES and not any_slot_passes(slot_statuses, fixed_pass_slots):
        reasons.append("fixed_or_before_plus_patch_status_not_pass")

    for slot, reason in [
        ("exact_same_verifier_identity", "exact_same_verifier_identity_not_proven"),
        ("patch_diff_apply_lineage", "patch_diff_apply_lineage_not_proven"),
        ("ordered_patch_effect_causality", "ordered_patch_effect_causality_not_proven"),
    ]:
        if not slot_passes(slot_statuses, slot) and normalized(row.get(slot)) not in PASS_SLOT_VALUES:
            reasons.append(reason)

    if scan_issues:
        reasons.append("public_raw_content_scan_failed")

    return not reasons, reasons, scan_issues


def validate_upstream(summary: dict[str, Any], schema: dict[str, Any]) -> tuple[list[str], list[str]]:
    if summary.get("stage") != STAGE12460:
        raise SystemExit("fail_closed: unexpected Stage12460 summary stage")
    if summary.get("training_allowed") is not False or summary.get("admission_allowed") is not False:
        raise SystemExit("fail_closed: Stage12460 must keep training/admission disabled")
    if summary.get("guardrail_scan_passed") is not True:
        raise SystemExit("fail_closed: Stage12460 public guardrail scan did not pass")
    required_slots = summary.get("required_return_slots")
    if not isinstance(required_slots, list) or not all(isinstance(slot, str) for slot in required_slots):
        raise SystemExit("fail_closed: Stage12460 required_return_slots missing or invalid")
    if "ordered_patch_effect_causality" not in required_slots:
        required_slots = [*required_slots, "ordered_patch_effect_causality"]

    required_fields = schema.get("required_public_fields")
    if not isinstance(required_fields, list) or not all(isinstance(field, str) for field in required_fields):
        raise SystemExit("fail_closed: return schema required_public_fields missing or invalid")
    return required_fields, required_slots


def accepted_ref(line_no: int, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12461_accepted_private_return_ref_hash_only_v1",
        "return_line_hash": stable_hash({"line_no": line_no, "row": row}),
        "candidate_ref_hash": str(row.get("candidate_ref_hash") or ""),
        "source_lane_id_hash": stable_hash(row.get("source_lane_id")),
        "slot_hashes_hash": stable_hash(row.get("slot_hashes")),
        "proof_complete_hash": stable_hash(row.get("proof_complete")),
        "training_allowed": False,
        "admission_allowed": False,
        "external_repair_credit_admitted": False,
    }


def build_contract(required_fields: list[str], required_slots: list[str]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "record_type": "stage12461_validator_contract_v1",
        "control_boundary": "validator_skeleton_only_no_execution_no_admission_no_training",
        "inputs": {
            "stage12460_summary": str(REQUEST_SUMMARY.relative_to(ROOT)),
            "stage12460_return_schema": str(RETURN_SCHEMA.relative_to(ROOT)),
            "optional_private_return_jsonl": str(RETURN_FILE.relative_to(ROOT)),
        },
        "outputs": {
            "summary": str(SUMMARY_OUT.relative_to(ROOT)),
            "accepted_return_ref_index": str(ACCEPTED_INDEX.relative_to(ROOT)),
            "validator_contract": str(CONTRACT_OUT.relative_to(ROOT)),
        },
        "required_public_fields": required_fields,
        "required_slots": required_slots,
        "row_acceptance_rules": [
            "proof_complete_true",
            "no_blocker_codes",
            "anti_leak_pass_true",
            "credit_training_and_admission_flags_false",
            "all_required_slots_present_exactly_not_placeholder",
            "all_required_slot_hashes_present_and_not_placeholder",
            "buggy_verifier_status_fail",
            "fixed_or_before_plus_patch_status_pass",
            "exact_same_verifier_identity_proven",
            "patch_diff_apply_lineage_proven",
            "ordered_patch_effect_causality_proven",
            "public_return_scan_has_no_raw_path_url_command_output_diff_or_source_text",
            "rejects_placeholder_slot_values_unknown_claimed_proven_equivalent_true_pass_ok",
        ],
        "non_actions": [
            "does_not_execute_tests",
            "does_not_apply_patches",
            "does_not_checkout_repositories",
            "does_not_admit_rows",
            "does_not_emit_training_rows",
            "does_not_train",
        ],
        "always_false_flags": {
            "training_allowed": False,
            "admission_allowed": False,
            "packaging_allowed": False,
        },
    }


def main() -> int:
    request_summary = read_json(REQUEST_SUMMARY)
    return_schema = read_json(RETURN_SCHEMA)
    required_fields, required_slots = validate_upstream(request_summary, return_schema)

    return_rows, rejected_counts = read_jsonl_lenient(RETURN_FILE)
    accepted_rows: list[dict[str, Any]] = []
    proof_complete_count = 0
    public_scan_issues: list[str] = []

    for line_no, row in return_rows:
        ok, reasons, scan_issues = validate_return_row(row, required_fields, required_slots)
        public_scan_issues.extend(scan_issues)
        if ok:
            proof_complete_count += 1
            accepted_rows.append(accepted_ref(line_no, row))
        else:
            for reason in reasons:
                rejected_counts[reason] += 1

    return_file_present = RETURN_FILE.exists()
    if not return_file_present:
        decision = "blocked_no_private_returns_present_external_repair_credit_zero"
        rejected_counts["private_return_file_missing"] += 1
    elif proof_complete_count == 0:
        decision = "blocked_private_returns_not_proof_complete_external_repair_credit_zero"
    else:
        decision = "private_return_refs_validated_hash_only_external_repair_credit_zero"

    contract = build_contract(required_fields, required_slots)
    summary = {
        "stage": STAGE,
        "record_type": "stage12461_external_patch_effect_return_validator_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Control validator only. This stage validates public-safe private return rows "
            "and keeps external repair credit, admission, packaging, and training closed."
        ),
        "return_file_present": return_file_present,
        "return_row_count": len(return_rows),
        "proof_complete_count": proof_complete_count,
        "accepted_return_ref_count": len(accepted_rows),
        "admitted_count": 0,
        "admitted_external_comparable_repair_credit_count": 0,
        "remaining_external_fail_to_pass_gap_after_returns": EXPECTED_GAP,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "emitted_training_rows": 0,
        "sealed_eval_rows": 0,
        "execution_performed_by_stage": False,
        "tests_executed_by_stage": False,
        "rows_admitted_by_stage": False,
        "model_training_performed_by_stage": False,
        "rejected_return_reasons": dict(sorted(rejected_counts.items())),
        "guardrail_scan": {
            "scan_scope": "public_private_proof_slot_return_rows_only",
            "scan_passed": not public_scan_issues,
            "raw_leak_count": len(public_scan_issues),
            "issue_hashes": [stable_hash(issue) for issue in public_scan_issues[:50]],
        },
        "guardrail_scan_passed": not public_scan_issues,
        "raw_leak_count": len(public_scan_issues),
        "schema_issue_count": 0,
        "required_return_slots": required_slots,
        "artifact_refs": {
            "accepted_return_ref_index": str(ACCEPTED_INDEX.relative_to(ROOT)),
            "validator_contract": str(CONTRACT_OUT.relative_to(ROOT)),
            "summary": str(SUMMARY_OUT.relative_to(ROOT)),
        },
        "source_input_hashes": {
            "stage12460_summary": file_hash(REQUEST_SUMMARY),
            "stage12460_return_schema": file_hash(RETURN_SCHEMA),
            "private_return_file": file_hash(RETURN_FILE),
        },
        "summary_hash": stable_hash(
            {
                "decision": decision,
                "return_file_present": return_file_present,
                "return_row_count": len(return_rows),
                "proof_complete_count": proof_complete_count,
                "rejected_return_reasons": dict(sorted(rejected_counts.items())),
            }
        ),
    }

    write_json(CONTRACT_OUT, contract)
    write_jsonl(ACCEPTED_INDEX, accepted_rows)
    write_json(SUMMARY_OUT, summary)
    print(SUMMARY_OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
