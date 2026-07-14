#!/usr/bin/env python3
"""Admission audit for Stage11985 second-batch transition-root probes."""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11986
NAME = "stage11986_transition_root_250_second_batch_admission_audit"
OUT = ART / NAME
SUMMARY = OUT / "transition_root_250_second_batch_admission_audit.json"
ADMITTED = OUT / "transition_root_250_second_batch_admitted_rows.jsonl"
REJECTED = OUT / "transition_root_250_second_batch_rejected_rows.jsonl"
SOURCE = ART / "stage11985_transition_root_250_second_batch_probe/transition_root_250_second_batch_review_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def observation(row: dict[str, Any]) -> dict[str, Any]:
    return ((row.get("standalone_projection_source") or {}).get("tool_or_verifier_observation") or {})


def command_kind(row: dict[str, Any]) -> str:
    rid = str(row.get("row_id") or "")
    for kind in ["cargo_check", "cargo_test", "npm_check", "npm_typecheck", "npm_test", "cmake_configure", "cmake_build", "ctest"]:
        if f"::{kind}::" in rid:
            return kind
    cmd = observation(row).get("command") or []
    return " ".join(cmd[:2])


def test_count(text: str) -> int | None:
    total = 0
    found = False
    for match in re.finditer(r"(\d+)\s+passed", text):
        found = True
        total += int(match.group(1))
    if found:
        return total
    match = re.search(r"(\d+)\s+tests?\s+collected", text)
    if match:
        return int(match.group(1))
    return None


def reject_reason(row: dict[str, Any]) -> str | None:
    status = str(row.get("observed_verifier_transition") or "")
    obs = observation(row)
    stdout = str(obs.get("stdout_tail") or "")
    stderr = str(obs.get("stderr_tail") or "")
    text = stdout + "\n" + stderr
    kind = command_kind(row)
    if row.get("repo_family") == "rust_zero_timeout":
        return "controlled_fixture_duplicate_existing_stage11980"
    if obs.get("returncode") != 0 or obs.get("timed_out"):
        return f"nonzero_or_timeout::{status}"
    if status == "PASS_TO_PASS":
        if "no tests were found" in text.lower():
            return "pass_to_pass_without_tests_ctest_empty"
        count = test_count(text)
        if count is not None and count <= 0:
            return "pass_to_pass_without_executed_tests"
        if kind in {"cargo_test", "npm_test", "ctest"} and count is None and "test result" not in text.lower() and "passed" not in text.lower():
            return "pass_to_pass_missing_test_count_evidence"
    elif status == "PASS_CURRENT_BUILD":
        if kind not in {"cargo_check", "cmake_configure", "cmake_build", "npm_check", "npm_typecheck"}:
            return f"pass_current_build_unexpected_kind::{kind}"
    else:
        return f"status_not_admitted_for_training::{status}"
    options = ((row.get("standalone_projection_source") or {}).get("opaque_options") or row.get("opaque_options") or [])
    if len(options) < 2:
        return "singleton_or_missing_options"
    anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    if anti.get("deterministic_option_shuffle") is not True:
        return "missing_deterministic_option_shuffle"
    if not row.get("bounded_choice_target_label"):
        return "missing_target_label"
    return None


def admit(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["split"] = "train"
    out["split_role"] = "stage11986_admitted_train_support_only"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["source_heldout_admissible"] = False
    out["stage11986_admission"] = {
        "admitted": True,
        "admission_role": "transition_root_250_second_batch_train_support_only",
        "not_promotable_eval": True,
        "reason": "local_source_command_observed_with_nonleaky_bounded_options",
    }
    return out


def main() -> None:
    rows = read_jsonl(SOURCE)
    admitted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in rows:
        reason = reject_reason(row)
        if reason is None:
            admitted.append(admit(row))
        else:
            bad = dict(row)
            bad["stage11986_rejection_reason"] = reason
            rejected.append(bad)
    write_jsonl(ADMITTED, admitted)
    write_jsonl(REJECTED, rejected)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "second_batch_admission_complete_train_support_only" if admitted else "second_batch_admission_complete_no_trainable_rows",
        "claim_boundary": "Rows are train-support-only; not source-heldout, not strict eval, not a frontier claim.",
        "source_artifact": rel(SOURCE),
        "summary": {
            "review_rows": len(rows),
            "admitted_rows": len(admitted),
            "rejected_rows": len(rejected),
            "admitted_language_counts": dict(Counter(r.get("language_family") for r in admitted)),
            "admitted_status_counts": dict(Counter(r.get("observed_verifier_transition") for r in admitted)),
            "admitted_repo_family_counts": dict(Counter(r.get("repo_family") for r in admitted)),
            "rejection_reasons": dict(Counter(r.get("stage11986_rejection_reason") for r in rejected)),
            "unique_admitted_roots": len({r.get("root_lineage_key") for r in admitted}),
        },
        "quality_notes": [
            "PASS_TO_PASS rows with zero tests or ctest no-test output are rejected.",
            "Controlled fixture rediscovery is rejected as duplicate support, not fresh root supply.",
            "Web rows did not admit in this batch because local package scripts were underhydrated or failed before verifier execution.",
        ],
        "outputs": {"summary": rel(SUMMARY), "admitted": rel(ADMITTED), "rejected": rel(REJECTED)},
        "next_stage_recommendation": {
            "stage": "stage11987_transition_support_rollup_v2",
            "action": "Merge Stage11981 and Stage11986 admitted train-support rows, report remaining floors, but do not train unless the package has enough root/status breadth or is explicitly diagnostic.",
        },
    }
    write_json(SUMMARY, summary)
    print(json.dumps({"decision": summary["decision"], "summary": summary["summary"], "next": summary["next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
