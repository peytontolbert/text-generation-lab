#!/usr/bin/env python3
"""Build Stage12459 external comparable patch-effect source preflight.

This is a fail-closed public control artifact. It inventories source lanes by
stage refs only, emits no training rows, admits no rows, executes no tests, and
does not expose raw paths, URLs, commands, stdout/stderr, diffs, or tiny repo
identifiers.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12459_external_comparable_patch_effect_source_preflight"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

SUMMARY_REFS = {
    "stage12458": ROOT / "runs/summaries/stage12458_balance_and_external_repair_gate.json",
    "stage12392": ROOT
    / "runs/summaries/stage12392_raw_visible_review_packet_builder_or_external_root_pivot.json",
    "stage12327": ROOT / "runs/summaries/stage12327_external_adapter_preflight.json",
    "stage12328": ROOT / "runs/summaries/stage12328_external_adapter_qc_materialization_request.json",
    "stage12284": ROOT / "runs/summaries/stage12284_external_repair_commit_pair_preflight.json",
    "stage12285": ROOT / "runs/summaries/stage12285_external_repair_replay_executor_request.json",
    "stage12286": ROOT / "runs/summaries/stage12286_external_repair_replay_smoke_executor.json",
    "stage12287": ROOT / "runs/summaries/stage12287_external_repair_replay_second_smoke_request.json",
    "stage12288": ROOT / "runs/summaries/stage12288_external_repair_replay_second_smoke_executor.json",
    "stage12289": ROOT / "runs/summaries/stage12289_replay_failure_after_phase_diagnostic.json",
    "stage12290": ROOT / "runs/summaries/stage12290_replay_queue_repair_or_retarget_decision.json",
    "stage12449": ROOT
    / "runs/summaries/stage12449_external_repair_trace_fail_to_pass_projection.json",
}

ARTIFACT_REFS = {
    "stage12327_open_swe_priority": ROOT
    / "runs/local/artifacts/stage12327_external_adapter_preflight"
    / "open_swe_priority_capped_trace_support_candidates.jsonl",
    "stage12327_open_swe_all": ROOT
    / "runs/local/artifacts/stage12327_external_adapter_preflight"
    / "open_swe_trace_support_candidates.jsonl",
    "stage12327_bears_failing_passing": ROOT
    / "runs/local/artifacts/stage12327_external_adapter_preflight"
    / "bears_failing_passing_candidates.jsonl",
    "stage12327_bears_nonrepair": ROOT
    / "runs/local/artifacts/stage12327_external_adapter_preflight"
    / "bears_nonrepair_blocked_candidates.jsonl",
    "stage12284_ready": ROOT
    / "runs/local/artifacts/stage12284_external_repair_commit_pair_preflight"
    / "replay_ready_targets.jsonl",
    "stage12286_pe2": ROOT
    / "runs/local/artifacts/stage12286_external_repair_replay_smoke_executor"
    / "patch_effect_PE2_candidates.jsonl",
    "stage12288_pe2": ROOT
    / "runs/local/artifacts/stage12288_external_repair_replay_second_smoke_executor"
    / "patch_effect_PE2_candidates.jsonl",
    "stage12392_pivot_worklist": ROOT
    / "runs/local/artifacts/stage12392_raw_visible_review_packet_builder_or_external_root_pivot"
    / "external_root_private_review_packet_pivot_worklist.jsonl",
}

ZERO_GUARDS = {
    "external_comparable_repair_credit_count": 0,
    "external_fail_to_pass_remaining_floor_gap": 15,
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "emitted_training_rows": 0,
    "sealed_eval_rows": 0,
}

REQUIRED_REPAIR_PROOF_SLOTS = [
    "buggy_state_ref_hash",
    "fixed_or_patch_state_ref_hash",
    "patch_ref_hash",
    "same_source_verifier_identity_hash",
    "before_verifier_status_fail",
    "after_or_before_plus_patch_verifier_status_pass",
    "verifier_output_ref_hashes",
    "ordered_patch_effect_causality_ref",
    "anti_leak_public_rendering_pass",
]

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
    "patch_body",
    "raw_text",
    "source_text",
    "repo",
    "repo_id",
    "repo_name",
}
KEY_ALLOW_RE = re.compile(
    r"(policy|forbidden|required|slot|slots|hash|ref|refs|stage|lane|scan|"
    r"count|bucket|proof|identity|status|guardrail|reason|request|artifact)",
    re.I,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:stdout|stderr|traceback|command output|terminal output|git clone|"
    r"git apply|pytest\s|python -c|bash -|sh -|curl\s)\b",
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


def int_value(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    return default


def line_count(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def count_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    if count <= 4:
        return "2-4"
    if count <= 9:
        return "5-9"
    if count <= 24:
        return "10-24"
    if count <= 74:
        return "25-74"
    if count <= 249:
        return "75-249"
    return "250-plus"


def language_bucket(languages: Any) -> str:
    if not isinstance(languages, dict) or not languages:
        return "unknown_or_not_public"
    keys = {str(key).lower() for key in languages}
    if keys == {"java"}:
        return "single_jvm"
    if keys == {"python"}:
        return "single_python"
    if keys <= {"javascript", "typescript", "html", "web_js_ts_html"}:
        return "web_script"
    if len(keys & {"rust", "c", "cpp", "c++"}) > 0 and len(keys) <= 3:
        return "systems_mixed"
    if len(keys) >= 4:
        return "multilingual_mixed"
    return "small_language_mix"


def scan_public(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not KEY_ALLOW_RE.search(label):
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


def present_stage_refs(records: dict[str, dict[str, Any]], names: list[str]) -> list[str]:
    refs = []
    for name in names:
        record = records.get(name, {})
        if record or SUMMARY_REFS[name].exists():
            refs.append(str(record.get("stage") or SUMMARY_REFS[name].stem))
    return refs


def build_lane_inventory(
    summaries: dict[str, dict[str, Any]], counts: dict[str, int]
) -> list[dict[str, Any]]:
    stage12327 = summaries["stage12327"]
    stage12328 = summaries["stage12328"]
    stage12284 = summaries["stage12284"]
    stage12290 = summaries["stage12290"]
    stage12392 = summaries["stage12392"]

    open_swe = stage12327.get("open_swe_import_artifact", {})
    bears = stage12327.get("bears_inventory", {})
    source_preflight = stage12328.get("source_preflight", {})

    lanes = [
        {
            "lane_id": "lane_ref_bears_failing_passing_private_hydration",
            "rank": 1,
            "source_stage_refs": present_stage_refs(summaries, ["stage12327", "stage12328"]),
            "candidate_count_bucket": count_bucket(
                int_value(source_preflight.get("bears_failing_passing_candidates"))
                or counts["stage12327_bears_failing_passing"]
            ),
            "language_bucket": language_bucket(bears.get("language_counts")),
            "can_satisfy_external_repair_credit_if_hydrated": True,
            "missing_proof_slots": REQUIRED_REPAIR_PROOF_SLOTS,
        },
        {
            "lane_id": "lane_ref_external_root_private_review_pivot",
            "rank": 2,
            "source_stage_refs": present_stage_refs(summaries, ["stage12392"]),
            "candidate_count_bucket": count_bucket(
                int_value(stage12392.get("external_root_pivot_worklist_count"))
                or counts["stage12392_pivot_worklist"]
            ),
            "language_bucket": "unknown_or_not_public",
            "can_satisfy_external_repair_credit_if_hydrated": True,
            "missing_proof_slots": REQUIRED_REPAIR_PROOF_SLOTS,
        },
        {
            "lane_id": "lane_ref_open_swe_trace_support_private_qc",
            "rank": 3,
            "source_stage_refs": present_stage_refs(summaries, ["stage12327", "stage12328"]),
            "candidate_count_bucket": count_bucket(
                int_value(source_preflight.get("open_swe_priority_capped_candidates"))
                or int_value(open_swe.get("priority_capped_candidates"))
                or counts["stage12327_open_swe_priority"]
            ),
            "language_bucket": language_bucket(open_swe.get("priority_language_counts")),
            "can_satisfy_external_repair_credit_if_hydrated": False,
            "missing_proof_slots": [
                "independent_before_fail_after_pass_replay",
                "same_source_verifier_identity_hash",
                "patch_effect_causality_beyond_trace_co_presence",
                "anti_leak_public_rendering_pass",
            ],
        },
        {
            "lane_id": "lane_ref_commit_pair_retarget_after_pass_prefilter",
            "rank": 4,
            "source_stage_refs": present_stage_refs(
                summaries,
                [
                    "stage12284",
                    "stage12285",
                    "stage12286",
                    "stage12287",
                    "stage12288",
                    "stage12289",
                    "stage12290",
                ],
            ),
            "candidate_count_bucket": count_bucket(
                int_value(stage12284.get("preflight_ready_targets"))
                or counts["stage12284_ready"]
            ),
            "language_bucket": language_bucket(stage12284.get("ready_by_language")),
            "can_satisfy_external_repair_credit_if_hydrated": False,
            "missing_proof_slots": [
                "after_state_must_pass_exact_verifier",
                "before_state_must_fail_exact_verifier",
                "before_plus_patch_must_pass_exact_verifier",
                "same_verifier_identity_across_states",
                "environment_failure_separated_from_software_failure",
            ],
            "blocking_observation_ref": str(stage12290.get("stage") or "stage12290"),
        },
        {
            "lane_id": "lane_ref_stage12449_projection_repair_trace_returns",
            "rank": 5,
            "source_stage_refs": present_stage_refs(summaries, ["stage12449"]),
            "candidate_count_bucket": count_bucket(
                int_value(summaries["stage12449"].get("source_record_count"))
            ),
            "language_bucket": "unknown_or_not_public",
            "can_satisfy_external_repair_credit_if_hydrated": False,
            "missing_proof_slots": [
                "proof_complete_fail_to_pass_row",
                "before_verifier_runnable_or_authoritative",
                "transition_status_fail_to_pass_only",
                "policy_label_independence_proof",
            ],
        },
    ]
    return sorted(lanes, key=lambda row: int_value(row.get("rank"), 999))


def build_rejected_inventory(
    summaries: dict[str, dict[str, Any]], counts: dict[str, int]
) -> list[dict[str, Any]]:
    stage12449 = summaries["stage12449"]
    stage12290 = summaries["stage12290"]
    stage12458 = summaries["stage12458"]

    return [
        {
            "rejection_class": "controlled mutation",
            "source_stage_refs": present_stage_refs(summaries, ["stage12458"]),
            "candidate_count_bucket": count_bucket(
                int_value(stage12458.get("controlled_or_mutation_fail_to_pass_support_count"))
            ),
            "reason": "controlled_or_mutation_support_is_not_external_comparable_repair_proof",
        },
        {
            "rejection_class": "selected-test verifier observation",
            "source_stage_refs": present_stage_refs(summaries, ["stage12458"]),
            "candidate_count_bucket": count_bucket(
                int_value(stage12458.get("selected_test_verifier_observation_validated_delta"))
            ),
            "reason": "selected_test_observation_support_cannot_close_external_repair_credit_floor",
        },
        {
            "rejection_class": "PASS_TO_PASS",
            "source_stage_refs": present_stage_refs(summaries, ["stage12449"]),
            "candidate_count_bucket": count_bucket(
                int_value(
                    (
                        stage12449.get("input_transition_status_counts", {})
                        if isinstance(stage12449.get("input_transition_status_counts"), dict)
                        else {}
                    ).get("PASS_TO_PASS")
                )
            ),
            "reason": "pass_to_pass_is_not_fail_to_pass_patch_effect",
        },
        {
            "rejection_class": "co-presence-only",
            "source_stage_refs": present_stage_refs(summaries, ["stage12327", "stage12328"]),
            "candidate_count_bucket": count_bucket(counts["stage12327_open_swe_all"]),
            "reason": "patch_and_verifier_co_presence_without_replay_causality_is_insufficient",
        },
        {
            "rejection_class": "normalized verifier identity-only",
            "source_stage_refs": present_stage_refs(summaries, ["stage12290", "stage12449"]),
            "candidate_count_bucket": count_bucket(
                int_value(stage12290.get("targets_attempted_across_smoke"))
                + int_value(stage12449.get("blocked_record_count"))
            ),
            "reason": "verifier_identity_without_before_fail_and_after_pass_statuses_is_insufficient",
        },
    ]


def main() -> None:
    summaries = {name: read_json(path) for name, path in SUMMARY_REFS.items()}
    counts = {name: line_count(path) for name, path in ARTIFACT_REFS.items()}

    stage12458 = summaries["stage12458"]
    observed_gap = int_value(stage12458.get("external_fail_to_pass_remaining_floor_gap"))
    observed_credit = int_value(stage12458.get("external_comparable_repair_credit_count"))
    if observed_gap != ZERO_GUARDS["external_fail_to_pass_remaining_floor_gap"]:
        raise SystemExit(
            "fail_closed: upstream external fail-to-pass gap does not match required floor gap"
        )
    if observed_credit != ZERO_GUARDS["external_comparable_repair_credit_count"]:
        raise SystemExit("fail_closed: upstream external comparable repair credit is nonzero")

    source_lane_inventory = build_lane_inventory(summaries, counts)
    rejected_lane_inventory = build_rejected_inventory(summaries, counts)
    worklist_rows = [
        {
            "lane_id": row["lane_id"],
            "rank": row["rank"],
            "source_stage_refs": row["source_stage_refs"],
            "candidate_count_bucket": row["candidate_count_bucket"],
            "required_proof_slots_ref": "stage12459_required_repair_proof_slots_v1",
        }
        for row in source_lane_inventory
        if row["can_satisfy_external_repair_credit_if_hydrated"]
    ]

    summary: dict[str, Any] = {
        "stage": STAGE,
        "record_type": "external_comparable_patch_effect_source_preflight_public_safe_v1",
        "decision": "fail_closed_source_preflight_ready_for_private_proof_slot_materialization",
        "claim_boundary": (
            "Public-safe source-lane control only. No rows are admitted, no training rows "
            "are emitted, no tests are executed, and no sensitive locators, execution logs, "
            "change bodies, or exact tiny source identifiers are exposed."
        ),
        **ZERO_GUARDS,
        "source_lane_inventory": source_lane_inventory,
        "rejected_lane_inventory": rejected_lane_inventory,
        "next_execution_or_materialization_request": {
            "safe_next_stage_name": (
                "stage12460_external_comparable_patch_effect_private_proof_slot_materialization_request"
            ),
            "request_type": "private_proof_slot_materialization_only",
            "scope": "ranked_lane_refs_only_no_broad_mining",
            "required_proof_slots_ref": "stage12459_required_repair_proof_slots_v1",
            "required_proof_slots": REQUIRED_REPAIR_PROOF_SLOTS,
            "admission_after_next_stage_allowed": False,
            "training_after_next_stage_allowed": False,
            "minimum_success_condition": (
                "materialize at least external_fail_to_pass_remaining_floor_gap proof-complete "
                "FAIL_TO_PASS comparable patch-effect records in private artifacts before any "
                "later admission stage may request credit"
            ),
        },
        "source_fingerprint_hashes": {
            name: file_hash(path) for name, path in {**SUMMARY_REFS, **ARTIFACT_REFS}.items()
        },
        "worklist_artifact_ref": "stage12459_public_lane_ref_worklist_jsonl",
    }

    public_issues = scan_public("summary", summary)
    summary["guardrail_scan"] = {
        "scan_scope": "stage12459_public_summary_and_lane_ref_worklist",
        "scan_passed": not public_issues,
        "raw_leak_count": len(public_issues),
        "issues": public_issues,
    }
    summary["guardrail_scan_passed"] = not public_issues
    summary["raw_leak_count"] = len(public_issues)
    summary["summary_hash"] = stable_hash(
        {key: value for key, value in summary.items() if key != "summary_hash"}
    )

    # Re-scan after adding guardrail fields and hash; fail closed on any issue.
    final_issues = scan_public("summary", summary)
    if final_issues:
        summary["guardrail_scan"] = {
            "scan_scope": "stage12459_public_summary_and_lane_ref_worklist",
            "scan_passed": False,
            "raw_leak_count": len(final_issues),
            "issues": final_issues,
        }
        summary["guardrail_scan_passed"] = False
        summary["raw_leak_count"] = len(final_issues)
        write_json(OUT_DIR / "summary.json", summary)
        write_json(SUMMARY_OUT, summary)
        raise SystemExit("fail_closed: public guardrail scan detected leakage")

    write_jsonl(OUT_DIR / "public_lane_ref_worklist.jsonl", worklist_rows)
    write_json(OUT_DIR / "summary.json", summary)
    write_json(SUMMARY_OUT, summary)


if __name__ == "__main__":
    main()
