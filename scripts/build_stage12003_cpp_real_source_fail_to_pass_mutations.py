#!/usr/bin/env python3
"""Create C++ benchmark real-source FAIL_TO_PASS transition rows with restore guards."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12003_cpp_real_source_fail_to_pass_mutations")
ROWS = ROOT / "cpp_real_source_fail_to_pass_rows.jsonl"
SUMMARY = ROOT / "cpp_real_source_fail_to_pass_mutations.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12003_cpp_real_source_fail_to_pass_mutations.json")
LABELS = list("ABCDEFGH")
REPO = Path("/data/repositories/benchmark")

SPECS = [
    {
        "id": "benchmark_check_cc_diagnostics_compile_guard",
        "source_file": "src/check.cc",
        "build_dir": "/data/tmp/stage11876_benchmark_extra_build",
        "targets": ["diagnostics_test"],
        "ctest_regex": "^(diagnostics_test)$",
        "selected_verifier_path": "diagnostics_test via cmake --build + ctest",
    },
    {
        "id": "benchmark_commandlineflags_min_time_compile_guard",
        "source_file": "src/commandlineflags.cc",
        "build_dir": "/data/tmp/stage11876_benchmark_extra_build",
        "targets": ["benchmark_min_time_flag_time_test"],
        "ctest_regex": "^(min_time_flag_time)$",
        "selected_verifier_path": "min_time_flag_time via cmake --build + ctest",
    },
    {
        "id": "benchmark_register_filter_compile_guard",
        "source_file": "src/benchmark_register.cc",
        "build_dir": "/data/tmp/stage11872_benchmark_build",
        "targets": ["filter_test"],
        "ctest_regex": "^(filter_simple|filter_regex_all)$",
        "selected_verifier_path": "filter_simple/filter_regex_all via cmake --build + ctest",
    },
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def run(cmd: list[str], cwd: Path, name: str) -> dict[str, Any]:
    env = os.environ.copy()
    env.update({"CUDA_VISIBLE_DEVICES": "", "NVIDIA_VISIBLE_DEVICES": "", "TMPDIR": "/data/tmp", "TMP": "/data/tmp", "TEMP": "/data/tmp"})
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=90, check=False)
        payload = {"command": cmd, "cwd": str(cwd), "returncode": proc.returncode, "timed_out": False, "duration_sec": round(time.time() - started, 3), "stdout_tail": (proc.stdout or "")[-4000:], "stderr_tail": (proc.stderr or "")[-4000:]}
    except subprocess.TimeoutExpired as exc:
        payload = {"command": cmd, "cwd": str(cwd), "returncode": 124, "timed_out": True, "duration_sec": round(time.time() - started, 3), "stdout_tail": exc.stdout if isinstance(exc.stdout, str) else "", "stderr_tail": exc.stderr if isinstance(exc.stderr, str) else ""}
    log = ROOT / "logs" / f"{name}.json"
    write_json(log, payload)
    payload["log_path"] = str(log)
    return payload


def run_build_and_ctest(spec: dict[str, Any], phase: str) -> dict[str, Any]:
    build_dir = Path(spec["build_dir"])
    build_cmd = ["cmake", "--build", str(build_dir), "--target", *spec["targets"], "-j2"]
    test_cmd = ["ctest", "--test-dir", str(build_dir), "-R", spec["ctest_regex"], "--output-on-failure"]
    build = run(build_cmd, REPO, f"{spec['id']}_{phase}_build")
    execute = run(test_cmd, REPO, f"{spec['id']}_{phase}_ctest") if build["returncode"] == 0 and not build["timed_out"] else None
    return {"build": build, "execute": execute}


def phase_pass(phase: dict[str, Any]) -> bool:
    build = phase.get("build") or {}
    execute = phase.get("execute") or {}
    text = (execute.get("stdout_tail") or "") + "\n" + (execute.get("stderr_tail") or "")
    return build.get("returncode") == 0 and not build.get("timed_out") and execute.get("returncode") == 0 and "100% tests passed" in text


def phase_fail(phase: dict[str, Any]) -> bool:
    build = phase.get("build") or {}
    execute = phase.get("execute") or {}
    return build.get("returncode") not in (0, None) or build.get("timed_out") or (execute and execute.get("returncode") not in (0, None))


def options(row_id: str) -> list[dict[str, str]]:
    vals = [
        ("FAIL_TO_PASS", "baseline passed, controlled C++ source mutation failed verifier, restored source passed"),
        ("PASS_CURRENT_BUILD_AND_RUN", "build and runnable CTest verifier both passed without mutation failure"),
        ("PASS_TO_PASS", "focused verifier passed but paired build/mutation evidence is absent"),
        ("PASS_CURRENT_BUILD", "build passed but runnable verifier body did not execute"),
        ("NOT_EXERCISED", "command did not exercise or collect selected verifier"),
        ("INSUFFICIENT_EVIDENCE", "environment is underhydrated, so no trustworthy transition is available"),
        ("FAIL_TO_FAIL", "baseline already failed before mutation"),
        ("VERIFIER_REMOVED", "verifier evidence was removed and row should abstain"),
    ]
    keyed = [(hashlib.sha256(f"{row_id}::{i}::{v}".encode()).hexdigest(), v, text) for i, (v, text) in enumerate(vals)]
    return [{"label": label, "canonical_value": value, "value": value, "text": text, "role": "verifier_transition_status", "artifact_type": "cpp_controlled_mutation_status"} for label, (_, value, text) in zip(LABELS, sorted(keyed))]


def make_row(spec: dict[str, Any], baseline: dict[str, Any], mutant: dict[str, Any], restored: dict[str, Any]) -> dict[str, Any]:
    row_id = f"stage12003::benchmark::{spec['id']}"
    opts = options(row_id)
    target_label = next(o["label"] for o in opts if o["canonical_value"] == "FAIL_TO_PASS")
    prompt = "\n".join([
        "Language: c_cpp",
        "Perspective: transition_verifier_transition",
        "Task: choose the verifier transition proven by baseline, controlled C++ source mutation, and restored-source evidence.",
        "Repository family: benchmark",
        f"Source root: {REPO}",
        f"Source file mutated: {spec['source_file']}",
        f"Selected verifier: {spec['selected_verifier_path']}",
        f"Baseline build rc: {baseline['build']['returncode']} ctest rc: {(baseline.get('execute') or {}).get('returncode')} tail: {((baseline.get('execute') or {}).get('stdout_tail') or baseline['build'].get('stderr_tail') or '')[-700:]}",
        f"Mutant build rc: {mutant['build']['returncode']} ctest rc: {(mutant.get('execute') or {}).get('returncode')} tail: {(mutant['build'].get('stderr_tail') or mutant['build'].get('stdout_tail') or '')[-700:]}",
        f"Restored build rc: {restored['build']['returncode']} ctest rc: {(restored.get('execute') or {}).get('returncode')} tail: {((restored.get('execute') or {}).get('stdout_tail') or restored['build'].get('stderr_tail') or '')[-700:]}",
        "Options:",
        *[f"{o['label']}. {o['text']}" for o in opts],
        "Answer:",
    ])
    return {
        "row_id": row_id,
        "root_id": row_id,
        "root_lineage_key": f"stage12003::benchmark::{spec['source_file']}::{spec['ctest_regex']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": "benchmark",
        "repo_family": "benchmark",
        "language_family": "c_cpp",
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12003_cpp_real_source_fail_to_pass_train_support_only",
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
        "target": {"bounded_choice_target_label": target_label, "decoder_text": target_label, "semantic_value": "FAIL_TO_PASS"},
        "opaque_options": opts,
        "observed_verifier_transition": "FAIL_TO_PASS",
        "anti_cheat": {"deterministic_option_shuffle": True, "target_label_not_visible_before_options": True, "target_value_not_visible_before_options": True, "singleton_options": False, "restore_guarded_original_source": True, "train_support_only": True},
        "standalone_projection_source": {"projection_mode": "stage12003_cpp_real_source_fail_to_pass_mutations", "selected_verifier_path": spec["selected_verifier_path"], "source_file": spec["source_file"], "mutation_kind": "cpp_compile_error", "observed_verifier_transition": "FAIL_TO_PASS", "tool_or_verifier_observation": {"baseline": baseline, "mutant": mutant, "restored": restored}},
    }


def run_spec(spec: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    src = REPO / spec["source_file"]
    original = src.read_text()
    baseline = mutant = restored = {}
    restored_matches = False
    mutation_applied = False
    try:
        baseline = run_build_and_ctest(spec, "baseline")
        src.write_text(original + "\nint __stage12003_forced_compile_error( {\n")
        mutation_applied = True
        mutant = run_build_and_ctest(spec, "mutant")
    finally:
        src.write_text(original)
        restored_matches = src.read_text() == original
    restored = run_build_and_ctest(spec, "restored")
    admitted = mutation_applied and restored_matches and phase_pass(baseline) and phase_fail(mutant) and phase_pass(restored)
    card = {"spec": spec, "mutation_applied": mutation_applied, "restored_matches_original": restored_matches, "baseline_pass": phase_pass(baseline), "mutant_failed": phase_fail(mutant), "restored_pass": phase_pass(restored), "admitted": admitted, "baseline": baseline, "mutant": mutant, "restored": restored}
    return (make_row(spec, baseline, mutant, restored) if admitted else None), card


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    rows = []
    cards = []
    for spec in SPECS:
        row, card = run_spec(spec)
        cards.append(card)
        if row:
            rows.append(row)
    write_jsonl(ROWS, rows)
    summary = {
        "stage": "stage12003_cpp_real_source_fail_to_pass_mutations",
        "created_at_utc": now(),
        "rows_path": str(ROWS),
        "rows_attempted": len(SPECS),
        "admitted_rows": len(rows),
        "language_counts": dict(Counter(r["language_family"] for r in rows)),
        "repo_family_counts": dict(Counter(r["repo_family"] for r in rows)),
        "status_counts": dict(Counter(r["observed_verifier_transition"] for r in rows)),
        "probe_cards": cards,
        "decision": "admit_cpp_real_source_fail_to_pass_train_support" if rows else "no_cpp_fail_to_pass_rows_admitted",
        "claim_boundary": "Real local benchmark source mutation with baseline/mutant/restored build+CTest evidence; train-support only, one repo family.",
        "next_stage_recommendation": {"stage": "stage12004_transition_support_rollup_v9", "action": "Merge C++ FAIL_TO_PASS rows and report remaining floors."},
    }
    write_json(SUMMARY, summary)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps({k: summary[k] for k in ["decision", "admitted_rows", "language_counts", "status_counts", "next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
