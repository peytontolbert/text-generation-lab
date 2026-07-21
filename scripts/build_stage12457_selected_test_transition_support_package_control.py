#!/usr/bin/env python3
"""Build Stage12457 selected-test transition support package control artifact.

This stage packages only public-safe support metadata from Stage12456 audited
rows. It emits no model training rows and grants no admission or training
authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12457_selected_test_transition_support_package_control"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12456_OUT = (
    ROOT / "runs/local/artifacts/stage12456_selected_test_return_proof_depth_audit"
)
STAGE12456_SUMMARY = STAGE12456_OUT / "summary.json"
STAGE12456_ROW_AUDIT = STAGE12456_OUT / "row_audit_records.jsonl"
STAGE12445_SELECTED_TEST_RETURN = (
    ROOT
    / "runs/local/artifacts/stage12445_adapter_execution_return_ingest_and_level3_gate"
    / "returns/selected_test_transition_root_batch_non_web_first.return.jsonl"
)
STAGE12450_CONTROL = (
    ROOT
    / "runs/local/artifacts/stage12450_post_stage12449_level3_supply_control_board"
    / "summary.json"
)

ZERO_AUTHORITY = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "training_materializer_allowed": False,
    "execution_allowed": False,
    "execution_performed_by_stage": False,
    "emitted_training_rows": 0,
    "sealed_eval_rows_emitted": 0,
    "model_training_row_count": 0,
}

EXACT_DEPTHS = {
    "same_source_lineage_depth": "source_record_reprojection_exact_lineage_hash_match",
    "verifier_relevance_depth": "source_candidate_selected_verifier_command_bound",
    "policy_label_independence_depth": "metadata_derived_label_with_counterfactuals_non_eval_bound",
    "causal_linkage_depth": "source_execution_result_to_status_reprojection_exact",
    "state_delta_depth": "source_status_to_state_delta_codes_recomputed_exact",
    "stop_continue_depth": "source_stop_decision_or_status_rule_recomputed_exact",
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
    "raw",
    "raw_text",
    "trace",
    "trace_text",
    "source",
    "source_path",
    "source_text",
    "private_locator",
}
ALLOWED_KEY_CONTEXT_RE = re.compile(
    r"(policy|emitted|forbidden|required|slot|slots|schema|hash|hashes|ref|refs|"
    r"class|status|proof|reason|contract|request|count|scan|supply|stage|artifact|"
    r"depth|summary|input|fingerprint|gate|credit|quarantine|manifest)",
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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} is not a JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
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
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bucket_counter(counter: Counter[str]) -> dict[str, str | int]:
    """Expose distribution shape without publishing exact tiny cohort identities."""
    if not counter:
        return {"bucketed_total": 0, "bucket_policy": "empty"}
    return {
        "bucketed_total": int(sum(counter.values())),
        "distinct_bucket_count": len(counter),
        "max_bucket_size": int(max(counter.values())),
        "bucket_policy": "exact_keys_suppressed_stage12457_public_control",
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


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


def scan_public(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not ALLOWED_KEY_CONTEXT_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_public_leak:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(scan_public(f"{label}.{key}", child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(scan_public(f"{label}[{index}]", child))
    return issues


def depth_exact(record: dict[str, Any]) -> bool:
    return all(record.get(key) == expected for key, expected in EXACT_DEPTHS.items())


def package_eligible(record: dict[str, Any]) -> bool:
    return (
        record.get("source_match_class") == "source_reprojection_exact"
        and depth_exact(record)
        and record.get("training_eligible") is False
        and record.get("strict_eval_eligible") is False
    )


def bool_counter(value: bool) -> int:
    return 1 if value else 0


def build_artifacts() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    stage12456_summary = read_json(STAGE12456_SUMMARY)
    stage12450_control = read_json(STAGE12450_CONTROL)
    audit_rows = read_jsonl(STAGE12456_ROW_AUDIT)
    return_rows = read_jsonl(STAGE12445_SELECTED_TEST_RETURN)

    return_by_hash: dict[str, dict[str, Any]] = {}
    duplicate_return_hash_count = 0
    for row in return_rows:
        row_hash = str(row.get("return_row_hash") or "")
        if not row_hash:
            continue
        if row_hash in return_by_hash:
            duplicate_return_hash_count += 1
        return_by_hash[row_hash] = row

    input_hashes = {
        "stage12456_summary_sha256_24": file_hash(STAGE12456_SUMMARY),
        "stage12456_row_audit_records_sha256_24": file_hash(STAGE12456_ROW_AUDIT),
        "stage12445_selected_test_return_sha256_24": file_hash(
            STAGE12445_SELECTED_TEST_RETURN
        ),
        "stage12450_control_board_sha256_24": file_hash(STAGE12450_CONTROL),
    }

    candidate_count = len(audit_rows)
    eligible_rows = [row for row in audit_rows if package_eligible(row)]
    selected_hashes = {str(row.get("return_row_hash") or "") for row in eligible_rows}
    missing_selected_return_hashes = sorted(
        row_hash for row_hash in selected_hashes if row_hash not in return_by_hash
    )

    language_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    source_stage_counts: Counter[str] = Counter()
    root_hash_counts: Counter[str] = Counter()
    source_match_counts: Counter[str] = Counter()
    external_repair_credit_counts: Counter[str] = Counter()
    proof_depth_counts: dict[str, Counter[str]] = {key: Counter() for key in EXACT_DEPTHS}
    ineligible_reason_counts: Counter[str] = Counter()
    package_rows: list[dict[str, Any]] = []
    quarantine_rows: list[dict[str, Any]] = []

    for record in audit_rows:
        source_match_counts[str(record.get("source_match_class") or "unknown")] += 1
        external_repair_credit_counts[
            str(record.get("external_repair_credit_class") or "unknown")
        ] += 1
        for key in EXACT_DEPTHS:
            proof_depth_counts[key][str(record.get(key) or "unknown")] += 1
        if record.get("source_match_class") != "source_reprojection_exact":
            ineligible_reason_counts["source_match_not_exact"] += 1
        if not depth_exact(record):
            ineligible_reason_counts["proof_depth_not_exact_source_backed"] += 1
        if record.get("training_eligible") is not False:
            ineligible_reason_counts["training_eligible_not_false"] += 1
        if record.get("strict_eval_eligible") is not False:
            ineligible_reason_counts["strict_eval_eligible_not_false"] += 1

    for index, record in enumerate(eligible_rows, start=1):
        row_hash = str(record.get("return_row_hash") or "")
        return_row = return_by_hash.get(row_hash, {})
        root_hash = str(return_row.get("root_id_hash") or "missing")
        row_status = str(record.get("observation_status_class") or "unknown")
        language = str(record.get("language_family") or "unknown")
        source_stage = str(record.get("source_stage") or "unknown")

        language_counts[language] += 1
        status_counts[row_status] += 1
        source_stage_counts[source_stage] += 1
        root_hash_counts[root_hash] += 1

        row_index = {
            "package_row_ref_hash": stable_hash(["package_row", index, row_hash]),
            "row_ref_hash": record.get("row_ref_hash"),
            "return_row_hash": row_hash,
            "source_record_ref_hash": record.get("source_record_ref_hash"),
            "root_id_hash": root_hash,
            "source_match_class": record.get("source_match_class"),
            "source_stage": source_stage,
            "language_family": language,
            "observation_status_class": row_status,
            "proof_depth_class": "all_six_dimensions_source_backed_exact",
            "training_eligible": False,
            "strict_eval_eligible": False,
            "support_use_class": "transition_support_only_not_training_material",
            "external_repair_credit_class": record.get("external_repair_credit_class"),
            "external_repair_credit_allowed": False,
        }
        package_rows.append(row_index)
        if row_status == "FAIL_TO_PASS":
            quarantine_rows.append(
                {
                    "quarantine_ref_hash": stable_hash(["quarantine", index, row_hash]),
                    "row_ref_hash": record.get("row_ref_hash"),
                    "return_row_hash": row_hash,
                    "root_id_hash": root_hash,
                    "source_record_ref_hash": record.get("source_record_ref_hash"),
                    "source_stage": source_stage,
                    "language_family": language,
                    "observation_status_class": row_status,
                    "repair_credit_class": record.get("repair_credit_class"),
                    "external_repair_credit_class": record.get(
                        "external_repair_credit_class"
                    ),
                    "quarantine_class": "quarantined_from_external_repair_credit",
                    "external_repair_credit_allowed": False,
                    "external_repair_credit_value": 0,
                }
            )

    package_row_count = len(package_rows)
    fail_to_pass_quarantine_count = len(quarantine_rows)
    external_credit_count = external_repair_credit_counts.get(
        "external_comparable_repair_patch_effect_proven", 0
    )

    gates = {
        "stage12456_guardrail_scan_passed": stage12456_summary.get("guardrail_scan_passed")
        is True,
        "stage12456_all_rows_source_backed_depth": stage12456_summary.get(
            "all_rows_source_backed_depth"
        )
        is True,
        "stage12456_transition_support_packaging_allowed": stage12456_summary.get(
            "transition_support_packaging_allowed"
        )
        is True,
        "stage12456_external_repair_credit_count_zero": int(
            stage12456_summary.get("external_repair_credit_count") or 0
        )
        == 0,
        "stage12456_training_and_eval_disabled": stage12456_summary.get("training_allowed")
        is False
        and stage12456_summary.get("admission_allowed") is False
        and int(stage12456_summary.get("emitted_training_rows") or 0) == 0
        and int(stage12456_summary.get("sealed_eval_rows_emitted") or 0) == 0,
        "stage12450_control_board_training_blocked": stage12450_control.get(
            "training_allowed"
        )
        is False
        and stage12450_control.get("admission_allowed") is False
        and int(stage12450_control.get("external_fail_to_pass_validated_delta") or 0) == 0,
        "candidate_rows_nonempty": candidate_count > 0,
        "all_candidate_rows_selected": package_row_count == candidate_count,
        "all_selected_rows_have_return_root_hash": not missing_selected_return_hashes
        and "missing" not in root_hash_counts,
        "selected_return_hashes_unique": len(selected_hashes) == package_row_count
        and duplicate_return_hash_count == 0,
        "all_selected_rows_source_reprojection_exact": source_match_counts
        == Counter({"source_reprojection_exact": candidate_count}),
        "all_selected_rows_proof_depth_exact": all(
            counter == Counter({EXACT_DEPTHS[key]: candidate_count})
            for key, counter in proof_depth_counts.items()
        ),
        "all_selected_rows_training_flags_false": all(
            row.get("training_eligible") is False
            and row.get("strict_eval_eligible") is False
            for row in audit_rows
        ),
        "fail_to_pass_rows_quarantined_from_external_repair_credit": (
            fail_to_pass_quarantine_count == status_counts.get("FAIL_TO_PASS", 0) == 9
        ),
        "external_repair_credit_remains_zero": external_credit_count == 0,
        "no_model_training_rows_emitted": True,
    }

    transition_support_package_ready = all(gates.values())
    manifest_without_scan = {
        "stage": STAGE,
        "record_type": "selected_test_transition_support_package_control_v1",
        "decision": (
            "transition_support_package_ready_training_and_admission_blocked"
            if transition_support_package_ready
            else "transition_support_package_blocked_gate_failure"
        ),
        **ZERO_AUTHORITY,
        "transition_support_package_ready": transition_support_package_ready,
        "candidate_row_count": candidate_count,
        "package_row_count": package_row_count,
        "package_manifest_row_count": package_row_count,
        "quarantine_row_count": fail_to_pass_quarantine_count,
        "external_repair_credit_allowed": False,
        "external_repair_credit_count": 0,
        "external_repair_credit_value_total": 0,
        "source_match_class_counts": dict(sorted(source_match_counts.items())),
        "proof_depth_class_counts": {
            key: dict(sorted(counter.items())) for key, counter in sorted(proof_depth_counts.items())
        },
        "private_distribution_counts": {
            "language_counts": dict(sorted(language_counts.items())),
            "observation_status_counts": dict(sorted(status_counts.items())),
            "source_stage_counts": dict(sorted(source_stage_counts.items())),
            "root_hash_counts": dict(sorted(root_hash_counts.items())),
        },
        "public_bucketed_distribution_counts": {
            "language_counts_bucketed": bucket_counter(language_counts),
            "observation_status_counts_bucketed": bucket_counter(status_counts),
            "source_stage_counts_bucketed": bucket_counter(source_stage_counts),
            "root_hash_counts_bucketed": bucket_counter(root_hash_counts),
        },
        "clustering_exposure_policy": (
            "exact tiny cohort counts are kept only in private local control artifacts; "
            "summary consumers should use public_bucketed_distribution_counts"
        ),
        "external_repair_credit_class_counts": dict(
            sorted(external_repair_credit_counts.items())
        ),
        "ineligible_reason_counts": dict(sorted(ineligible_reason_counts.items())),
        "quarantine_class_counts": {
            "quarantined_from_external_repair_credit": fail_to_pass_quarantine_count
        },
        "training_materializer_gates": gates,
        "future_training_materializer_policy": {
            "training_allowed": False,
            "admission_allowed": False,
            "requires_separate_materializer_stage": True,
            "requires_external_repair_credit_to_remain_zero": True,
            "requires_raw_value_hydration_outside_public_artifact": True,
            "may_consume_only_hash_class_count_manifest": True,
            "model_rows_available_in_this_stage": 0,
        },
        "input_hashes": input_hashes,
        "package_hashes": {
            "package_row_index_sha256_24": stable_hash(package_rows),
            "external_repair_credit_quarantine_sha256_24": stable_hash(quarantine_rows),
        },
        "upstream_count_checks": {
            "stage12456_return_row_count": int(stage12456_summary.get("return_row_count") or 0),
            "stage12456_row_audit_record_count": int(
                stage12456_summary.get("row_audit_record_count") or 0
            ),
            "stage12445_selected_test_verifier_observation_validated_delta": int(
                stage12450_control.get("selected_test_verifier_observation_validated_delta")
                or 0
            ),
            "stage12450_external_fail_to_pass_validated_delta": int(
                stage12450_control.get("external_fail_to_pass_validated_delta") or 0
            ),
        },
        "claim_boundary": (
            "Support-only transition package control artifact. It contains only "
            "hashes, classes, and counts; emits zero model training rows; grants "
            "no admission; and grants zero external FAIL_TO_PASS repair credit."
        ),
        "guardrail_scan": {},
        "guardrail_scan_passed": False,
        "raw_leak_count": 0,
        "schema_issue_count": 0,
        "summary_hash": "pending",
    }

    all_outputs_for_scan = {
        "manifest": manifest_without_scan,
        "package_rows": package_rows,
        "quarantine_rows": quarantine_rows,
    }
    public_scan_issues = sorted(set(scan_public("stage12457_outputs", all_outputs_for_scan)))
    manifest = dict(manifest_without_scan)
    manifest["guardrail_scan"] = {
        "scan_passed": not public_scan_issues,
        "issue_count": len(public_scan_issues),
        "issues": public_scan_issues,
        "raw_leak_count": len(
            [
                issue
                for issue in public_scan_issues
                if "raw_public_leak" in issue or "forbidden_public_key" in issue
            ]
        ),
        "scan_scope": "stage12457_hash_class_count_support_control_outputs",
    }
    manifest["guardrail_scan_passed"] = manifest["guardrail_scan"]["scan_passed"]
    manifest["raw_leak_count"] = manifest["guardrail_scan"]["raw_leak_count"]
    manifest["transition_support_package_ready"] = (
        transition_support_package_ready and manifest["guardrail_scan_passed"]
    )
    if not manifest["transition_support_package_ready"]:
        manifest["decision"] = "transition_support_package_blocked_gate_failure"
    manifest["summary_hash"] = stable_hash(
        {key: value for key, value in manifest.items() if key != "summary_hash"}
    )
    return manifest, package_rows, quarantine_rows


def public_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    public = dict(manifest)
    public.pop("private_distribution_counts", None)
    public["private_distribution_counts_suppressed"] = True
    public["private_control_manifest"] = "private_control_manifest.json"
    public["public_summary_policy"] = (
        "exact tiny cohort language/status/source/root counts are suppressed here; "
        "use only bucketed distributions for control-plane summaries"
    )
    return public


def main() -> None:
    manifest, package_rows, quarantine_rows = build_artifacts()
    public = public_manifest(manifest)
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "private_control_manifest.json", manifest)
    write_json(OUT / "package_manifest.json", public)
    write_json(OUT / f"{STAGE}.json", public)
    write_json(OUT / "summary.json", public)
    write_json(SUMMARY_OUT, public)
    write_jsonl(OUT / "support_package_row_index.jsonl", package_rows)
    write_jsonl(OUT / "external_repair_credit_quarantine.jsonl", quarantine_rows)
    print(
        json.dumps(
            {
                "stage": public["stage"],
                "decision": public["decision"],
                "candidate_row_count": public["candidate_row_count"],
                "package_row_count": public["package_row_count"],
                "quarantine_row_count": public["quarantine_row_count"],
                "external_repair_credit_count": public["external_repair_credit_count"],
                "training_allowed": public["training_allowed"],
                "admission_allowed": public["admission_allowed"],
                "packaging_allowed": public["packaging_allowed"],
                "transition_support_package_ready": public[
                    "transition_support_package_ready"
                ],
                "guardrail_scan_passed": public["guardrail_scan_passed"],
                "raw_leak_count": public["raw_leak_count"],
                "private_distribution_counts_suppressed": public[
                    "private_distribution_counts_suppressed"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
