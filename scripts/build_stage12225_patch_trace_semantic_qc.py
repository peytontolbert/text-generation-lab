#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12225_patch_trace_semantic_qc"
SRC = ROOT / "runs/local/artifacts/stage12224_patch_trace_training_rollup/patch_trace_train_support.jsonl"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if line:
                yield line_no, json.loads(line)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def before_output(row: dict[str, Any]) -> str:
    verifier = row.get("verifier_result") or {}
    before = verifier.get("before") or {}
    return (str(before.get("stdout_tail", "")) + "\n" + str(before.get("stderr_tail", ""))).lower()


def semantic_blockers(row: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    patch = row.get("patch_trace") or {}
    before = before_output(row)
    transition = row.get("verifier_transition")
    if transition == "FAIL_TO_PASS" and ("file or directory not found" in before or "no tests ran" in before):
        blockers.append("invalid_fail_to_pass_before_verifier_missing_test_or_no_tests")
    if transition == "FAIL_TO_PASS" and row.get("repo_family") == "mem0":
        blockers.append("mem0_patch_added_selected_test_before_command_not_comparable")
    if patch.get("counts_toward_fail_to_pass_floor") and blockers:
        blockers.append("remove_fail_to_pass_floor_credit")
    if transition not in {"FAIL_TO_PASS", "PASS_TO_PASS"}:
        blockers.append("unsupported_transition")
    return blockers


def main() -> int:
    admitted: list[dict[str, Any]] = []
    downgraded: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for line_no, row in iter_jsonl(SRC) or []:
        row = dict(row)
        blockers = semantic_blockers(row)
        if blockers:
            row["stage12225_semantic_blockers"] = blockers
            patch = dict(row.get("patch_trace") or {})
            patch["counts_toward_fail_to_pass_floor"] = False
            patch["counts_toward_patch_trace_floor"] = False
            patch["semantic_patch_validation_strength"] = "downgraded_before_verifier_not_comparable"
            row["patch_trace"] = patch
            row["verifier_transition_original"] = row.get("verifier_transition")
            row["verifier_transition"] = "TEST_ADDED_OR_VERIFIER_NOT_COMPARABLE"
            row["training_allowed"] = False
            downgraded.append(row)
            continue
        if row.get("patch_trace", {}).get("counts_toward_patch_trace_floor"):
            admitted.append(row)
        else:
            row["stage12225_semantic_blockers"] = ["not_patch_trace_floor_after_qc"]
            blocked.append(row)

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "admitted_patch_trace_train_support_after_semantic_qc.jsonl", admitted)
    write_jsonl(OUT / "downgraded_patch_trace_records.jsonl", downgraded)
    write_jsonl(OUT / "blocked_patch_trace_records.jsonl", blocked)
    summary = {
        "stage": STAGE,
        "source_stage": "stage12224_patch_trace_training_rollup",
        "decision": "semantic_qc_complete",
        "admitted_count": len(admitted),
        "downgraded_count": len(downgraded),
        "blocked_count": len(blocked),
        "patch_trace_floor_count": sum(1 for r in admitted if r.get("patch_trace", {}).get("counts_toward_patch_trace_floor")),
        "fail_to_pass_floor_count": sum(1 for r in admitted if r.get("patch_trace", {}).get("counts_toward_fail_to_pass_floor")),
        "transition_counts": dict(Counter(str(r.get("verifier_transition")) for r in admitted)),
        "downgraded_transition_counts": dict(Counter(str(r.get("verifier_transition_original") or r.get("verifier_transition")) for r in downgraded)),
        "repo_family_counts": dict(Counter(str(r.get("repo_family")) for r in admitted)),
        "downgraded_repo_family_counts": dict(Counter(str(r.get("repo_family")) for r in downgraded)),
        "training_allowed": False,
        "claim_boundary": "Semantic QC corrected Stage12224. Rows where before verifier failed because the selected test did not exist are not fail-to-pass proof and do not count toward patch-trace floor.",
        "artifact_paths": {
            "admitted": str(OUT / "admitted_patch_trace_train_support_after_semantic_qc.jsonl"),
            "downgraded": str(OUT / "downgraded_patch_trace_records.jsonl"),
            "blocked": str(OUT / "blocked_patch_trace_records.jsonl"),
        },
    }
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
