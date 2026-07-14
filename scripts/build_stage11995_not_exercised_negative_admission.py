#!/usr/bin/env python3
"""Convert clean zero-test/no-test observations into NOT_EXERCISED transition support."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path("runs/local/artifacts/stage11995_not_exercised_negative_admission")
INPUT = Path("runs/local/artifacts/stage11986_transition_root_250_second_batch_admission_audit/transition_root_250_second_batch_rejected_rows.jsonl")
ADMITTED = ROOT / "not_exercised_admitted_rows.jsonl"
REJECTED = ROOT / "not_exercised_rejected_rows.jsonl"
SUMMARY = ROOT / "not_exercised_negative_admission.json"
SUMMARY_MIRROR = Path("runs/summaries/stage11995_not_exercised_negative_admission.json")
CONVERTIBLE_REASONS = {"pass_to_pass_without_executed_tests", "pass_to_pass_without_tests_ctest_empty"}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def root_key(row: dict) -> str | None:
    return row.get("root_lineage_key") or row.get("root_id") or row.get("source_root_id") or row.get("source_bundle_id") or row.get("row_id")


def obs(row: dict) -> dict:
    src = row.get("standalone_projection_source") or {}
    return src.get("tool_or_verifier_observation") or src.get("test_observation") or src.get("build_observation") or {}


def has_zero_test_evidence(row: dict) -> bool:
    o = obs(row)
    text = (o.get("stdout_tail") or "") + "\n" + (o.get("stderr_tail") or "")
    return "running 0 tests" in text or "0 passed" in text or "No tests were found" in text or "0 tests" in text


def clean_successful_no_test(row: dict) -> tuple[bool, str | None]:
    reason = row.get("stage11986_rejection_reason")
    if reason not in CONVERTIBLE_REASONS:
        return False, "not_convertible_rejection_reason"
    o = obs(row)
    if o.get("returncode") != 0 or o.get("timed_out"):
        return False, "observation_not_successful"
    if not has_zero_test_evidence(row):
        return False, "missing_zero_test_evidence"
    options = row.get("opaque_options") or []
    labels = [opt.get("label") for opt in options if opt.get("canonical_value") == "NOT_EXERCISED" or opt.get("value") == "NOT_EXERCISED"]
    if not labels:
        return False, "missing_not_exercised_option"
    if len(options) < 2:
        return False, "singleton_or_missing_options"
    anti = row.get("anti_cheat") or {}
    if anti.get("deterministic_option_shuffle") is not True:
        return False, "shuffle_not_asserted"
    return True, None


def retarget(row: dict) -> dict:
    out = dict(row)
    options = out.get("opaque_options") or []
    target_label = next(opt.get("label") for opt in options if opt.get("canonical_value") == "NOT_EXERCISED" or opt.get("value") == "NOT_EXERCISED")
    out["observed_verifier_transition"] = "NOT_EXERCISED"
    out["bounded_choice_target_label"] = target_label
    out["decoder_text"] = target_label
    out["target_text"] = target_label
    out["target"] = {
        "bounded_choice_target_label": target_label,
        "decoder_text": target_label,
        "semantic_value": "NOT_EXERCISED",
    }
    src = dict(out.get("standalone_projection_source") or {})
    src["gold_label"] = target_label
    src["gold_value"] = "NOT_EXERCISED"
    src["observed_verifier_transition"] = "NOT_EXERCISED"
    src["projection_mode"] = "stage11995_clean_zero_test_not_exercised_negative_admission"
    out["standalone_projection_source"] = src
    out["row_id"] = out.get("row_id", "stage11995") + "::stage11995_not_exercised"
    out["root_id"] = (out.get("root_id") or "stage11995_root") + "::stage11995_not_exercised"
    out["source_root_id"] = out["root_id"]
    out["source_bundle_id"] = out["root_id"]
    out["split"] = "train"
    out["split_role"] = "stage11995_not_exercised_train_support_only"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["source_heldout_admissible"] = False
    out["stage11995_admission"] = {
        "admitted": True,
        "source_stage": "stage11986_rejected_rows",
        "reason": "successful_command_with_zero_or_no_tests_converted_to_not_exercised",
        "original_rejection_reason": row.get("stage11986_rejection_reason"),
    }
    anti = dict(out.get("anti_cheat") or {})
    anti.update({
        "review_queue_only": False,
        "not_merged_into_train": False,
        "deterministic_option_shuffle": True,
        "singleton_options": False,
        "target_label_not_visible_before_options": True,
        "target_value_not_visible_before_options": True,
    })
    out["anti_cheat"] = anti
    return out


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(INPUT)
    admitted, rejected = [], []
    reasons = Counter()
    seen = set()
    for row in rows:
        ok, reason = clean_successful_no_test(row)
        if ok:
            key = root_key(row)
            if key in seen:
                ok, reason = False, "duplicate_root_key"
            else:
                seen.add(key)
        if ok:
            admitted.append(retarget(row))
        else:
            reasons[reason or "unknown"] += 1
            rejected.append({"row_id": row.get("row_id"), "reason": reason or "unknown", "original_reason": row.get("stage11986_rejection_reason")})
    write_jsonl(ADMITTED, admitted)
    write_jsonl(REJECTED, rejected)
    summary = {
        "stage": "stage11995_not_exercised_negative_admission",
        "source": str(INPUT),
        "admitted_rows_path": str(ADMITTED),
        "rows_reviewed": len(rows),
        "admitted_rows": len(admitted),
        "rejected_rows": len(rejected),
        "rejection_reasons": dict(sorted(reasons.items())),
        "language_counts": dict(Counter(row.get("language_family") for row in admitted)),
        "repo_family_counts": dict(Counter(row.get("repo_family") for row in admitted)),
        "status_counts": dict(Counter(row.get("observed_verifier_transition") for row in admitted)),
        "unique_roots": len({root_key(row) for row in admitted}),
        "decision": "admit_clean_not_exercised_train_support" if admitted else "no_clean_not_exercised_rows",
        "claim_boundary": "Train-support negative verifier-status rows only; not strict/source-heldout and not a frontier training package.",
        "next_stage_recommendation": {"stage": "stage11996_transition_support_rollup_v5", "action": "Merge clean NOT_EXERCISED rows into support inventory and report remaining floors."},
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    SUMMARY_MIRROR.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
