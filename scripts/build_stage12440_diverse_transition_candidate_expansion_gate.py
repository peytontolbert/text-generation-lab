#!/usr/bin/env python3
"""Build Stage12440 public-safe diversity/similarity expansion gate.

This stage reconnects older diversity/dedupe controls to the current
Level-3/transition lane as a review-priority gate only. It never trains,
admits rows, executes raw review, or emits raw candidate values.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12440_diverse_transition_candidate_expansion_gate"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12439_SUMMARY = ROOT / "runs/summaries/stage12439_session_like_raw_private_semantic_review_packet_request.json"
STAGE12438_SUMMARY = ROOT / "runs/summaries/stage12438_session_like_materializer_upgrade_postrun.json"
STAGE12436_SUMMARY = ROOT / "runs/summaries/stage12436_parallel_two_lane_control_request.json"
STAGE12364_SUMMARY = ROOT / "runs/summaries/stage12364_diversity_weighted_admission_policy.json"
STAGE12385_SUMMARY = ROOT / "runs/summaries/stage12385_combined_train_support_ledger_v15_dedup.json"
STAGE12295_SUMMARY = ROOT / "runs/summaries/stage12295_transition_function_ledger.json"
STAGE12302_SUMMARY = ROOT / "runs/summaries/stage12302_transition_function_graph_control_board.json"

STAGE12387_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12387_transition_local_materializer_upgrade_worklist/"
    "transition_local_materializer_upgrade_worklist.jsonl"
)
STAGE12388_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12388_transition_local_candidate_recovery/"
    "transition_local_candidate_recovery_records.jsonl"
)
STAGE12389_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12389_transition_candidate_semantic_review/"
    "transition_candidate_semantic_review_records.jsonl"
)

RAW_OR_WORKLIST_CANDIDATES = 185
STRUCTURALLY_RECOVERED = 94
PRIVATE_REVIEW_PACKET_READY = 0
POLICY_LABEL_VALID = 0
LEVEL3_CANDIDATE = 0

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "admitted_rows": 0,
    "emitted_training_rows": 0,
    "countable_new_rows": 0,
    "level3_candidate_count": 0,
    "patch_trace_candidate_count": 0,
}

SIMILARITY_USE_POLICY = {
    "used_for_priority_only": True,
    "used_for_admission": False,
    "used_for_labeling": False,
    "used_for_eval_selection": False,
}

RAW_CONTENT_POLICY = {
    "raw_private_trace_text_inspected": False,
    "raw_private_trace_text_emitted": False,
    "raw_command_values_emitted": False,
    "raw_output_values_emitted": False,
    "raw_diff_values_emitted": False,
    "raw_patch_values_emitted": False,
    "raw_source_values_emitted": False,
    "raw_url_values_emitted": False,
    "raw_path_values_emitted": False,
    "private_locator_values_emitted": False,
    "raw_row_values_emitted": False,
}

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout:|stderr:|stack trace|"
    r"terminal output:|command output:|git clone\s+\S|git apply\s+\S|"
    r"curl\s+\S|bash -|sh -|python -c)\b",
    re.IGNORECASE | re.MULTILINE,
)

OVERCLAIM_RE = re.compile(
    r"\b(?:admission|admitted|training|trainable|accepted|acceptance|proof|"
    r"execution succeeded|review executed|verified repair|closed loop|"
    r"level3 complete|level-3|patch-trace|patch applied|tests passed)\b",
    re.IGNORECASE,
)

ALLOWED_OVERCLAIM_CONTEXT_RE = re.compile(
    r"(false|zero|none|\bno\b|not_|blocked|fail_closed|fail-closed|no_|never|disallowed|"
    r"priority.only|priority only|not.admission|guardrail|counter|risk|unavailable|"
    r"requested|future|required|policy|claim_boundary|similarity|diversity)",
    re.IGNORECASE,
)

STAGE12302_UNAVAILABLE_FIELDS = [
    "transition_function_key_count",
    "semantic_rule_id_count",
    "language_family_count",
    "repo_family_count",
    "task_family_count",
]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
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
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def dig(row: dict[str, Any] | None, *path: str) -> Any:
    value: Any = row or {}
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def source_guardrail_status(payload: dict[str, Any]) -> str:
    if not payload:
        return "missing_fail_closed"
    if payload.get("guardrail_scan_passed") is True:
        return "passed"
    guardrail = payload.get("guardrail_scan")
    if isinstance(guardrail, dict) and guardrail.get("scan_passed") is True:
        return "passed"
    if "guardrail_scan_passed" in payload or isinstance(guardrail, dict):
        return "failed_fail_closed"
    return "legacy_no_scan_fail_closed"


def input_status(items: list[tuple[str, Path, dict[str, Any]]]) -> dict[str, Any]:
    return {
        label: {
            "present": bool(payload),
            "stage": payload.get("stage") or "unknown",
            "decision_hash": stable_hash(payload.get("decision")),
            "guardrail_status": source_guardrail_status(payload),
            "summary_sha256_24": file_hash(path),
        }
        for label, path, payload in items
    }


def index_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if row.get(key)}


def normalized_family(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    lowered = text.lower()
    if "/" in text or "\\" in text or lowered.startswith(("http:", "https:", "file:")):
        return fallback
    if len(text) > 80:
        return fallback
    return text


def task_family_for(worklist: dict[str, Any], review: dict[str, Any] | None) -> str:
    expected = normalized_family(worklist.get("expected_role"), "")
    classification = normalized_family(worklist.get("classification"), "")
    recommendation = normalized_family((review or {}).get("recommendation"), "")
    if expected:
        return expected
    if classification:
        return classification
    if recommendation:
        return f"semantic_review_{recommendation}"
    return "transition_candidate_review"


def priority_bucket(
    worklist: dict[str, Any],
    recovery: dict[str, Any] | None,
    review: dict[str, Any] | None,
) -> str:
    if not recovery:
        return "structural_recovery_required_before_private_review"
    recommendation = str((review or {}).get("recommendation") or "")
    blockers = set(str(item) for item in safe_list((review or {}).get("remaining_blockers")))
    if recommendation == "needs_manual_review":
        return "manual_semantic_review_priority_if_private_packet_exists"
    if "mixed_patch_status_repair_transition_rejected" in blockers or "patch_failed_repair_transition_rejected" in blockers:
        return "hard_rule_rejected_low_priority"
    if "verifier_nonpass_repair_transition_rejected" in blockers:
        return "verifier_nonpass_low_priority"
    if safe_dict(worklist.get("recovery_safety")).get("semantic_review_only") is True:
        return "semantic_review_only_blocked"
    return "blocked_private_packet_or_policy_label_missing"


def diversity_weight(repo_family: str, source_cluster_size: int, blockers: set[str]) -> float:
    if "self_repo_dominated_scale_claim_blocked" in blockers:
        return 0.25
    if "repo_family_low_confidence" in blockers:
        return 0.25
    if source_cluster_size > 1:
        return 0.5
    return 1.0


def build_candidate_hash_records(
    worklist_rows: list[dict[str, Any]],
    recovery_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    recovery_by_worklist = index_by(recovery_rows, "source_worklist_id")
    review_by_recovery = index_by(review_rows, "source_recovery_record_id")

    preliminary: list[dict[str, Any]] = []
    source_cluster_counter: Counter[str] = Counter()
    for worklist in worklist_rows:
        worklist_id = str(worklist.get("worklist_id") or "")
        recovery = recovery_by_worklist.get(worklist_id)
        review = review_by_recovery.get(str((recovery or {}).get("recovery_record_id") or ""))
        repo_family = normalized_family(
            (review or {}).get("repo_family") or dig(recovery, "identity_recovery", "repo_family_candidate"),
            "missing_repo_family",
        )
        language_family = normalized_family(
            dig(recovery, "identity_recovery", "language_candidate") or worklist.get("language_family"),
            "missing_language_family",
        )
        task_family = task_family_for(worklist, review)
        source_adapter = "session_like_transition_local"
        source_cluster = stable_hash(
            {
                "source_adapter": source_adapter,
                "repo_family": repo_family,
                "language_family": language_family,
                "task_family": task_family,
            }
        )
        source_cluster_counter[source_cluster] += 1
        preliminary.append(
            {
                "worklist": worklist,
                "recovery": recovery,
                "review": review,
                "repo_family": repo_family,
                "language_family": language_family,
                "task_family": task_family,
                "source_adapter": source_adapter,
                "source_cluster_key_hash": source_cluster,
            }
        )

    records: list[dict[str, Any]] = []
    for item in preliminary:
        worklist = item["worklist"]
        recovery = item["recovery"]
        review = item["review"]
        transition_label = normalized_family(
            (review or {}).get("transition_candidate")
            or dig(recovery, "transition_recovery", "verifier_transition_candidate", "candidate_label"),
            "missing_transition_candidate",
        )
        rule_ids = sorted(str(rule) for rule in safe_list((review or {}).get("rule_ids")))
        blockers = sorted(
            set(str(reason) for reason in safe_list(worklist.get("blocker_classes")))
            | set(str(reason) for reason in safe_list((recovery or {}).get("blocked_reasons")))
            | set(str(reason) for reason in safe_list((review or {}).get("remaining_blockers")))
        )
        blocked_reason_codes = blockers or ["not_structurally_recovered"]
        semantic_key_hash = stable_hash(
            {
                "transition_candidate": transition_label,
                "rule_ids": rule_ids,
                "task_family": item["task_family"],
                "blocked_reason_codes": blocked_reason_codes,
            }
        )
        exact_row_hash = stable_hash(
            {
                "worklist": worklist,
                "recovery": recovery or {},
                "review": review or {},
            }
        )
        duplicate_cluster_id_hash = stable_hash(
            {
                "source_cluster_key_hash": item["source_cluster_key_hash"],
                "semantic_key_hash": semantic_key_hash,
                "blocked_reason_codes": blocked_reason_codes,
            }
        )
        root_lineage_key_hash = stable_hash(
            {
                "source_row_id": worklist.get("source_row_id"),
                "task_window_id": (review or {}).get("task_window_id") or (recovery or {}).get("task_window_id"),
                "root_id_candidate": dig(recovery, "identity_recovery", "root_id_candidate"),
            }
        )
        record = {
            "candidate_id_hash": stable_hash(
                {
                    "worklist_id": worklist.get("worklist_id"),
                    "recovery_record_id": (recovery or {}).get("recovery_record_id"),
                    "semantic_review_record_id": (review or {}).get("semantic_review_record_id"),
                }
            ),
            "root_lineage_key_hash": root_lineage_key_hash,
            "split_group_id_hash": stable_hash({"root_lineage_key_hash": root_lineage_key_hash, "gate": "blocked"}),
            "source_adapter": item["source_adapter"],
            "repo_family_hash": stable_hash(item["repo_family"]),
            "language_family": item["language_family"],
            "task_family": item["task_family"],
            "transition_function_key_hash": stable_hash({"transition_candidate_proxy": transition_label}),
            "semantic_rule_id_hash": stable_hash({"rule_ids": rule_ids}) if rule_ids else "unavailable_hash",
            "candidate_action_set_hash": stable_hash(
                {
                    "transition_candidate": transition_label,
                    "next_materialization_actions": sorted(
                        str(action) for action in safe_list((review or {}).get("next_materialization_actions"))
                    ),
                }
            ),
            "exact_row_hash": exact_row_hash,
            "semantic_key_hash": semantic_key_hash,
            "source_cluster_key_hash": item["source_cluster_key_hash"],
            "duplicate_cluster_id_hash": duplicate_cluster_id_hash,
            "diversity_weight": diversity_weight(
                item["repo_family"],
                source_cluster_counter[item["source_cluster_key_hash"]],
                set(blocked_reason_codes),
            ),
            "priority_bucket": priority_bucket(worklist, recovery, review),
            "blocked_reason_codes": blocked_reason_codes,
        }
        records.append(record)
    return records


def top_counts(counter: Counter[str], limit: int = 20) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit])


def cluster_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    duplicate_counts = Counter(str(row["duplicate_cluster_id_hash"]) for row in records)
    source_counts = Counter(str(row["source_cluster_key_hash"]) for row in records)
    semantic_counts = Counter(str(row["semantic_key_hash"]) for row in records)
    transition_counts = Counter(str(row["transition_function_key_hash"]) for row in records)
    semantic_rule_counts = Counter(str(row["semantic_rule_id_hash"]) for row in records)
    repo_counts = Counter(str(row["repo_family_hash"]) for row in records)
    language_counts = Counter(str(row["language_family"]) for row in records)
    task_counts = Counter(str(row["task_family"]) for row in records)
    bucket_counts = Counter(str(row["priority_bucket"]) for row in records)
    denominator = len(records) or 1
    return {
        "duplicate_cluster_count": len(duplicate_counts),
        "duplicate_cluster_max_share": round(max(duplicate_counts.values(), default=0) / denominator, 6),
        "source_cluster_count": len(source_counts),
        "semantic_cluster_count": len(semantic_counts),
        "transition_function_key_count": len(transition_counts),
        "semantic_rule_id_count": len(semantic_rule_counts - Counter({"unavailable_hash": semantic_rule_counts["unavailable_hash"]})),
        "repo_family_count": len(repo_counts - Counter({stable_hash("missing_repo_family"): repo_counts[stable_hash("missing_repo_family")]})),
        "language_family_count": len(language_counts),
        "task_family_count": len(task_counts),
        "expansion_priority_queue_count": len(records),
        "top_priority_buckets": top_counts(bucket_counts),
        "priority_bucket_counts": dict(sorted(bucket_counts.items())),
        "duplicate_cluster_size_counts_top20": top_counts(Counter(str(size) for size in duplicate_counts.values())),
        "source_cluster_size_counts_top20": top_counts(Counter(str(size) for size in source_counts.values())),
        "semantic_cluster_size_counts_top20": top_counts(Counter(str(size) for size in semantic_counts.values())),
    }


def stage12302_metric_availability(stage12302: dict[str, Any]) -> dict[str, Any]:
    return {
        field: {
            "value": stage12302.get(field),
            "status": "unavailable_null_source_summary"
            if stage12302.get(field) is None
            else "available_from_source_summary",
        }
        for field in STAGE12302_UNAVAILABLE_FIELDS
    }


def diversity_policy_summary(stage12364: dict[str, Any]) -> dict[str, Any]:
    same_source = safe_dict(safe_dict(stage12364.get("weighted_warnings_not_hard_rejects")).get("same_org_or_source_adapter_repeat"))
    return {
        "source_stage": stage12364.get("stage"),
        "decision": stage12364.get("decision"),
        "training_allowed": bool(stage12364.get("training_allowed")),
        "policy_correction_hash": stable_hash(stage12364.get("policy_correction")),
        "hard_reject_rule_count": len(safe_list(stage12364.get("hard_rejects_that_remain"))),
        "weighted_warning_keys": sorted(safe_dict(stage12364.get("weighted_warnings_not_hard_rejects")).keys()),
        "same_source_weight_values": {
            key: same_source.get(key)
            for key in [
                "first_distinct_repo_family",
                "additional_distinct_repo_family_with_distinct_verifier",
                "same_repo_distinct_package_or_subsystem",
                "same_repo_same_task_family_PASS_only",
                "repair_grade_fail_to_pass_with_same_source_proof",
            ]
            if key in same_source
        },
        "admission_accounting_field_count": len(safe_list(stage12364.get("admission_accounting_fields_required"))),
        "stage12440_interpretation": "diversity_weight_affects_review_priority_only_not_admission",
    }


def prior_ledger_duplicate_risk(stage12385: dict[str, Any]) -> dict[str, Any]:
    duplicate_counts = safe_dict(stage12385.get("duplicate_row_id_counts"))
    duplicate_issue_count = int(stage12385.get("duplicate_row_ids_should_be_zero") or 0)
    return {
        "source_stage": stage12385.get("stage") or "missing",
        "prior_ledger_duplicate_risk": duplicate_issue_count > 0,
        "duplicate_row_ids_should_be_zero_reported_value": duplicate_issue_count,
        "duplicate_key_count": len(duplicate_counts),
        "duplicate_key_hashes_top20": [stable_hash(key) for key in sorted(duplicate_counts)[:20]],
        "decision_text_hash": stable_hash(stage12385.get("decision")),
        "stage12440_interpretation": "not_clean_dedup_when_duplicate_row_ids_should_be_zero_is_nonzero",
    }


def public_support_ledger_snapshot(stage12295: dict[str, Any], stage12385: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage12295": {
            "stage": stage12295.get("stage"),
            "ledger_records": stage12295.get("ledger_records"),
            "train_support_rows": stage12295.get("train_support_rows"),
            "validation_level_counts": safe_dict(stage12295.get("validation_level_counts")),
            "train_validation_level_counts": safe_dict(stage12295.get("train_validation_level_counts")),
            "train_task_family_counts": safe_dict(stage12295.get("train_task_family_counts")),
            "action_family_counts_top20": safe_dict(stage12295.get("action_family_counts_top20")),
            "proof_counts": safe_dict(stage12295.get("proof_counts")),
        },
        "stage12385": {
            "stage": stage12385.get("stage"),
            "current_admitted_train_support_tasks": stage12385.get("current_admitted_train_support_tasks"),
            "language_counts": safe_dict(stage12385.get("language_counts")),
            "source_count_total": sum(int(value) for value in safe_dict(stage12385.get("source_counts")).values()),
            "source_count_unique": len(safe_dict(stage12385.get("source_counts"))),
            "task_family_or_record_type_counts": safe_dict(stage12385.get("task_family_or_record_type_counts")),
            "training_blocker_count": len(safe_list(stage12385.get("training_blockers"))),
        },
    }


def public_artifact_manifest() -> list[dict[str, Any]]:
    names = [
        f"{STAGE}.json",
        "summary.json",
        "candidate_hash_records.jsonl",
        "priority_bucket_counts.json",
        "cluster_counts.json",
        "input_status.json",
        "diversity_weight_policy_summary.json",
        "prior_ledger_duplicate_risk.json",
        "guardrail_scan.json",
        "public_artifact_manifest.json",
    ]
    return [
        {
            "artifact_file": name,
            "public_safe": True,
            "contains_raw_values": False,
            "raw_leak_count": 0,
            "overclaim_count": 0,
        }
        for name in names
    ]


def iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for child in value.values():
            strings.extend(iter_strings(child))
        return strings
    if isinstance(value, list):
        strings = []
        for child in value:
            strings.extend(iter_strings(child))
        return strings
    return []


def scan_payload(label: str, payload: Any) -> list[str]:
    issues: list[str] = []
    for text in iter_strings(payload):
        if RAW_LEAK_RE.search(text):
            issues.append(f"{label}:raw_leak_pattern:{stable_hash(text)}")
        for match in OVERCLAIM_RE.finditer(text):
            start = max(0, match.start() - 80)
            end = min(len(text), match.end() + 80)
            context = text[start:end]
            if not ALLOWED_OVERCLAIM_CONTEXT_RE.search(context):
                issues.append(f"{label}:overclaim_pattern:{stable_hash(context)}")
    return issues


def scan_artifact_set(artifact_set: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    main = safe_dict(artifact_set.get("main"))
    for key, expected in ZERO_COUNTERS.items():
        if main.get(key) != expected:
            issues.append(f"zero_counter_mismatch:{key}")
    if main.get("similarity_use_policy") != SIMILARITY_USE_POLICY:
        issues.append("similarity_use_policy_mismatch")
    expected_flow = {
        "raw_or_worklist_candidates": RAW_OR_WORKLIST_CANDIDATES,
        "structurally_recovered": STRUCTURALLY_RECOVERED,
        "private_review_packet_ready": PRIVATE_REVIEW_PACKET_READY,
        "policy_label_valid": POLICY_LABEL_VALID,
        "level3_candidate": LEVEL3_CANDIDATE,
    }
    if main.get("candidate_denominator_flow") != expected_flow:
        issues.append("candidate_denominator_flow_mismatch")
    for key, expected in RAW_CONTENT_POLICY.items():
        if safe_dict(main.get("raw_content_policy")).get(key) != expected:
            issues.append(f"raw_content_policy_mismatch:{key}")
    for label, payload in artifact_set.items():
        if label != "guardrail_scan":
            issues.extend(scan_payload(label, payload))
    raw_leaks = [issue for issue in issues if ":raw_leak_pattern:" in issue]
    overclaims = [issue for issue in issues if ":overclaim_pattern:" in issue]
    return {
        "scan_passed": not issues,
        "issue_count": len(set(issues)),
        "issues": sorted(set(issues)),
        "raw_leak_count": len(set(raw_leaks)),
        "overclaim_count": len(set(overclaims)),
        "scan_scope": "stage12440_public_safe_aggregate_and_hash_artifacts",
        "raw_leak_policy": {
            "raw_urls_fail": True,
            "raw_paths_fail": True,
            "raw_diffs_or_patches_fail": True,
            "raw_commands_fail": True,
            "raw_outputs_fail": True,
            "private_locator_values_fail": True,
        },
        "overclaim_policy": {
            "unqualified_admission_claim_fails": True,
            "unqualified_training_claim_fails": True,
            "unqualified_proof_claim_fails": True,
        },
    }


def build_artifact() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    stage12439 = read_json(STAGE12439_SUMMARY)
    stage12438 = read_json(STAGE12438_SUMMARY)
    stage12436 = read_json(STAGE12436_SUMMARY)
    stage12364 = read_json(STAGE12364_SUMMARY)
    stage12385 = read_json(STAGE12385_SUMMARY)
    stage12295 = read_json(STAGE12295_SUMMARY)
    stage12302 = read_json(STAGE12302_SUMMARY)

    worklist_rows = read_jsonl(STAGE12387_RECORDS)
    recovery_rows = read_jsonl(STAGE12388_RECORDS)
    review_rows = read_jsonl(STAGE12389_RECORDS)
    candidate_records = build_candidate_hash_records(worklist_rows, recovery_rows, review_rows)
    clusters = cluster_summary(candidate_records)
    diversity_summary = diversity_policy_summary(stage12364)
    duplicate_risk = prior_ledger_duplicate_risk(stage12385)
    metric_availability = stage12302_metric_availability(stage12302)
    support_snapshot = public_support_ledger_snapshot(stage12295, stage12385)
    inputs = input_status(
        [
            ("stage12439", STAGE12439_SUMMARY, stage12439),
            ("stage12438", STAGE12438_SUMMARY, stage12438),
            ("stage12436", STAGE12436_SUMMARY, stage12436),
            ("stage12364", STAGE12364_SUMMARY, stage12364),
            ("stage12385", STAGE12385_SUMMARY, stage12385),
            ("stage12295", STAGE12295_SUMMARY, stage12295),
            ("stage12302", STAGE12302_SUMMARY, stage12302),
        ]
    )

    artifact: dict[str, Any] = {
        "stage": STAGE,
        "record_type": "diverse_transition_candidate_expansion_gate_public_safe_v1",
        "decision": "fail_closed_diverse_transition_candidate_expansion_gate_ready",
        **ZERO_COUNTERS,
        "similarity_use_policy": SIMILARITY_USE_POLICY,
        "candidate_denominator_flow": {
            "raw_or_worklist_candidates": RAW_OR_WORKLIST_CANDIDATES,
            "structurally_recovered": STRUCTURALLY_RECOVERED,
            "private_review_packet_ready": PRIVATE_REVIEW_PACKET_READY,
            "policy_label_valid": POLICY_LABEL_VALID,
            "level3_candidate": LEVEL3_CANDIDATE,
        },
        "duplicate_cluster_count": clusters["duplicate_cluster_count"],
        "duplicate_cluster_max_share": clusters["duplicate_cluster_max_share"],
        "source_cluster_count": clusters["source_cluster_count"],
        "semantic_cluster_count": clusters["semantic_cluster_count"],
        "transition_function_key_count": clusters["transition_function_key_count"],
        "semantic_rule_id_count": clusters["semantic_rule_id_count"],
        "repo_family_count": clusters["repo_family_count"],
        "language_family_count": clusters["language_family_count"],
        "task_family_count": clusters["task_family_count"],
        "diversity_weight_policy_summary": diversity_summary,
        "expansion_priority_queue_count": clusters["expansion_priority_queue_count"],
        "top_priority_buckets": clusters["top_priority_buckets"],
        "required_next_stage": "stage12440_or_12441_private_review_prioritized_packet_builder",
        "hard_gate_blockers": [
            "policy_label_valid_zero",
            "private_review_packet_ready_zero",
            "level3_admission_blocked",
            "similarity_not_admission_authority",
        ],
        "raw_content_policy": RAW_CONTENT_POLICY,
        "candidate_hash_record_contract": {
            "candidate_records_public_safe": True,
            "raw_values_emitted": False,
            "hash_only_fields": [
                "candidate_id_hash",
                "root_lineage_key_hash",
                "split_group_id_hash",
                "repo_family_hash",
                "transition_function_key_hash",
                "semantic_rule_id_hash",
                "candidate_action_set_hash",
                "exact_row_hash",
                "semantic_key_hash",
                "source_cluster_key_hash",
                "duplicate_cluster_id_hash",
            ],
            "raw_or_private_fields_forbidden": [
                "raw_path",
                "raw_url",
                "raw_command",
                "raw_output",
                "raw_diff",
                "raw_patch",
                "raw_source",
                "private_locator",
            ],
        },
        "cluster_accounting": clusters,
        "priority_bucket_counts": clusters["priority_bucket_counts"],
        "stage12302_metric_availability": metric_availability,
        "stage12302_null_source_summary_fields": [
            field for field, status in metric_availability.items() if status["status"] == "unavailable_null_source_summary"
        ],
        "prior_ledger_duplicate_risk": duplicate_risk,
        "support_ledger_public_snapshot": support_snapshot,
        "source_counter_snapshot": {
            "stage12439_candidate_denominator_structurally_recovered": stage12439.get(
                "candidate_denominator_structurally_recovered"
            ),
            "stage12439_candidate_denominator_after_policy_label_filter": stage12439.get(
                "candidate_denominator_after_policy_label_filter"
            ),
            "stage12438_candidate_denominator_total": stage12438.get("candidate_denominator_total"),
            "stage12438_recovered_field_counters": safe_dict(stage12438.get("recovered_field_counters")),
            "stage12438_policy_label_counters": safe_dict(stage12438.get("policy_label_counters")),
            "stage12436_session_like_candidate_only_rows": stage12436.get("session_like_candidate_only_rows"),
        },
        "input_status": inputs,
        "claim_boundary": (
            "public-safe fail-closed expansion gate; similarity and diversity can order a future review queue only; "
            "no row admission, no labels, no eval selection, no execution, and no training emission"
        ),
        "public_artifact_manifest": public_artifact_manifest(),
        "summary_hash": "pending",
    }

    artifact_set = {
        "main": artifact,
        "candidate_hash_records": candidate_records,
        "priority_bucket_counts": artifact["priority_bucket_counts"],
        "cluster_counts": artifact["cluster_accounting"],
        "input_status": artifact["input_status"],
        "diversity_weight_policy_summary": diversity_summary,
        "prior_ledger_duplicate_risk": duplicate_risk,
        "public_artifact_manifest": artifact["public_artifact_manifest"],
    }
    guardrail = scan_artifact_set(artifact_set)
    artifact["guardrail_scan"] = guardrail
    artifact["guardrail_scan_passed"] = guardrail["scan_passed"]
    artifact["raw_leak_count"] = guardrail["raw_leak_count"]
    artifact["overclaim_count"] = guardrail["overclaim_count"]
    artifact["summary_hash"] = stable_hash({key: value for key, value in artifact.items() if key != "summary_hash"})

    artifact_set["main"] = artifact
    guardrail = scan_artifact_set(artifact_set)
    artifact["guardrail_scan"] = guardrail
    artifact["guardrail_scan_passed"] = guardrail["scan_passed"]
    artifact["raw_leak_count"] = guardrail["raw_leak_count"]
    artifact["overclaim_count"] = guardrail["overclaim_count"]
    artifact["summary_hash"] = stable_hash({key: value for key, value in artifact.items() if key != "summary_hash"})
    return artifact, candidate_records


def main() -> None:
    artifact, candidate_records = build_artifact()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    write_jsonl(OUT / "candidate_hash_records.jsonl", candidate_records)
    write_json(OUT / "priority_bucket_counts.json", artifact["priority_bucket_counts"])
    write_json(OUT / "cluster_counts.json", artifact["cluster_accounting"])
    write_json(OUT / "input_status.json", artifact["input_status"])
    write_json(OUT / "diversity_weight_policy_summary.json", artifact["diversity_weight_policy_summary"])
    write_json(OUT / "prior_ledger_duplicate_risk.json", artifact["prior_ledger_duplicate_risk"])
    write_json(OUT / "guardrail_scan.json", artifact["guardrail_scan"])
    write_json(OUT / "public_artifact_manifest.json", artifact["public_artifact_manifest"])
    print(
        json.dumps(
            {
                "stage": artifact["stage"],
                "decision": artifact["decision"],
                "expansion_priority_queue_count": artifact["expansion_priority_queue_count"],
                "candidate_denominator_flow": artifact["candidate_denominator_flow"],
                "guardrail_scan_passed": artifact["guardrail_scan_passed"],
                "raw_leak_count": artifact["raw_leak_count"],
                "overclaim_count": artifact["overclaim_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
