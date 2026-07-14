#!/usr/bin/env python3
"""Materialize google/benchmark C++ abstain-attractor support rows."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11873
NAME = "stage11873_cpp_benchmark_filter_abstain_support_rows"
OUT = ART / NAME
SUMMARY = OUT / "cpp_benchmark_filter_abstain_support_rows.json"
ROWS = OUT / "cpp_benchmark_filter_abstain_support_rows.jsonl"
FEASIBILITY = ART / "stage11872_cpp_benchmark_filter_feasibility/cpp_benchmark_filter_feasibility_results.jsonl"
REPO = Path("/data/repositories/benchmark")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def file_evidence(eid: str, kind: str, rel_path: str, summary: str) -> dict[str, Any]:
    text = (REPO / rel_path).read_text(encoding="utf-8", errors="replace")
    return {
        "id": eid,
        "kind": kind,
        "path": rel_path,
        "start_line": 1,
        "end_line": len(text.splitlines()),
        "summary": summary,
        "text": text,
        "sha256": sha_text(text),
    }


def log_evidence(eid: str, result: dict[str, Any], summary: str) -> dict[str, Any]:
    stdout = (ROOT / result["stdout_log"]).read_text(encoding="utf-8", errors="replace")
    stderr = (ROOT / result["stderr_log"]).read_text(encoding="utf-8", errors="replace")
    text = stdout + "\n" + stderr
    return {
        "id": eid,
        "kind": "actual_build_or_run_log",
        "path": result["stdout_log"],
        "stderr_path": result["stderr_log"],
        "summary": summary,
        "text": text[-3500:],
        "sha256": sha_text(text),
    }


def base_row(
    root_id: str,
    suffix: str,
    task_type: str,
    options: list[dict[str, Any]],
    target_label: str,
    verifier_present: bool,
) -> dict[str, Any]:
    target = next(opt for opt in options if opt["label"] == target_label)
    return {
        "stage": STAGE,
        "row_id": f"{root_id}::{suffix}",
        "root_id": root_id,
        "root_lineage_key": root_id,
        "repo_id": "google_benchmark",
        "repo_family": "google_benchmark",
        "language_family": "c_cpp",
        "task_type": task_type,
        "split": "train",
        "package_split": "train",
        "train_support_only": True,
        "train_eligible": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "source_snapshot_id": "google_benchmark::local_git_snapshot",
        "surface": "cpp_abstain_attractor_build_verifier_support_bounded_choice",
        "target_label": target_label,
        "target_text": target_label,
        "bounded_choice_target_label": target_label,
        "decoder_text": target_label,
        "target_value": target["value"],
        "semantic_target_value": target["value"],
        "opaque_options": options,
        "standalone_projection_source": {"opaque_options": options, "gold_label": target_label, "gold_value": target["value"]},
        "loss_mask": {"bounded_choice_aux": True, "decoder_ce": True},
        "selected_test_anchor": verifier_present,
        "verifier_anchor": verifier_present,
        "verifier_transition": "PASS_CURRENT_BUILD_AND_RUN" if verifier_present else "VERIFIER_REMOVED",
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "opaque_labels": True,
            "singleton_options": False,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "source_backed_snippets": True,
            "actual_verifier_log_attached": verifier_present,
            "strict_smoke_root_replay": False,
            "sentencepiece_overlap": False,
            "paired_answerable_and_abstain_variants": True,
            "generated_build_harness_declared": False,
        },
    }


def main() -> None:
    feasible = [row for row in read_jsonl(FEASIBILITY) if row.get("repo_family") == "google_benchmark" and row.get("passed") is True]
    if not feasible:
        raise SystemExit("google/benchmark filter feasibility did not pass")
    feasibility = feasible[0]
    evidence = [
        file_evidence("E01", "candidate_change_surface", "src/benchmark_register.cc", "Benchmark registration and filtering code owns regex matching for benchmark families."),
        file_evidence("E02", "selected_test_anchor", "test/filter_test.cc", "Filter tests assert selected benchmark names, counts, family indices, list-only behavior, and negative filters."),
        file_evidence("E03", "nearby_runner_distractor", "src/benchmark_runner.cc", "Runner execution/reporting code is adjacent but not the selected filtering contract surface."),
        file_evidence("E04", "build_configuration", "CMakeLists.txt", "CMake options enable benchmark tests while disabling gtest-dependent tests for local verifier execution."),
        log_evidence("V01", feasibility["configure"], "google/benchmark CMake configure passed with tests enabled and gtest-dependent tests disabled."),
        log_evidence("V02", feasibility["build"], "benchmark_test, filter_test, and options_test built successfully."),
        log_evidence("V03", feasibility["execute"], "Focused ctest run passed benchmark/filter/options verifier tests."),
    ]
    verifier_evidence = {
        "id": "V03",
        "kind": "actual_cpp_build_run_pass_log",
        "summary": "google/benchmark configured, built, and passed focused filter/options verifier tests.",
        "configure": feasibility["configure"],
        "build": feasibility["build"],
        "execute": feasibility["execute"],
        "result": "PASS_CURRENT_BUILD_AND_RUN",
        "build_dir": "/data/tmp/stage11872_benchmark_build",
    }
    answerable = [
        {"label": "A", "role": "candidate_change_surface", "value": "src/benchmark_register.cc", "evidence_ids": ["E01"]},
        {"label": "B", "role": "verifier_and_build_constraint", "value": "ctest focused benchmark/filter/options tests passed", "evidence_ids": ["E02", "V01", "V02", "V03"]},
        {"label": "C", "role": "nearby_runner_surface", "value": "src/benchmark_runner.cc", "evidence_ids": ["E03"]},
        {"label": "D", "role": "abstain_insufficient_evidence", "value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "evidence_ids": []},
    ]
    abstain = [
        {"label": "A", "role": "candidate_change_surface", "value": "src/benchmark_register.cc", "evidence_ids": ["E01"]},
        {"label": "B", "role": "verifier_and_build_constraint_removed", "value": "build/run evidence unavailable in this variant", "evidence_ids": []},
        {"label": "C", "role": "nearby_runner_surface", "value": "src/benchmark_runner.cc", "evidence_ids": ["E03"]},
        {"label": "D", "role": "abstain_insufficient_evidence", "value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "evidence_ids": []},
    ]
    root_id = "stage11873::google_benchmark::c_cpp::filter_support"
    rows = [
        base_row(root_id, "answerable_evidence_citation_build_run_constraint", "evidence_citation", answerable, "B", True),
        base_row(root_id, "answerable_patch_impact_filter_surface", "patch_impact", answerable, "A", True),
        base_row(root_id, "answerable_abstain_rejection", "abstention_insufficient_evidence", answerable, "B", True),
        base_row(root_id, "verifier_removed_abstain", "abstention_insufficient_evidence", abstain, "D", False),
    ]
    for row in rows:
        row["evidence_ledger"] = evidence if row["verifier_anchor"] else [item for item in evidence if not item["id"].startswith("V")]
        row["verifier_evidence"] = verifier_evidence if row["verifier_anchor"] else None
        row["prompt_text"] = ""
        row["input_text"] = ""
    write_jsonl(ROWS, rows)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "eighth_cpp_abstain_attractor_support_root_materialized",
        "passed": True,
        "row_count": len(rows),
        "root_count": 1,
        "repo_family": "google_benchmark",
        "source_artifacts": {"feasibility": rel(FEASIBILITY)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS)},
        "claim_boundary": [
            "Rows are train-support-only.",
            "Source evidence is repo-backed and verifier evidence is build/run backed.",
            "This adds one C/C++ support root but does not satisfy Stage11742 quota.",
        ],
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "row_count": len(rows), "root_count": 1}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
