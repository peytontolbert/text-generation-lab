#!/usr/bin/env python3
"""Materialize final PASS_CURRENT_BUILD_AND_RUN floor-closure rows."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12045_buildrun_floor_closure_rows")
ROWS = ROOT / "buildrun_floor_closure_rows.jsonl"
SUMMARY = ROOT / "buildrun_floor_closure_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12045_buildrun_floor_closure_rows.json")
LABELS = list("ABCDEFGH")

OBSERVATIONS: list[dict[str, Any]] = [
    {"language_family": "python", "repo_family": "NousResearch__hermes-agent", "cwd": "/data/repositories/NousResearch__hermes-agent", "selected_verifier_path": "py_compile tests/test_utils_truthy_values.py + tests/test_utils_truthy_values.py", "command": "python -m py_compile /data/repositories/NousResearch__hermes-agent/tests/test_utils_truthy_values.py && python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12045_pytest_cache /data/repositories/NousResearch__hermes-agent/tests/test_utils_truthy_values.py", "stdout_tail": "py_compile completed; pytest reported 4 passed in 2.01s"},
    {"language_family": "python", "repo_family": "SWE-agent__SWE-ReX", "cwd": "/data/repositories/SWE-agent__SWE-ReX", "selected_verifier_path": "py_compile test_footer.py + test_footer.py", "command": "python -m py_compile /data/repositories/SWE-agent__SWE-ReX/test_footer.py && python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12045_pytest_cache /data/repositories/SWE-agent__SWE-ReX/test_footer.py", "stdout_tail": "py_compile completed; pytest reported 4 passed, 4 warnings in 0.31s"},
    {"language_family": "c_cpp", "repo_family": "sentencepiece", "cwd": "/data/repositories/sentencepiece", "selected_verifier_path": "sentencepiece-static build + sentencepiece_test", "command": "cmake --build /data/tmp/sentencepiece_stage11737_build --target sentencepiece-static -j2 && ctest --test-dir /data/tmp/sentencepiece_stage11737_build -R '^sentencepiece_test$' --output-on-failure", "stdout_tail": "Built target sentencepiece-static; CTest sentencepiece_test passed with 100% tests passed"},
    {"language_family": "rust", "repo_family": "tokenizers", "cwd": "/data/repositories/tokenizers", "selected_verifier_path": "cargo check fancy-regex + decoders::ctc::tests::handmade_sample", "command": "cargo check --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --features fancy-regex --quiet && cargo test --manifest-path /data/repositories/tokenizers/tokenizers/Cargo.toml --features fancy-regex decoders::ctc::tests::handmade_sample --quiet", "stdout_tail": "cargo check completed; cargo test ran 1 test and passed with 191 filtered out"},
    {"language_family": "python", "repo_family": "Python", "cwd": "/data/repositories/Python", "selected_verifier_path": "py_compile filters/gaussian_filter.py + digital_image_processing/test_digital_image_processing.py", "command": "python -m py_compile /data/repositories/Python/digital_image_processing/filters/gaussian_filter.py && python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12045_pytest_cache /data/repositories/Python/digital_image_processing/test_digital_image_processing.py", "stdout_tail": "py_compile completed; pytest reported 12 passed in 2.68s"},
    {"language_family": "python", "repo_family": "NousResearch__hermes-agent", "cwd": "/data/repositories/NousResearch__hermes-agent", "selected_verifier_path": "py_compile agent/retry_utils.py + tests/test_retry_utils.py", "command": "python -m py_compile /data/repositories/NousResearch__hermes-agent/agent/retry_utils.py && python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12045_pytest_cache /data/repositories/NousResearch__hermes-agent/tests/test_retry_utils.py", "stdout_tail": "py_compile completed; pytest reported 9 passed in 1.32s"},
    {"language_family": "web_js_ts_html", "repo_family": "modelcontextprotocol__typescript-sdk", "cwd": "/data/repositories/modelcontextprotocol__typescript-sdk", "selected_verifier_path": "@modelcontextprotocol/core typecheck + packages/core/test/shared/protocol.test.ts", "command": "pnpm --dir /data/repositories/modelcontextprotocol__typescript-sdk --filter @modelcontextprotocol/core run typecheck && ./node_modules/.bin/vitest run --globals packages/core/test/shared/protocol.test.ts", "stdout_tail": "typecheck completed; Vitest reported 1 file passed and 150 tests passed"},
    {"language_family": "web_js_ts_html", "repo_family": "modelcontextprotocol__typescript-sdk", "cwd": "/data/repositories/modelcontextprotocol__typescript-sdk", "selected_verifier_path": "@modelcontextprotocol/core typecheck + packages/core/test/shared/stdio.test.ts", "command": "pnpm --dir /data/repositories/modelcontextprotocol__typescript-sdk --filter @modelcontextprotocol/core run typecheck && ./node_modules/.bin/vitest run --globals packages/core/test/shared/stdio.test.ts", "stdout_tail": "typecheck completed; Vitest reported 1 file passed and 11 tests passed"},
]

REJECTED_PROBES = [
    {"repo_family": "Python", "command": "python -m py_compile /data/repositories/Python/digital_image_processing/edge_detection.py && pytest digital_image_processing/test_digital_image_processing.py", "returncode": 1, "reason": "compile path did not exist"},
    {"repo_family": "openclaw__clawhub", "command": "npm run typecheck -- --pretty false && vitest src/lib/numberFormat.test.ts", "returncode": 1, "reason": "package has no npm typecheck script"},
    {"repo_family": "openclaw__clawhub", "command": "npm run typecheck -- --pretty false && vitest convex/lib/searchText.test.ts", "returncode": 1, "reason": "package has no npm typecheck script"},
]

TRANSITION_TEXT = {
    "PASS_TO_PASS": "focused verifier executed from local source and passed",
    "PASS_CURRENT_BUILD_AND_RUN": "build and runnable verifier both passed",
    "PASS_CURRENT_BUILD": "build or collection passed but runnable verifier body did not execute",
    "FAIL_TO_PASS": "controlled broken state failed and restored or repaired source passed",
    "NOT_EXERCISED": "command did not exercise or collect the selected verifier",
    "INSUFFICIENT_EVIDENCE": "environment is underhydrated so no trustworthy transition is available",
    "FAIL_TO_FAIL": "verifier failed in the current local source state",
    "VERIFIER_REMOVED": "verifier evidence was removed and the row should abstain",
}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def options(row_id: str, language: str) -> list[dict[str, str]]:
    keyed = [(hashlib.sha256(f"{row_id}::{value}".encode()).hexdigest(), value, text) for value, text in TRANSITION_TEXT.items()]
    return [{"label": label, "canonical_value": value, "value": value, "text": text, "role": "verifier_transition_status", "artifact_type": f"{language}_verifier_status"} for label, (_, value, text) in zip(LABELS, sorted(keyed))]


def make_row(obs: dict[str, Any]) -> dict[str, Any]:
    semantic = "PASS_CURRENT_BUILD_AND_RUN"
    material = f"{obs['repo_family']}::{obs['selected_verifier_path']}::{semantic}"
    row_id = f"stage12045::{obs['repo_family']}::{hashlib.sha1(material.encode()).hexdigest()[:12]}::{semantic}"
    opts = options(row_id, obs["language_family"])
    target_label = next(o["label"] for o in opts if o["canonical_value"] == semantic)
    prompt = "\n".join([
        f"Language: {obs['language_family']}",
        "Perspective: transition_verifier_transition",
        "Task: choose the verifier transition supported by paired build/typecheck and runnable verifier evidence.",
        f"Repository family: {obs['repo_family']}",
        f"Source root: {obs['cwd']}",
        f"Selected verifier/build pair: {obs['selected_verifier_path']}",
        f"Observed command: {obs['command']}",
        "Return code: 0",
        f"Output tail: {obs['stdout_tail']}",
        "Options:",
        *[f"{o['label']}. {o['text']}" for o in opts],
        "Answer:",
    ])
    return {
        "row_id": row_id,
        "root_id": row_id,
        "root_lineage_key": f"stage12045::{obs['repo_family']}::{obs['selected_verifier_path']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": obs["repo_family"],
        "repo_family": obs["repo_family"],
        "language_family": obs["language_family"],
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12045_buildrun_floor_closure_train_support_only",
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
        "target": {"bounded_choice_target_label": target_label, "decoder_text": target_label, "semantic_value": semantic},
        "opaque_options": opts,
        "observed_verifier_transition": semantic,
        "anti_cheat": {"deterministic_option_shuffle": True, "target_label_not_visible_before_options": True, "target_value_not_visible_before_options": True, "singleton_options": False, "train_support_only": True},
        "standalone_projection_source": {"projection_mode": "stage12045_buildrun_floor_closure_rows", "selected_verifier_path": obs["selected_verifier_path"], "observed_verifier_transition": semantic, "tool_or_verifier_observation": {"command": obs["command"], "cwd": obs["cwd"], "returncode": 0, "stdout_tail": obs["stdout_tail"], "timed_out": False}},
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    rows = [make_row(obs) for obs in OBSERVATIONS]
    write_jsonl(ROWS, rows)
    summary = {
        "stage": "stage12045_buildrun_floor_closure_rows",
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(sorted(Counter(r["language_family"] for r in rows).items())),
        "status_counts": dict(sorted(Counter(r["observed_verifier_transition"] for r in rows).items())),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "rejected_probe_count": len(REJECTED_PROBES),
        "rejected_probes": REJECTED_PROBES,
        "decision": "admit_buildrun_floor_closure_train_support",
        "claim_boundary": "Rows are train-support only. No model promotion follows from this artifact.",
        "next_stage_recommendation": {"stage": "stage12046_transition_support_rollup_v30", "action": "Merge build+run floor closure rows and report remaining status floors."},
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
