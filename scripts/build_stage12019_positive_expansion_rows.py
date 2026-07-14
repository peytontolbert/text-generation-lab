#!/usr/bin/env python3
"""Materialize additional Python/Web PASS_TO_PASS transition observations."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12019_positive_expansion_rows")
ROWS = ROOT / "positive_expansion_rows.jsonl"
SUMMARY = ROOT / "positive_expansion_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12019_positive_expansion_rows.json")
LABELS = list("ABCDEFGH")

OBSERVATIONS: list[dict[str, Any]] = [
    {"language_family": "python", "repo_family": "einops", "cwd": "/data/repositories/einops", "selected_verifier_path": "einops/tests/test_other.py", "command": "env EINOPS_TEST_BACKENDS=numpy python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12019_pytest_cache einops/tests/test_other.py", "returncode": 0, "stdout_tail": "13 passed, 4 skipped, 1 warning in 0.64s"},
    {"language_family": "python", "repo_family": "einops", "cwd": "/data/repositories/einops", "selected_verifier_path": "einops/tests/test_ops.py", "command": "env EINOPS_TEST_BACKENDS=numpy python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12019_pytest_cache einops/tests/test_ops.py", "returncode": 0, "stdout_tail": "23 passed, 1 skipped in 0.52s"},
    {"language_family": "python", "repo_family": "lastmile-ai__mcp-agent", "cwd": "/data/repositories/lastmile-ai__mcp-agent", "selected_verifier_path": "tests/config/test_env_settings.py", "command": "env PYTHONPATH=/data/repositories/lastmile-ai__mcp-agent/src python -m pytest -q -c /dev/null -o cache_dir=/data/tmp/stage12019_pytest_cache tests/config/test_env_settings.py", "returncode": 0, "stdout_tail": "2 passed in 0.62s"},
    {"language_family": "web_js_ts_html", "repo_family": "modelcontextprotocol__typescript-sdk", "cwd": "/data/repositories/modelcontextprotocol__typescript-sdk", "selected_verifier_path": "packages/core/test/shared/uriTemplate.test.ts", "command": "./node_modules/.bin/vitest run --globals packages/core/test/shared/uriTemplate.test.ts", "returncode": 0, "stdout_tail": "Test Files  1 passed (1)\n      Tests  38 passed (38)"},
    {"language_family": "web_js_ts_html", "repo_family": "modelcontextprotocol__typescript-sdk", "cwd": "/data/repositories/modelcontextprotocol__typescript-sdk", "selected_verifier_path": "packages/core/test/shared/authUtils.test.ts", "command": "./node_modules/.bin/vitest run --globals packages/core/test/shared/authUtils.test.ts", "returncode": 0, "stdout_tail": "Test Files  1 passed (1)\n      Tests  9 passed (9)"},
    {"language_family": "web_js_ts_html", "repo_family": "modelcontextprotocol__typescript-sdk", "cwd": "/data/repositories/modelcontextprotocol__typescript-sdk", "selected_verifier_path": "packages/core/test/util/zodCompat.test.ts", "command": "./node_modules/.bin/vitest run --globals packages/core/test/util/zodCompat.test.ts", "returncode": 0, "stdout_tail": "Test Files  1 passed (1)\n      Tests  15 passed (15)"},
    {"language_family": "web_js_ts_html", "repo_family": "openclaw__clawhub", "cwd": "/data/repositories/openclaw__clawhub", "selected_verifier_path": "convex/lib/skillSlugValidator.test.ts", "command": "env VITE_CONVEX_URL=https://example.invalid ./node_modules/.bin/vitest run convex/lib/skillSlugValidator.test.ts", "returncode": 0, "stdout_tail": "Test Files  1 passed (1)\n      Tests  52 passed (52)"},
    {"language_family": "web_js_ts_html", "repo_family": "openclaw__clawhub", "cwd": "/data/repositories/openclaw__clawhub", "selected_verifier_path": "convex/lib/skillCapabilityTags.test.ts", "command": "env VITE_CONVEX_URL=https://example.invalid ./node_modules/.bin/vitest run convex/lib/skillCapabilityTags.test.ts", "returncode": 0, "stdout_tail": "Test Files  1 passed (1)\n      Tests  7 passed (7)"},
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
    semantic = "PASS_TO_PASS"
    material = f"{obs['repo_family']}::{obs['selected_verifier_path']}::{semantic}"
    row_id = f"stage12019::{obs['repo_family']}::{hashlib.sha1(material.encode()).hexdigest()[:12]}::{semantic}"
    opts = options(row_id, obs["language_family"])
    target_label = next(o["label"] for o in opts if o["canonical_value"] == semantic)
    prompt = "\n".join([
        f"Language: {obs['language_family']}",
        "Perspective: transition_verifier_transition",
        "Task: choose the verifier transition supported by the observed local-source command.",
        f"Repository family: {obs['repo_family']}",
        f"Source root: {obs['cwd']}",
        f"Selected verifier: {obs['selected_verifier_path']}",
        f"Observed command: {obs['command']}",
        f"Return code: {obs['returncode']}",
        f"Output tail: {obs['stdout_tail']}",
        "Options:",
        *[f"{o['label']}. {o['text']}" for o in opts],
        "Answer:",
    ])
    return {
        "row_id": row_id,
        "root_id": row_id,
        "root_lineage_key": f"stage12019::{obs['repo_family']}::{obs['selected_verifier_path']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": obs["repo_family"],
        "repo_family": obs["repo_family"],
        "language_family": obs["language_family"],
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12019_positive_expansion_train_support_only",
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
        "standalone_projection_source": {"projection_mode": "stage12019_positive_expansion_rows", "selected_verifier_path": obs["selected_verifier_path"], "observed_verifier_transition": semantic, "tool_or_verifier_observation": {"command": obs["command"], "cwd": obs["cwd"], "returncode": obs["returncode"], "stdout_tail": obs["stdout_tail"], "timed_out": False}},
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    rows = [make_row(obs) for obs in OBSERVATIONS]
    write_jsonl(ROWS, rows)
    summary = {
        "stage": "stage12019_positive_expansion_rows",
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(sorted(Counter(r["language_family"] for r in rows).items())),
        "status_counts": dict(Counter(r["observed_verifier_transition"] for r in rows)),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "decision": "admit_positive_expansion_train_support",
        "claim_boundary": "Rows are train-support only. No model promotion follows from this artifact.",
        "next_stage_recommendation": {"stage": "stage12020_transition_support_rollup_v17", "action": "Merge positive rows and report remaining Transition-Root-250 floors."},
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
