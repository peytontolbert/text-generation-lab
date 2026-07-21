#!/usr/bin/env python3
"""Define the direct Level-3 source hierarchy after Stage12452.

This stage is a control artifact only. It prevents overcounting derivative
rollups/projections as new roots and directs the next materializers to the
highest-value direct sources.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12453_direct_level3_source_hierarchy_and_next_lanes"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

SOURCES = {
    "stage12205_authoritative_verifier_log_level3_joiner": ROOT / "runs/local/artifacts/stage12205_authoritative_verifier_log_level3_joiner/authoritative_level3_episode_records.jsonl",
    "stage12210_controlled_triple_level3_joiner": ROOT / "runs/local/artifacts/stage12210_controlled_triple_level3_joiner/controlled_triple_level3_records.jsonl",
    "stage12216_normalized_verifier_observation_dataset": ROOT / "runs/local/artifacts/stage12216_normalized_verifier_observation_dataset/normalized_verifier_observation_records.jsonl",
    "stage12211_v35_buildrun_level3_converter": ROOT / "runs/local/artifacts/stage12211_v35_buildrun_level3_converter/v35_buildrun_level3_records.jsonl",
    "stage12212_v35_buildonly_level3_converter": ROOT / "runs/local/artifacts/stage12212_v35_buildonly_level3_converter/v35_buildonly_level3_records.jsonl",
    "stage12213_strict_fail_current_state_level3_converter": ROOT / "runs/local/artifacts/stage12213_strict_fail_current_state_level3_converter/strict_fail_current_state_level3_records.jsonl",
    "stage12421_new_direct_real_verifier_observation_miner": ROOT / "runs/local/artifacts/stage12421_new_direct_real_verifier_observation_miner/new_direct_verifier_observation_train_support_rows.jsonl",
}

DIRECT_PRIORITY = [
    "stage12205_authoritative_verifier_log_level3_joiner",
    "stage12210_controlled_triple_level3_joiner",
    "stage12204_hydratable_verifier_replay_batch",
]
DERIVATIVE_OR_AUXILIARY = {
    "stage12216_normalized_verifier_observation_dataset": "normalized_rollup_use_for_dedupe_and_canonical_status_not_incremental_supply",
    "stage12211_v35_buildrun_level3_converter": "converter_subset_likely_covered_by_normalized_rollup",
    "stage12212_v35_buildonly_level3_converter": "converter_subset_likely_covered_by_normalized_rollup",
    "stage12213_strict_fail_current_state_level3_converter": "tiny_converter_subset_use_only_if_lineage_not_in_direct_sources",
    "stage12421_new_direct_real_verifier_observation_miner": "public_safe_auxiliary_most_rows_controlled_fixture_only_count_new_rows_from_its_own_audit",
}

FORBIDDEN_PUBLIC_KEYS = {"path", "paths", "url", "urls", "uri", "command", "command_text", "commands", "stdout", "stderr", "output", "outputs", "diff", "patch", "patch_body", "source", "source_path", "source_text", "private_locator", "raw", "raw_text", "trace", "trace_text", "issue_body"}
ALLOWED_KEY_CONTEXT_RE = re.compile(r"(policy|emitted|forbidden|required|slot|slots|schema|hash|hashes|ref|refs|class|status|proof|reason|contract|request|count|scan|supply|stage|artifact|lane)", re.I)
RAW_LEAK_RE = re.compile(r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|\b(?:stdout:|stderr:|terminal output:|command output:|git clone\s+\S|git apply\s+\S|python -c|bash -)\b", re.I | re.M)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
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
    return hashlib.sha256(f"{STAGE}:{payload}".encode()).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
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
        for key, child in value.items():
            issues.extend(scan(f"{label}.{key}", child))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            issues.extend(scan(f"{label}[{idx}]", child))
    return issues


def source_signature(row: dict[str, Any]) -> str:
    parts = [
        row.get("episode_id"),
        row.get("root_id"),
        row.get("repo_family") or row.get("repo_id"),
        row.get("rollup_source_ref") or row.get("source_ref") or row.get("source_record_ref"),
        row.get("verifier_transition"),
    ]
    cr = row.get("command_result") if isinstance(row.get("command_result"), dict) else {}
    parts.extend([cr.get("command_result_id"), row.get("command_result_id"), row.get("observation_id")])
    return stable_hash(parts)


def summarize_source(stage: str, path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    roots = {str(row.get("root_id") or "") for row in rows if row.get("root_id")}
    languages = Counter(str(row.get("language") or row.get("language_family") or "unknown") for row in rows)
    statuses = Counter(str(row.get("verifier_transition") or row.get("verifier_status") or row.get("observation_status_class") or "unknown") for row in rows)
    signatures = {source_signature(row) for row in rows}
    direct_signature_fields = Counter()
    for row in rows:
        direct_signature_fields.update({
            "candidate_action_set": "candidate_action_set" in row,
            "command_result_or_observation": "command_result" in row or "command_result_id" in row or "observation_id" in row,
            "state_update_or_delta": "state_update" in row or "state_update_id" in row or "state_delta_codes" in row,
            "stop_decision_or_label": "stop_decision" in row or "stop_decision_id" in row or "stop_continue_label" in row,
        })
    return {
        "stage_class": stage,
        "artifact_path_hash": stable_hash(str(path.relative_to(ROOT))),
        "artifact_sha256_24": file_hash(path),
        "row_count": len(rows),
        "unique_root_count": len(roots),
        "unique_source_signature_count": len(signatures),
        "language_counts": dict(sorted(languages.items())),
        "verifier_transition_counts": dict(sorted(statuses.items())),
        "direct_signature_field_presence_counts": {str(k): int(v) for k, v in sorted(direct_signature_fields.items())},
        "source_role": "direct_priority" if stage in DIRECT_PRIORITY else "derivative_or_auxiliary",
        "derivative_reason": DERIVATIVE_OR_AUXILIARY.get(stage),
    }


def main() -> None:
    source_cards = [summarize_source(stage, path) for stage, path in SOURCES.items()]
    direct_rows = []
    for stage in ["stage12205_authoritative_verifier_log_level3_joiner", "stage12210_controlled_triple_level3_joiner"]:
        for row in read_jsonl(SOURCES[stage]):
            direct_rows.append((stage, source_signature(row), row))
    direct_unique = {sig for _stage, sig, _row in direct_rows}
    normalized_rows = read_jsonl(SOURCES["stage12216_normalized_verifier_observation_dataset"])
    normalized_signatures = {source_signature(row) for row in normalized_rows}
    lane_orders = [
        {
            "priority": 1,
            "lane": "authoritative_direct_verifier_log_wrap_stage12205",
            "source_stage": "stage12205_authoritative_verifier_log_level3_joiner",
            "expected_use": "wrap raw direct records into public-safe Stage12445-style return rows for verifier-transition and continue-stop support",
            "hard_bounds": ["no_raw_values", "no_repair_overclaim", "dedupe_by_source_signature", "training_eligible_false_at_return_gate"],
        },
        {
            "priority": 2,
            "lane": "controlled_triple_fail_to_pass_wrap_stage12210",
            "source_stage": "stage12210_controlled_triple_level3_joiner",
            "expected_use": "wrap controlled same-source before_fail_after_pass triples; count separately from external comparable repair",
            "hard_bounds": ["controlled_fixture_label_required", "semantic_not_syntax_only_breakdown_required", "no_external_fail_to_pass_claim_without source audit"],
        },
        {
            "priority": 3,
            "lane": "normalized_rollup_dedupe_only_stage12216",
            "source_stage": "stage12216_normalized_verifier_observation_dataset",
            "expected_use": "dedupe/canonical status accounting only unless source signature is absent from direct layers",
            "hard_bounds": ["do_not_double_count_derivatives", "do_not_use_sanitized_projection_as_state_stop_proof"],
        },
    ]
    artifact = {
        "stage": STAGE,
        "record_type": "direct_level3_source_hierarchy_and_next_lanes_v1",
        "decision": "direct_source_hierarchy_ready_next_wrap_stage12205_then_stage12210_training_blocked",
        "training_allowed": False,
        "admission_allowed": False,
        "execution_allowed": False,
        "emitted_training_rows": 0,
        "sealed_eval_rows_emitted": 0,
        "source_card_count": len(source_cards),
        "source_cards": source_cards,
        "direct_priority_unique_source_signature_count": len(direct_unique),
        "normalized_rollup_unique_source_signature_count": len(normalized_signatures),
        "normalized_overlap_with_direct_priority_signature_count": len(normalized_signatures & direct_unique),
        "next_lane_order_count": len(lane_orders),
        "next_lane_orders_path": "runs/local/artifacts/stage12453_direct_level3_source_hierarchy_and_next_lanes/next_lane_orders.jsonl",
        "hard_lessons": [
            "candidate discovery and rerenders are not training supply",
            "selected-test verifier observations are not repair proof",
            "derivative normalized rollups must not be counted in addition to direct source rows",
            "Stage12445 validates proof-complete public-safe return rows but keeps training disabled",
        ],
        "claim_boundary": "Control artifact only. It defines source hierarchy and next lanes; it emits no training rows and admits no rows.",
        "guardrail_scan": {},
        "guardrail_scan_passed": False,
        "raw_leak_count": 0,
        "schema_issue_count": 0,
        "summary_hash": "pending",
    }
    issues = scan("artifact", artifact) + scan("next_lane_orders", lane_orders)
    artifact["guardrail_scan"] = {
        "scan_passed": not issues,
        "issue_count": len(set(issues)),
        "issues": sorted(set(issues)),
        "raw_leak_count": len({i for i in issues if "raw_public_leak" in i or "forbidden_public_key" in i}),
        "scan_scope": "stage12453_public_safe_control_artifacts",
    }
    artifact["guardrail_scan_passed"] = artifact["guardrail_scan"]["scan_passed"]
    artifact["raw_leak_count"] = artifact["guardrail_scan"]["raw_leak_count"]
    artifact["summary_hash"] = stable_hash({k: v for k, v in artifact.items() if k != "summary_hash"})
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    write_jsonl(OUT / "source_cards.jsonl", source_cards)
    write_jsonl(OUT / "next_lane_orders.jsonl", lane_orders)
    print(json.dumps({
        "stage": artifact["stage"],
        "decision": artifact["decision"],
        "direct_priority_unique_source_signature_count": artifact["direct_priority_unique_source_signature_count"],
        "normalized_overlap_with_direct_priority_signature_count": artifact["normalized_overlap_with_direct_priority_signature_count"],
        "training_allowed": artifact["training_allowed"],
        "guardrail_scan_passed": artifact["guardrail_scan_passed"],
        "raw_leak_count": artifact["raw_leak_count"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
