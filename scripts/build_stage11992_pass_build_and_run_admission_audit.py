#!/usr/bin/env python3
"""Admit clean PASS_CURRENT_BUILD_AND_RUN transition rows from Stage11991."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path("runs/local/artifacts/stage11992_pass_build_and_run_admission_audit")
INPUT = Path(
    "runs/local/artifacts/stage11991_pass_build_and_run_transition_probe/"
    "pass_build_and_run_rows.jsonl"
)
ADMITTED = ROOT / "pass_build_and_run_admitted_rows.jsonl"
SUMMARY = ROOT / "pass_build_and_run_admission_audit.json"
SUMMARY_MIRROR = Path("runs/summaries/stage11992_pass_build_and_run_admission_audit.json")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def positive_test_count(row: dict) -> bool:
    src = row.get("standalone_projection_source") or {}
    test_obs = src.get("test_observation") or {}
    text = (test_obs.get("stdout_tail") or "") + "\n" + (test_obs.get("stderr_tail") or "")
    if "No tests were found" in text:
        return False
    positive_pass_counts = [int(match) for match in re.findall(r"(\d+) passed", text)]
    if any(count > 0 for count in positive_pass_counts):
        return True
    vitest_counts = [int(match) for match in re.findall(r"\|\s+(\d+) passed", text)]
    if any(count > 0 for count in vitest_counts):
        return True
    return False


def has_clean_observation(row: dict) -> tuple[bool, str | None]:
    if row.get("observed_verifier_transition") != "PASS_CURRENT_BUILD_AND_RUN":
        return False, "wrong_observed_verifier_transition"

    target = row.get("target") or {}
    if target.get("semantic_value") != "PASS_CURRENT_BUILD_AND_RUN":
        return False, "wrong_target_semantic_value"

    options = row.get("opaque_options") or []
    if len(options) < 2:
        return False, "singleton_or_missing_options"

    anti = row.get("anti_cheat") or {}
    if anti.get("deterministic_option_shuffle") is not True:
        return False, "deterministic_option_shuffle_not_asserted"

    src = row.get("standalone_projection_source") or {}
    build_obs = src.get("build_observation") or {}
    test_obs = src.get("test_observation") or {}
    if build_obs.get("returncode") != 0 or build_obs.get("timed_out"):
        return False, "build_not_clean"
    if test_obs.get("returncode") != 0 or test_obs.get("timed_out"):
        return False, "test_not_clean"
    if not positive_test_count(row):
        return False, "missing_positive_test_count"

    return True, None


def normalize(row: dict) -> dict:
    out = dict(row)
    out["split"] = "train"
    out["split_role"] = "stage11992_pass_build_and_run_train_support_only"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["source_heldout_admissible"] = False
    out["stage11992_admission"] = {
        "admitted": True,
        "reason": "clean_build_typecheck_plus_positive_test_execution",
        "source_stage": "stage11991",
    }
    anti = dict(out.get("anti_cheat") or {})
    anti.update(
        {
            "review_queue_only": False,
            "not_merged_into_train": False,
            "deterministic_option_shuffle": True,
            "singleton_options": False,
            "target_label_not_visible_before_options": True,
        }
    )
    out["anti_cheat"] = anti
    return out


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)

    rows = read_jsonl(INPUT)
    admitted: list[dict] = []
    rejected: list[dict] = []
    reject_reasons: Counter[str] = Counter()

    seen_roots: set[str] = set()
    for row in rows:
        ok, reason = has_clean_observation(row)
        root = row.get("root_lineage_key") or row.get("root_id")
        if ok and root in seen_roots:
            ok, reason = False, "duplicate_root_lineage_key"
        if ok:
            seen_roots.add(root)
            admitted.append(normalize(row))
        else:
            reason = reason or "unknown_rejection"
            reject_reasons[reason] += 1
            rejected.append({"row_id": row.get("row_id"), "reason": reason})

    write_jsonl(ADMITTED, admitted)

    summary = {
        "stage": "stage11992_pass_build_and_run_admission_audit",
        "input_path": str(INPUT),
        "admitted_rows_path": str(ADMITTED),
        "rows_reviewed": len(rows),
        "admitted_rows": len(admitted),
        "rejected_rows": len(rejected),
        "reject_reasons": dict(sorted(reject_reasons.items())),
        "language_counts": dict(Counter(row.get("language_family") for row in admitted)),
        "repo_family_counts": dict(Counter(row.get("repo_family") for row in admitted)),
        "status_counts": dict(Counter(row.get("observed_verifier_transition") for row in admitted)),
        "unique_roots": len({row.get("root_lineage_key") or row.get("root_id") for row in admitted}),
        "decision": (
            "admit_pass_build_and_run_train_support"
            if admitted
            else "no_admitted_pass_build_and_run_rows"
        ),
        "next_stage_recommendation": {
            "stage": "stage11993_transition_support_rollup_v4",
            "action": "Merge admitted PASS_CURRENT_BUILD_AND_RUN rows into support inventory; do not train until root/status floors improve.",
        },
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    SUMMARY_MIRROR.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
