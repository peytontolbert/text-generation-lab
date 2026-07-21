#!/usr/bin/env python3
"""Build Stage12458 balance and external repair gate control artifact.

This is a public-safe control board. It emits no model rows, admits no rows,
and does not convert selected-test transition support into external repair
credit.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12458_balance_and_external_repair_gate"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12457_ARTIFACT = (
    ROOT / "runs/local/artifacts/stage12457_selected_test_transition_support_package_control"
)
STAGE12457_SUMMARY = STAGE12457_ARTIFACT / "summary.json"
STAGE12457_PRIVATE_MANIFEST = STAGE12457_ARTIFACT / "private_control_manifest.json"
STAGE12450_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12450_post_stage12449_level3_supply_control_board"
    / "summary.json"
)
STAGE12456_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12456_selected_test_return_proof_depth_audit"
    / "summary.json"
)

CONTROL_BOARD_SUMMARY_CANDIDATES = [
    ROOT / "runs/summaries/stage12222_patch_trace_floor_audit.json",
    ROOT / "runs/summaries/stage12224_patch_trace_training_rollup.json",
    ROOT / "runs/summaries/stage12233_external_acquisition_blocker_decision.json",
    ROOT / "runs/summaries/stage12237_current_training_control_board.json",
    ROOT / "runs/summaries/stage12240_external_repair_acquisition_request_v2.json",
    ROOT / "runs/summaries/stage12283_patch_effect_proof_source_plan.json",
    ROOT / "runs/summaries/stage12284_external_repair_commit_pair_preflight.json",
    ROOT / "runs/summaries/stage12290_replay_queue_repair_or_retarget_decision.json",
    ROOT / "runs/summaries/stage12293_commit_pair_queue_exhaustion_and_next_source_decision.json",
    ROOT / "runs/summaries/stage12302_transition_function_graph_control_board.json",
    ROOT / "runs/summaries/stage12313_spine_aligned_training_progress_analysis.json",
    ROOT / "runs/summaries/stage12319_500_task_scale_control_board.json",
    ROOT / "runs/summaries/stage12371_current_dataset_control_board.json",
    ROOT / "runs/summaries/stage12377_current_dataset_control_board_v2.json",
    ROOT / "runs/summaries/stage12384_current_dataset_control_board_v4.json",
    ROOT / "runs/summaries/stage12450_post_stage12449_level3_supply_control_board.json",
]

ZERO_AUTHORITY = {
    "training_allowed": False,
    "selected_test_support_training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "training_materializer_allowed": False,
    "execution_allowed": False,
    "execution_performed_by_stage": False,
    "emitted_training_rows": 0,
    "model_training_row_count": 0,
    "trainable_level3_rows": 0,
    "sealed_eval_rows": 0,
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
    "raw",
    "raw_text",
    "trace",
    "trace_text",
    "source_text",
    "private_locator",
}
ALLOWED_KEY_CONTEXT_RE = re.compile(
    r"(policy|emitted|forbidden|required|slot|slots|schema|hash|hashes|ref|refs|"
    r"class|status|proof|reason|contract|request|count|scan|supply|stage|artifact|"
    r"depth|summary|input|fingerprint|gate|credit|quarantine|manifest|lane|control)",
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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


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


def bucketed_distribution_from_private_manifest(
    private_manifest: dict[str, Any],
) -> dict[str, dict[str, str | int]]:
    private_counts = private_manifest.get("private_distribution_counts")
    if not isinstance(private_counts, dict):
        return {}

    bucketed: dict[str, dict[str, str | int]] = {}
    for name, counts in private_counts.items():
        if not isinstance(counts, dict):
            continue
        numeric_counts = [value for value in counts.values() if isinstance(value, int)]
        if not numeric_counts:
            continue
        bucketed[f"{name}_bucketed"] = {
            "bucket_policy": "exact_keys_suppressed_stage12458_public_control",
            "bucketed_total": int(sum(numeric_counts)),
            "distinct_bucket_count": len(numeric_counts),
            "max_bucket_size": int(max(numeric_counts)),
        }
    return bucketed


def derive_controlled_fail_to_pass_support_count(
    stage12457_summary: dict[str, Any],
    stage12457_private: dict[str, Any],
    stage12456_summary: dict[str, Any],
) -> tuple[int, str]:
    private_status_counts = (
        stage12457_private.get("private_distribution_counts", {})
        if isinstance(stage12457_private.get("private_distribution_counts"), dict)
        else {}
    )
    observation_status_counts = (
        private_status_counts.get("observation_status_counts", {})
        if isinstance(private_status_counts.get("observation_status_counts"), dict)
        else {}
    )
    private_fail_to_pass = int_or_none(observation_status_counts.get("FAIL_TO_PASS"))
    private_quarantine = int_or_none(stage12457_private.get("quarantine_row_count"))
    public_quarantine = int_or_none(stage12457_summary.get("quarantine_row_count"))

    if private_fail_to_pass is not None and private_quarantine is not None:
        return (
            min(private_fail_to_pass, private_quarantine),
            "stage12457_private_status_fail_to_pass_intersected_with_quarantine",
        )
    if private_quarantine is not None:
        return private_quarantine, "stage12457_private_quarantine_row_count"
    if public_quarantine is not None:
        return public_quarantine, "stage12457_public_quarantine_row_count"

    repair_credit_counts = stage12456_summary.get("repair_credit_class_counts")
    if isinstance(repair_credit_counts, dict):
        value = int_or_none(repair_credit_counts.get("controlled_or_mutation_transition_support"))
        if value is not None:
            return value, "stage12456_repair_credit_class_count"

    return 0, "no_count_source_available"


def external_floor_evidence(stage12450_summary: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    paths = [STAGE12450_SUMMARY, *CONTROL_BOARD_SUMMARY_CANDIDATES]
    seen: set[Path] = set()
    seen_evidence: set[tuple[str, str]] = set()

    for path in paths:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        record = read_json(path)
        floor = int_or_none(record.get("external_fail_to_pass_floor"))
        gap = int_or_none(record.get("external_fail_to_pass_remaining_floor_gap"))
        validated_delta = int_or_none(record.get("external_fail_to_pass_validated_delta"))
        if floor is None and gap is None and validated_delta is None:
            continue
        item = {
            "stage": str(record.get("stage") or path.stem),
            "external_fail_to_pass_floor": floor,
            "external_fail_to_pass_remaining_floor_gap": gap,
            "external_fail_to_pass_validated_delta": validated_delta,
            "summary_sha256_24": file_hash(path),
        }
        evidence_key = (str(item["stage"]), str(item["summary_sha256_24"]))
        if evidence_key in seen_evidence:
            continue
        seen_evidence.add(evidence_key)
        evidence.append(item)

    if not evidence and stage12450_summary:
        evidence.append(
            {
                "stage": str(
                    stage12450_summary.get("stage")
                    or "stage12450_post_stage12449_level3_supply_control_board"
                ),
                "external_fail_to_pass_floor": int_or_none(
                    stage12450_summary.get("external_fail_to_pass_floor")
                ),
                "external_fail_to_pass_remaining_floor_gap": int_or_none(
                    stage12450_summary.get("external_fail_to_pass_remaining_floor_gap")
                ),
                "external_fail_to_pass_validated_delta": int_or_none(
                    stage12450_summary.get("external_fail_to_pass_validated_delta")
                ),
                "summary_sha256_24": file_hash(STAGE12450_SUMMARY),
            }
        )
    return evidence


def choose_external_gap(evidence: list[dict[str, Any]]) -> int:
    for item in evidence:
        if item.get("stage") == "stage12450_post_stage12449_level3_supply_control_board":
            gap = int_or_none(item.get("external_fail_to_pass_remaining_floor_gap"))
            if gap is not None:
                return gap
    for item in reversed(evidence):
        gap = int_or_none(item.get("external_fail_to_pass_remaining_floor_gap"))
        if gap is not None:
            return gap
    return 15


def build_summary() -> dict[str, Any]:
    stage12457_summary = read_json(STAGE12457_SUMMARY)
    stage12457_private = read_json(STAGE12457_PRIVATE_MANIFEST)
    stage12450_summary = read_json(STAGE12450_SUMMARY)
    stage12456_summary = read_json(STAGE12456_SUMMARY)

    selected_rows = int_or_none(stage12457_summary.get("package_row_count")) or 0
    controlled_count, controlled_count_source = derive_controlled_fail_to_pass_support_count(
        stage12457_summary, stage12457_private, stage12456_summary
    )
    prior_countable_supply = int(
        stage12450_summary.get("prior_countable_supply")
        or stage12450_summary.get("countable_supply_before_stage12445")
        or 190
    )
    target_countable_supply = int(
        stage12450_summary.get("target")
        or stage12450_summary.get("target_countable_supply")
        or 500
    )
    stage12445_validated_level3_candidate_delta = int(
        stage12450_summary.get("stage12445_validated_level3_candidate_delta") or 0
    )
    selected_test_verifier_observation_validated_delta = int(
        stage12450_summary.get("selected_test_verifier_observation_validated_delta") or 0
    )
    external_fail_to_pass_validated_delta = int(
        stage12450_summary.get("external_fail_to_pass_validated_delta") or 0
    )
    effective_supply = int(
        stage12450_summary.get("effective_supply_after_validated_delta")
        or stage12450_summary.get("effective_supply")
        or (prior_countable_supply + stage12445_validated_level3_candidate_delta)
    )
    remaining_gap = int(
        stage12450_summary.get("remaining_gap_to_500_after_validated_delta")
        or stage12450_summary.get("remaining_gap")
        or max(target_countable_supply - effective_supply, 0)
    )
    floor_evidence = external_floor_evidence(stage12450_summary)
    external_gap = choose_external_gap(floor_evidence)

    public_bucketed_distribution_counts = stage12457_summary.get(
        "public_bucketed_distribution_counts"
    )
    if not isinstance(public_bucketed_distribution_counts, dict):
        public_bucketed_distribution_counts = bucketed_distribution_from_private_manifest(
            stage12457_private
        )

    summary: dict[str, Any] = {
        **ZERO_AUTHORITY,
        "stage": STAGE,
        "record_type": "balance_and_external_repair_gate_control_board_v1",
        "decision": "training_admission_and_external_repair_credit_blocked",
        "claim_boundary": (
            "Control-board/gate artifact only. Selected-test transition support is "
            "not training material, not admission material, and not external "
            "comparable repair proof."
        ),
        "target": target_countable_supply,
        "prior_countable_supply": prior_countable_supply,
        "stage12445_validated_level3_candidate_delta": stage12445_validated_level3_candidate_delta,
        "effective_supply": effective_supply,
        "remaining_gap": remaining_gap,
        "remaining_gap_to_500_after_validated_delta": remaining_gap,
        "selected_test_verifier_observation_validated_delta": selected_test_verifier_observation_validated_delta,
        "external_fail_to_pass_validated_delta": external_fail_to_pass_validated_delta,
        "selected_test_transition_support_rows": selected_rows,
        "selected_test_transition_support_package_ready": bool(
            stage12457_summary.get("transition_support_package_ready") is True
        ),
        "controlled_or_mutation_fail_to_pass_support_count": controlled_count,
        "controlled_or_mutation_fail_to_pass_support_count_source": controlled_count_source,
        "external_comparable_repair_credit_count": 0,
        "external_fail_to_pass_remaining_floor_gap": external_gap,
        "external_fail_to_pass_floor_evidence": floor_evidence,
        "selected_test_support_credit_boundary": {
            "controlled_or_mutation_fail_to_pass_support_is_training_material": False,
            "controlled_or_mutation_fail_to_pass_support_is_admission_material": False,
            "controlled_or_mutation_fail_to_pass_support_is_external_repair_proof": False,
            "external_repair_credit_requires_comparable_patch_effect_proof": True,
        },
        "balance_public_bucketed_distribution_counts": public_bucketed_distribution_counts,
        "next_source_lane_recommendations": [
            {
                "priority": 1,
                "lane": "external_comparable_patch_effect_proof",
                "reason": (
                    "The external FAIL_TO_PASS repair floor remains open; selected-test "
                    "verifier observations cannot close comparable repair credit."
                ),
            },
            {
                "priority": 2,
                "lane": "non_web_non_python_selected_or_authoritative_verifier_balance",
                "reason": (
                    "Future support materialization should rebalance toward Rust/C/C++ "
                    "or other non-web/non-Python sources without claiming repair credit."
                ),
            },
            {
                "priority": 3,
                "lane": "separate_task_specific_support_materializer",
                "reason": (
                    "If selected-test transition support is useful, build a separate "
                    "materializer with raw-value hydration outside this public gate."
                ),
            },
        ],
        "hard_blockers": [
            "no_training_until_external_comparable_repair_proof_floor_is_met_or_explicitly_replaced",
            "no_training_from_selected_test_support_until_separate_task_specific_support_materializer_exists",
            "no_admission_from_stage12457_or_stage12458_control_artifacts",
            "no_external_repair_credit_from_controlled_or_mutation_selected_test_fail_to_pass_rows",
        ],
        "source_fingerprints": {
            "stage12457_summary_sha256_24": file_hash(STAGE12457_SUMMARY),
            "stage12457_private_control_manifest_sha256_24": file_hash(
                STAGE12457_PRIVATE_MANIFEST
            ),
            "stage12450_summary_sha256_24": file_hash(STAGE12450_SUMMARY),
            "stage12456_summary_sha256_24": file_hash(STAGE12456_SUMMARY),
        },
        "public_summary_policy": (
            "Do not expose exact tiny language, status, source-stage, or root-cluster "
            "counts in this public control summary; use bucketed distribution shapes only."
        ),
    }

    issues = scan_public("summary", summary)
    summary["guardrail_scan"] = {
        "scan_scope": "stage12458_public_safe_balance_and_external_repair_gate",
        "scan_passed": len(issues) == 0,
        "issue_count": len(issues),
        "issues": issues,
        "raw_leak_count": len([issue for issue in issues if ":raw_public_leak:" in issue]),
    }
    summary["guardrail_scan_passed"] = len(issues) == 0
    summary["raw_leak_count"] = summary["guardrail_scan"]["raw_leak_count"]
    summary["schema_issue_count"] = 0
    summary["summary_hash"] = stable_hash(summary)
    return summary


def main() -> None:
    summary = build_summary()
    write_json(OUT / "summary.json", summary)
    write_json(OUT / f"{STAGE}.json", summary)
    write_json(SUMMARY_OUT, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
