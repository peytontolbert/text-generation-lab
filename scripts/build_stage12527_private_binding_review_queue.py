#!/usr/bin/env python3
"""Rank Stage12526 public-safe binding candidates for private review.

Stage12527 consumes only Stage12526 public-safe filename/metadata worklists and
prior blocker codes. It does not read candidate file contents, prove readiness,
write Stage12521 manifests, executor returns, Stage12516 candidates,
Stage12503 rows, training/admission material, Level-3 atoms, or patch-trace
material.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12527_private_binding_review_queue"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12526 = "stage12526_private_executor_binding_source_audit"
SLOT_COUNT = 343

ALLOWED_CLASSES = {
    "trusted_binding_candidate_name",
    "private_executor_config_candidate_name",
    "authorized_return_writer_candidate_name",
}
FALSE_GUARDS = {
    "readiness_fabricated": False,
    "stage12521_readiness_manifests_written": False,
    "candidate_returns_written": False,
    "validated_returns_written": False,
    "stage12516_candidate_rows_written": False,
    "stage12503_return_file_written": False,
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
    "raw_source_output_included": False,
    "raw_private_values_revealed": False,
    "candidate_file_contents_read": False,
    "candidate_raw_paths_emitted": False,
    "readiness_claimed": False,
}
ZERO_GUARDS = {
    "stage12521_readiness_manifest_count": 0,
    "candidate_return_records_written": 0,
    "validated_return_records_written": 0,
    "stage12516_candidate_row_count": 0,
    "stage12503_return_records_written": 0,
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level3_atom_count": 0,
    "patch_trace_admitted": 0,
    "patch_trace_rows": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
    "executor_return_records_written": 0,
}

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output|verifier output|commit:)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)
FORBIDDEN_PUBLIC_KEYS = {
    "raw",
    "raw_output",
    "raw_outputs",
    "raw_diff",
    "diff",
    "patch",
    "command",
    "commands",
    "cmd",
    "path",
    "paths",
    "file_path",
    "candidate_name",
    "candidate_ref_hash",
    "source_text",
    "source_content",
    "verifier_output",
    "stdout",
    "stderr",
    "terminal_output",
    "policy_label",
    "policy_label_hash",
    "training_row",
    "training_rows",
    "admitted_row",
    "level3_atom",
    "patch_trace",
    "proof_row",
}


class RawLeakError(ValueError):
    pass


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


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
        for key, child in value.items():
            if key in FORBIDDEN_PUBLIC_KEYS:
                issues.append(stable_hash({"forbidden_key": key}))
            issues.extend(scan_raw_leaks(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan_raw_leaks(child))
    return issues


def enforce_no_raw_leaks(value: Any) -> None:
    issues = scan_raw_leaks(value)
    if issues:
        raise RawLeakError(f"stage12527 raw leak guard rejected {len(issues)} public field(s)")


def prior_stage12526(root: Path) -> dict[str, Any]:
    artifacts = root / "runs/local/artifacts" / STAGE12526
    summaries = root / "runs/summaries"
    return {
        "summary": read_json(artifacts / "summary.json") or read_json(summaries / f"{STAGE12526}.json"),
        "worklist": read_jsonl(artifacts / "candidate_binding_source_worklist.jsonl"),
        "missing_checklist": read_jsonl(artifacts / "missing_binding_checklist.jsonl"),
    }


def prior_blocker_codes(stage12526: dict[str, Any]) -> list[str]:
    codes: set[str] = set()
    summary = stage12526["summary"]
    for code in summary.get("prior_blocker_codes") or []:
        codes.add(str(code))
    for row in stage12526["missing_checklist"]:
        code = row.get("missing_binding_code")
        if code:
            codes.add(str(code))
    if not codes:
        codes.update(
            [
                "trusted_ai_env_private_extractor_binding_missing",
                "no_authorized_stage12503_return_writer_configured",
            ]
        )
    return sorted(codes)


def slot_context(summary: dict[str, Any]) -> int:
    value = (
        summary.get("preserved_slot_count_context")
        or summary.get("stage12525_preserved_slot_identity_count")
        or summary.get("stage12525_manifest_slot_count_required")
    )
    return value if isinstance(value, int) and value > 0 else SLOT_COUNT


def classify_review(row: dict[str, Any]) -> str:
    classification = row.get("classification")
    if classification in ALLOWED_CLASSES:
        return str(classification)
    return "private_executor_config_candidate_name"


def rank_score(row: dict[str, Any], review_class: str) -> int:
    name = str(row.get("candidate_name") or "").lower()
    parent = str(row.get("candidate_parent_name") or "").lower()
    suffix = str(row.get("candidate_suffix") or "").lower()
    score = {
        "authorized_return_writer_candidate_name": 10_000,
        "trusted_binding_candidate_name": 8_000,
        "private_executor_config_candidate_name": 6_000,
    }.get(review_class, 1_000)
    if "authorized" in name and "writer" in name:
        score += 900
    if "stage12521" in name or "stage12521" in parent:
        score += 700
    if "stage12510" in name or "stage12510" in parent:
        score += 650
    if "stage12524" in name or "stage12525" in name or "stage12526" in name:
        score += 450
    if "executor" in name:
        score += 300
    if "binding" in name or "resolver" in name:
        score += 250
    if "config" in name or "manifest" in name or "contract" in name:
        score += 150
    if suffix == ".json":
        score += 30
    elif suffix == ".jsonl":
        score += 20
    return score


def review_band(rank: int, score: int, review_class: str) -> str:
    if review_class == "authorized_return_writer_candidate_name":
        return "p0_authorized_writer_binding_review"
    if rank <= 10 or score >= 8_500:
        return "p1_trusted_binding_review"
    if rank <= 30:
        return "p2_executor_config_review"
    return "p3_low_confidence_filename_metadata_review"


def queue_rows(stage12526: dict[str, Any]) -> list[dict[str, Any]]:
    ranked: list[tuple[int, dict[str, Any], str]] = []
    for row in stage12526["worklist"]:
        review_class = classify_review(row)
        ranked.append((rank_score(row, review_class), row, review_class))
    ranked.sort(
        key=lambda item: (
            -item[0],
            str(item[1].get("candidate_parent_name") or ""),
            str(item[1].get("candidate_suffix") or ""),
            str(item[1].get("candidate_binding_source_id_hash") or ""),
        )
    )

    rows: list[dict[str, Any]] = []
    for rank, (score, row, review_class) in enumerate(ranked, start=1):
        candidate_id = str(row.get("candidate_binding_source_id_hash") or stable_hash(row))
        output = {
            "record_type": "stage12527_public_safe_private_review_queue_item_v1",
            "private_review_packet_id_hash": stable_hash({"candidate_id": candidate_id, "rank": rank}),
            "priority_rank": rank,
            "priority_score": score,
            "review_band": review_band(rank, score, review_class),
            "candidate_binding_source_id_hash": candidate_id,
            "candidate_class": review_class,
            "candidate_parent_name": str(row.get("candidate_parent_name") or "unknown_parent"),
            "candidate_suffix": str(row.get("candidate_suffix") or ""),
            "preserved_slot_count_context": slot_context(stage12526["summary"]),
            "public_safe_metadata_only": True,
            "candidate_contents_read": False,
            "private_review_required": True,
            "readiness_claimed": False,
            "accept_criteria_ref": "stage12527_private_review_accept_criteria_v1",
            "reject_criteria_ref": "stage12527_private_review_reject_criteria_v1",
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(output)
        rows.append(output)
    return rows


def criteria_document() -> dict[str, Any]:
    criteria = {
        "record_type": "stage12527_private_review_criteria_v1",
        "claim_boundary": (
            "These criteria guide future private review only. Stage12527 does not inspect "
            "candidate contents and does not mark any candidate ready."
        ),
        "accept_criteria": [
            "private_reviewer_confirms_candidate_is_intended_for_trusted_executor_or_return_writer_binding",
            "private_reviewer_confirms_binding_authority_is_current_and_scope_limited_to_stage12521_stage12516_stage12503_flow",
            "private_reviewer_confirms_return_writer_destination_and_schema_are_authorized_without_public_value_exposure",
            "private_reviewer_confirms_candidate_maps_to_all_343_required_slot_context_or_documents_exact_gap",
            "private_reviewer_confirms_no_training_admission_level3_or_patch_trace_materialization_is_requested_by_candidate",
        ],
        "reject_criteria": [
            "candidate_is_only_historical_planning_or_readiness_language_without_executable_authority",
            "candidate_requires_public_disclosure_of_private_locator_values_source_contents_outputs_or_credentials",
            "candidate_targets_training_admission_level3_patch_trace_or_stage12516_stage12503_materialization_before_authorized_return_review",
            "candidate_does_not_identify_a_trusted_executor_binding_or_authorized_return_writer_in_private_context",
            "candidate_is_superseded_ambiguous_or_scope_expanded_beyond_private_executor_binding_review",
        ],
        "public_safe_metadata_only": True,
        "readiness_claimed": False,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(criteria)
    return criteria


def missing_review_rows(stage12526: dict[str, Any], codes: list[str]) -> list[dict[str, Any]]:
    if stage12526["worklist"]:
        return []
    rows: list[dict[str, Any]] = []
    for idx, code in enumerate(codes, start=1):
        row = {
            "record_type": "stage12527_missing_private_review_queue_checklist_item_v1",
            "missing_review_item_id_hash": stable_hash({"code": code, "idx": idx}),
            "missing_binding_code": code,
            "required_private_review_input": {
                "trusted_ai_env_private_extractor_binding_missing": "public_safe_candidate_for_trusted_binding_private_review",
                "trusted_ai_env_private_extractor_binding_env_unproven": "public_safe_candidate_for_executor_env_binding_private_review",
                "no_authorized_stage12503_return_writer_configured": "public_safe_candidate_for_authorized_return_writer_private_review",
            }.get(code, "public_safe_candidate_for_prior_blocker_private_review"),
            "preserved_slot_count_context": slot_context(stage12526["summary"]),
            "public_safe_metadata_only": True,
            "readiness_claimed": False,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(row)
        rows.append(row)
    return rows


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    out.mkdir(parents=True, exist_ok=True)

    stage12526 = prior_stage12526(root)
    enforce_no_raw_leaks(
        {
            "summary": stage12526["summary"],
            "missing_checklist": stage12526["missing_checklist"],
        }
    )
    queue = queue_rows(stage12526)
    codes = prior_blocker_codes(stage12526)
    missing = missing_review_rows(stage12526, codes)
    criteria = criteria_document()
    class_counts = Counter(row["candidate_class"] for row in queue)
    band_counts = Counter(row["review_band"] for row in queue)

    decision = (
        "public_safe_private_review_queue_emitted_no_readiness_claimed"
        if queue
        else "blocked_no_stage12526_candidates_missing_private_review_checklist_emitted"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12527_private_binding_review_queue_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12527 ranks Stage12526 candidate binding sources into public-safe private-review "
            "packets using filename metadata already emitted by Stage12526. It does not read candidate "
            "file contents, output raw references, claim readiness, write Stage12521 manifests, executor "
            "returns, Stage12516 candidates, Stage12503 rows, training/admission material, Level-3 atoms, "
            "or patch-trace material."
        ),
        "source_stage": STAGE12526,
        "input_candidate_binding_source_count": len(stage12526["worklist"]),
        "private_review_queue_count": len(queue),
        "missing_private_review_checklist_count": len(missing),
        "candidate_class_counts": dict(sorted(class_counts.items())),
        "review_band_counts": dict(sorted(band_counts.items())),
        "prior_blocker_codes": codes,
        "preserved_slot_count_context": slot_context(stage12526["summary"]),
        "accept_criteria_ref": "review_criteria.json#stage12527_private_review_accept_criteria_v1",
        "reject_criteria_ref": "review_criteria.json#stage12527_private_review_reject_criteria_v1",
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "next_stage": (
            "private_review_ranked_candidates_without_public_raw_leakage"
            if queue
            else "rerun_stage12526_after_public_safe_candidate_binding_sources_exist"
        ),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail = {
        "stage": STAGE,
        "scan_passed": True,
        "raw_leak_count": 0,
        "raw_leak_issue_hashes": [],
        "scanned_outputs": [
            "private_review_queue.jsonl",
            "missing_private_review_checklist.jsonl",
            "review_criteria.json",
            "summary.json",
        ],
    }
    enforce_no_raw_leaks({"summary": summary, "queue": queue, "missing": missing, "criteria": criteria, "guardrail": guardrail})
    write_jsonl(out / "private_review_queue.jsonl", queue)
    write_jsonl(out / "missing_private_review_checklist.jsonl", missing)
    write_json(out / "review_criteria.json", criteria)
    write_json(out / "guardrail_scan.json", guardrail)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()
