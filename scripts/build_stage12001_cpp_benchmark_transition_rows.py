#!/usr/bin/env python3
"""Convert prior C++ benchmark feasibility results into transition support rows."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12001_cpp_benchmark_transition_rows")
INPUTS = [
    Path("runs/local/artifacts/stage11872_cpp_benchmark_filter_feasibility/cpp_benchmark_filter_feasibility_results.jsonl"),
    Path("runs/local/artifacts/stage11876_cpp_benchmark_extra_feasibility/cpp_benchmark_extra_feasibility_results.jsonl"),
]
ROWS = ROOT / "cpp_benchmark_transition_rows.jsonl"
SUMMARY = ROOT / "cpp_benchmark_transition_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12001_cpp_benchmark_transition_rows.json")
LABELS = list("ABCDEFGH")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists(): return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def test_count(execute: dict[str, Any]) -> int:
    text = (execute.get("stdout_tail") or "") + "\n" + (execute.get("stderr_tail") or "")
    m = re.search(r"100% tests passed, 0 tests failed out of (\d+)", text)
    if m:
        return int(m.group(1))
    nums = [int(x) for x in re.findall(r"\b(\d+)/(\d+) Test", text)]
    return max(nums) if nums else 0


def clean(row: dict[str, Any]) -> tuple[bool, str | None]:
    for field in ["configure", "build", "execute"]:
        obs = row.get(field) or {}
        if obs.get("returncode") != 0 or obs.get("passed") is not True:
            return False, f"{field}_not_clean"
    if test_count(row.get("execute") or {}) <= 0:
        return False, "missing_positive_ctest_count"
    return True, None


def options(row_id: str) -> list[dict[str, str]]:
    values = [
        ("PASS_CURRENT_BUILD_AND_RUN", "build/configure completed and runnable CTest verifier passed"),
        ("PASS_TO_PASS", "focused verifier passed, but no paired build evidence is provided"),
        ("PASS_CURRENT_BUILD", "build/configure passed but no runnable verifier test body executed"),
        ("FAIL_TO_PASS", "controlled mutation failed and restored source passed"),
        ("NOT_EXERCISED", "command did not exercise or collect the selected verifier"),
        ("INSUFFICIENT_EVIDENCE", "environment is underhydrated so no trustworthy transition is available"),
        ("FAIL_TO_FAIL", "verifier failed in the current local source state"),
        ("VERIFIER_REMOVED", "verifier evidence was removed and the row should abstain"),
    ]
    keyed = [(hashlib.sha256(f"{row_id}::{i}::{v}".encode()).hexdigest(), v, text) for i, (v, text) in enumerate(values)]
    return [{"label": label, "canonical_value": v, "value": v, "text": text, "role": "verifier_transition_status", "artifact_type": "cpp_build_and_ctest_status"} for label, (_, v, text) in zip(LABELS, sorted(keyed))]


def make_row(src: dict[str, Any], source_name: str, idx: int) -> dict[str, Any]:
    root_key = src.get("root_key") or src.get("selected_test") or f"filter_{idx}"
    row_id = f"stage12001::benchmark::{root_key}::{hashlib.sha1((src.get('source_path','') + source_name).encode()).hexdigest()[:10]}"
    opts = options(row_id)
    target_label = next(o["label"] for o in opts if o["canonical_value"] == "PASS_CURRENT_BUILD_AND_RUN")
    execute = src.get("execute") or {}
    build = src.get("build") or {}
    configure = src.get("configure") or {}
    count = test_count(execute)
    prompt = "\n".join([
        "Language: c_cpp",
        "Perspective: transition_verifier_transition",
        "Task: choose the verifier transition supported by configure/build/CTest evidence.",
        "Repository family: benchmark",
        f"Root key: {root_key}",
        f"Source path: {src.get('source_path')}",
        f"Selected verifier: {src.get('selected_test') or execute.get('command')}",
        f"Configure rc: {configure.get('returncode')} tail: {(configure.get('stdout_tail') or configure.get('stderr_tail') or '')[-500:]}",
        f"Build rc: {build.get('returncode')} tail: {(build.get('stdout_tail') or build.get('stderr_tail') or '')[-500:]}",
        f"CTest rc: {execute.get('returncode')} observed test count: {count} tail: {(execute.get('stdout_tail') or execute.get('stderr_tail') or '')[-700:]}",
        "Options:",
        *[f"{o['label']}. {o['text']}" for o in opts],
        "Answer:",
    ])
    return {
        "row_id": row_id,
        "root_id": row_id,
        "root_lineage_key": f"stage12001::benchmark::{root_key}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": "benchmark",
        "repo_family": "benchmark",
        "language_family": "c_cpp",
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12001_cpp_benchmark_train_support_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "selected_test_anchor": True,
        "verifier_anchor": True,
        "input_text": prompt,
        "prompt_text": prompt,
        "target_text": target_label,
        "decoder_text": target_label,
        "bounded_choice_target_label": target_label,
        "target": {"bounded_choice_target_label": target_label, "decoder_text": target_label, "semantic_value": "PASS_CURRENT_BUILD_AND_RUN"},
        "opaque_options": opts,
        "observed_verifier_transition": "PASS_CURRENT_BUILD_AND_RUN",
        "anti_cheat": {"deterministic_option_shuffle": True, "target_label_not_visible_before_options": True, "target_value_not_visible_before_options": True, "singleton_options": False, "train_support_only": True},
        "standalone_projection_source": {"projection_mode": "stage12001_cpp_benchmark_transition_rows", "source_feasibility_stage": src.get("stage_name"), "selected_verifier_path": src.get("selected_test") or "ctest", "observed_test_count": count, "observed_verifier_transition": "PASS_CURRENT_BUILD_AND_RUN", "tool_or_verifier_observation": {"configure": configure, "build": build, "execute": execute}},
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    rows, rejected = [], []
    seen = set()
    for path in INPUTS:
        for idx, src in enumerate(read_jsonl(path)):
            ok, reason = clean(src)
            key = src.get("root_key") or src.get("selected_test") or f"{path.name}_{idx}"
            if ok and key in seen:
                ok, reason = False, "duplicate_root_key"
            if ok:
                seen.add(key)
                rows.append(make_row(src, path.name, idx))
            else:
                rejected.append({"source": str(path), "idx": idx, "reason": reason})
    write_jsonl(ROWS, rows)
    summary = {
        "stage": "stage12001_cpp_benchmark_transition_rows",
        "input_paths": [str(p) for p in INPUTS],
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "rejected_rows": len(rejected),
        "rejections": rejected,
        "language_counts": dict(Counter(r["language_family"] for r in rows)),
        "repo_family_counts": dict(Counter(r["repo_family"] for r in rows)),
        "status_counts": dict(Counter(r["observed_verifier_transition"] for r in rows)),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "decision": "admit_cpp_benchmark_build_and_run_train_support" if rows else "no_cpp_benchmark_rows_admitted",
        "claim_boundary": "C++ benchmark rows are train-support only from one repo family; not source-heldout frontier evidence.",
        "next_stage_recommendation": {"stage": "stage12002_transition_support_rollup_v8", "action": "Merge C++ benchmark build+CTest rows and report remaining floors."},
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__": main()
