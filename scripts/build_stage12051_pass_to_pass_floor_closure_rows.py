#!/usr/bin/env python3
"""Materialize focused PASS_TO_PASS floor-closure rows."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12051_pass_to_pass_floor_closure_rows")
ROWS = ROOT / "pass_to_pass_floor_closure_rows.jsonl"
SUMMARY = ROOT / "pass_to_pass_floor_closure_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12051_pass_to_pass_floor_closure_rows.json")
LABELS = list("ABCDEFGH")

OBSERVATIONS: list[dict[str, Any]] = [
    {"language_family": "python", "repo_family": "SWE-agent__SWE-ReX", "cwd": "/data/repositories/SWE-agent__SWE-ReX", "selected_verifier_path": "test_footer.py", "command": "timeout 20 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12051_pytest_cache /data/repositories/SWE-agent__SWE-ReX/test_footer.py", "stdout_tail": "4 passed, 4 warnings in 0.46s"},
    {"language_family": "python", "repo_family": "method_comparison", "cwd": "/data/repositories/method_comparison", "selected_verifier_path": "test_sanitizer.py", "command": "timeout 20 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12051_pytest_cache /data/repositories/method_comparison/test_sanitizer.py", "stdout_tail": "10 passed in 1.21s"},
    {"language_family": "rust", "repo_family": "tokenizers", "cwd": "/data/repositories/tokenizers/tokenizers", "selected_verifier_path": "cargo test --lib", "command": "timeout 40 conda run -n trellis cargo test -q --lib", "stdout_tail": "running 192 tests; test result: ok. 192 passed; 0 failed; finished in 0.05s"},
    {"language_family": "web_js_ts_html", "repo_family": "openclaw__clawhub", "cwd": "/data/repositories/openclaw__clawhub", "selected_verifier_path": "src/__tests__/search-route.test.ts", "command": "timeout 30 ./node_modules/.bin/vitest run --globals src/__tests__/search-route.test.ts", "stdout_tail": "Test Files 2 passed (2); Tests 19 passed (19)"},
    {"language_family": "web_js_ts_html", "repo_family": "openclaw__clawhub", "cwd": "/data/repositories/openclaw__clawhub", "selected_verifier_path": "src/__tests__/skill-route-loader.test.ts", "command": "timeout 30 ./node_modules/.bin/vitest run --globals src/__tests__/skill-route-loader.test.ts", "stdout_tail": "Test Files 1 passed (1); Tests 13 passed (13)"},
    {"language_family": "web_js_ts_html", "repo_family": "openclaw__clawhub", "cwd": "/data/repositories/openclaw__clawhub", "selected_verifier_path": "convex/lib/access.test.ts", "command": "timeout 30 ./node_modules/.bin/vitest run --globals convex/lib/access.test.ts", "stdout_tail": "Test Files 1 passed (1); Tests 10 passed (10)"},
    {"language_family": "web_js_ts_html", "repo_family": "openclaw__clawhub", "cwd": "/data/repositories/openclaw__clawhub", "selected_verifier_path": "convex/lib/apiTokenAuth.test.ts", "command": "timeout 30 ./node_modules/.bin/vitest run --globals convex/lib/apiTokenAuth.test.ts", "stdout_tail": "Test Files 1 passed (1); Tests 8 passed (8)"},
    {"language_family": "web_js_ts_html", "repo_family": "openclaw__clawhub", "cwd": "/data/repositories/openclaw__clawhub", "selected_verifier_path": "convex/lib/githubIdentity.test.ts", "command": "timeout 30 ./node_modules/.bin/vitest run --globals convex/lib/githubIdentity.test.ts", "stdout_tail": "Test Files 1 passed (1); Tests 3 passed (3)"},
    {"language_family": "web_js_ts_html", "repo_family": "openclaw__clawhub", "cwd": "/data/repositories/openclaw__clawhub", "selected_verifier_path": "convex/lib/tokens.test.ts", "command": "timeout 30 ./node_modules/.bin/vitest run --globals convex/lib/tokens.test.ts", "stdout_tail": "Test Files 1 passed (1); Tests 5 passed (5)"},
    {"language_family": "web_js_ts_html", "repo_family": "modelcontextprotocol__typescript-sdk", "cwd": "/data/repositories/modelcontextprotocol__typescript-sdk", "selected_verifier_path": "packages/core/test/types.test.ts", "command": "timeout 30 pnpm --filter @modelcontextprotocol/core test -- packages/core/test/types.test.ts", "stdout_tail": "Test Files 21 passed (21); Tests 552 passed (552)"},
    {"language_family": "web_js_ts_html", "repo_family": "modelcontextprotocol__typescript-sdk", "cwd": "/data/repositories/modelcontextprotocol__typescript-sdk", "selected_verifier_path": "packages/core/test/shared/toolNameValidation.test.ts", "command": "timeout 30 pnpm --filter @modelcontextprotocol/core test -- packages/core/test/shared/toolNameValidation.test.ts", "stdout_tail": "Test Files 21 passed (21); Tests 552 passed (552)"},
    {"language_family": "python", "repo_family": "NousResearch__hermes-agent", "cwd": "/data/repositories/NousResearch__hermes-agent", "selected_verifier_path": "tests/agent/test_async_utils.py", "command": "timeout 30 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12051_pytest_cache /data/repositories/NousResearch__hermes-agent/tests/agent/test_async_utils.py", "stdout_tail": "6 passed in 1.70s"},
    {"language_family": "python", "repo_family": "NousResearch__hermes-agent", "cwd": "/data/repositories/NousResearch__hermes-agent", "selected_verifier_path": "tests/agent/test_error_classifier.py", "command": "timeout 30 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12051_pytest_cache /data/repositories/NousResearch__hermes-agent/tests/agent/test_error_classifier.py", "stdout_tail": "130 passed in 4.75s"},
    {"language_family": "python", "repo_family": "NousResearch__hermes-agent", "cwd": "/data/repositories/NousResearch__hermes-agent", "selected_verifier_path": "tests/agent/test_display.py", "command": "timeout 30 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12051_pytest_cache /data/repositories/NousResearch__hermes-agent/tests/agent/test_display.py", "stdout_tail": "31 passed in 2.19s"},
    {"language_family": "python", "repo_family": "NousResearch__hermes-agent", "cwd": "/data/repositories/NousResearch__hermes-agent", "selected_verifier_path": "tests/agent/test_context_references.py", "command": "timeout 30 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12051_pytest_cache /data/repositories/NousResearch__hermes-agent/tests/agent/test_context_references.py", "stdout_tail": "12 passed, 2 skipped, 4 warnings in 1.97s"},
    {"language_family": "python", "repo_family": "NousResearch__hermes-agent", "cwd": "/data/repositories/NousResearch__hermes-agent", "selected_verifier_path": "tests/agent/test_context_engine.py", "command": "timeout 30 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12051_pytest_cache /data/repositories/NousResearch__hermes-agent/tests/agent/test_context_engine.py", "stdout_tail": "19 passed in 1.86s"},
    {"language_family": "python", "repo_family": "NousResearch__hermes-agent", "cwd": "/data/repositories/NousResearch__hermes-agent", "selected_verifier_path": "tests/agent/test_display_emoji.py", "command": "timeout 30 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12051_pytest_cache /data/repositories/NousResearch__hermes-agent/tests/agent/test_display_emoji.py", "stdout_tail": "10 passed in 1.60s"},
    {"language_family": "python", "repo_family": "NousResearch__hermes-agent", "cwd": "/data/repositories/NousResearch__hermes-agent", "selected_verifier_path": "tests/agent/test_i18n.py", "command": "timeout 30 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12051_pytest_cache /data/repositories/NousResearch__hermes-agent/tests/agent/test_i18n.py", "stdout_tail": "43 passed in 3.60s"},
    {"language_family": "python", "repo_family": "NousResearch__hermes-agent", "cwd": "/data/repositories/NousResearch__hermes-agent", "selected_verifier_path": "tests/agent/test_insights.py", "command": "timeout 30 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12051_pytest_cache /data/repositories/NousResearch__hermes-agent/tests/agent/test_insights.py", "stdout_tail": "56 passed in 14.90s"},
    {"language_family": "python", "repo_family": "NousResearch__hermes-agent", "cwd": "/data/repositories/NousResearch__hermes-agent", "selected_verifier_path": "tests/agent/test_external_skills.py", "command": "timeout 30 python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12051_pytest_cache /data/repositories/NousResearch__hermes-agent/tests/agent/test_external_skills.py", "stdout_tail": "11 passed in 1.69s"},
    {"language_family": "web_js_ts_html", "repo_family": "openclaw__clawhub", "cwd": "/data/repositories/openclaw__clawhub", "selected_verifier_path": "convex/lib/httpRateLimit.test.ts", "command": "timeout 30 ./node_modules/.bin/vitest run --globals convex/lib/httpRateLimit.test.ts", "stdout_tail": "Test Files 1 passed (1); Tests 21 passed (21)"},
    {"language_family": "web_js_ts_html", "repo_family": "openclaw__clawhub", "cwd": "/data/repositories/openclaw__clawhub", "selected_verifier_path": "convex/lib/skillSlugValidator.test.ts", "command": "timeout 30 ./node_modules/.bin/vitest run --globals convex/lib/skillSlugValidator.test.ts", "stdout_tail": "Test Files 1 passed (1); Tests 52 passed (52)"},
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
    return [
        {"label": label, "canonical_value": value, "value": value, "text": text, "role": "verifier_transition_status", "artifact_type": f"{language}_verifier_status"}
        for label, (_, value, text) in zip(LABELS, sorted(keyed))
    ]


def make_row(obs: dict[str, Any]) -> dict[str, Any]:
    semantic = "PASS_TO_PASS"
    material = f"{obs['repo_family']}::{obs['selected_verifier_path']}::{semantic}"
    row_id = f"stage12051::{obs['repo_family']}::{hashlib.sha1(material.encode()).hexdigest()[:12]}::{semantic}"
    opts = options(row_id, obs["language_family"])
    target_label = next(o["label"] for o in opts if o["canonical_value"] == semantic)
    prompt = "\n".join([
        f"Language: {obs['language_family']}",
        "Perspective: transition_verifier_transition",
        "Task: choose the verifier transition supported by the observed focused verifier command.",
        f"Repository family: {obs['repo_family']}",
        f"Source root: {obs['cwd']}",
        f"Selected verifier: {obs['selected_verifier_path']}",
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
        "root_lineage_key": f"stage12051::{obs['repo_family']}::{obs['selected_verifier_path']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": obs["repo_family"],
        "repo_family": obs["repo_family"],
        "language_family": obs["language_family"],
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12051_pass_to_pass_floor_closure_train_support_only",
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
        "standalone_projection_source": {"projection_mode": "stage12051_pass_to_pass_floor_closure_rows", "selected_verifier_path": obs["selected_verifier_path"], "observed_verifier_transition": semantic, "tool_or_verifier_observation": {"command": obs["command"], "cwd": obs["cwd"], "returncode": 0, "stdout_tail": obs["stdout_tail"], "timed_out": False}},
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    rows = [make_row(obs) for obs in OBSERVATIONS]
    write_jsonl(ROWS, rows)
    summary = {
        "stage": "stage12051_pass_to_pass_floor_closure_rows",
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(sorted(Counter(r["language_family"] for r in rows).items())),
        "status_counts": dict(sorted(Counter(r["observed_verifier_transition"] for r in rows).items())),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "decision": "admit_pass_to_pass_floor_closure_train_support",
        "claim_boundary": "Rows are train-support only direct passing verifier observations. No model promotion follows from this artifact.",
        "next_stage_recommendation": {"stage": "stage12052_transition_support_rollup_v33", "action": "Merge PASS_TO_PASS floor-closure rows and report remaining semantic FAIL_TO_PASS floor."},
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
