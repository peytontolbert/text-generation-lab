#!/usr/bin/env python3
"""Create additional controlled multilingual FAIL_TO_PASS transition rows."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12025_controlled_fail_to_pass_expansion_rows").resolve()
FIXTURE_ROOT = ROOT / "fixture_repos"
ROWS = ROOT / "controlled_fail_to_pass_expansion_rows.jsonl"
SUMMARY = ROOT / "controlled_fail_to_pass_expansion_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12025_controlled_fail_to_pass_expansion_rows.json")
LABELS = list("ABCDEFGH")

FIXTURES: list[dict[str, Any]] = [
    {
        "id": "python_empty_timeout_preserved",
        "language_family": "python",
        "repo_family": "stage12025_python_controlled_fixture",
        "files": {
            "timeout_policy.py": "def normalize_timeout(value):\n    return value\n",
            "test_timeout_policy.py": "from timeout_policy import normalize_timeout\n\n\ndef test_empty_timeout_preserved():\n    assert normalize_timeout(0) == 0\n    assert normalize_timeout(7) == 7\n",
        },
        "command": ["python", "-m", "pytest", "-q", "-c", "/dev/null", "test_timeout_policy.py"],
        "source_file": "timeout_policy.py",
        "find": "    return value\n",
        "replace": "    return value or None\n",
        "selected_verifier_path": "test_timeout_policy.py::test_empty_timeout_preserved",
    },
    {
        "id": "python_case_sensitive_key",
        "language_family": "python",
        "repo_family": "stage12025_python_controlled_fixture",
        "files": {
            "key_lookup.py": "def canonical_key(value):\n    return value\n",
            "test_key_lookup.py": "from key_lookup import canonical_key\n\n\ndef test_case_is_preserved():\n    assert canonical_key('ApiKey') == 'ApiKey'\n",
        },
        "command": ["python", "-m", "pytest", "-q", "-c", "/dev/null", "test_key_lookup.py"],
        "source_file": "key_lookup.py",
        "find": "    return value\n",
        "replace": "    return value.lower()\n",
        "selected_verifier_path": "test_key_lookup.py::test_case_is_preserved",
    },
    {
        "id": "cpp_zero_id_preserved",
        "language_family": "c_cpp",
        "repo_family": "stage12025_cpp_controlled_fixture",
        "files": {
            "identity.hpp": "#pragma once\ninline int preserve_id(int value) { return value; }\n",
            "test_identity.cpp": "#include <cassert>\n#include \"identity.hpp\"\nint main() { assert(preserve_id(0) == 0); assert(preserve_id(9) == 9); return 0; }\n",
        },
        "command": ["bash", "-lc", "g++ -std=c++17 test_identity.cpp -o test_identity && ./test_identity"],
        "source_file": "identity.hpp",
        "find": "return value;",
        "replace": "return value == 0 ? -1 : value;",
        "selected_verifier_path": "test_identity.cpp",
    },
    {
        "id": "cpp_clamp_boundary",
        "language_family": "c_cpp",
        "repo_family": "stage12025_cpp_controlled_fixture",
        "files": {
            "clamp.hpp": "#pragma once\ninline int clamp_nonnegative(int value) { return value < 0 ? 0 : value; }\n",
            "test_clamp.cpp": "#include <cassert>\n#include \"clamp.hpp\"\nint main() { assert(clamp_nonnegative(-3) == 0); assert(clamp_nonnegative(4) == 4); return 0; }\n",
        },
        "command": ["bash", "-lc", "g++ -std=c++17 test_clamp.cpp -o test_clamp && ./test_clamp"],
        "source_file": "clamp.hpp",
        "find": "return value < 0 ? 0 : value;",
        "replace": "return value;",
        "selected_verifier_path": "test_clamp.cpp",
    },
    {
        "id": "rust_option_zero_preserved",
        "language_family": "rust",
        "repo_family": "stage12025_rust_controlled_fixture",
        "files": {
            "Cargo.toml": "[package]\nname = \"stage12025_rust_option_zero\"\nversion = \"0.1.0\"\nedition = \"2021\"\n",
            "src/lib.rs": "pub fn keep_timeout(value: Option<u64>) -> Option<u64> { value }\n\n#[cfg(test)]\nmod tests {\n    use super::*;\n    #[test]\n    fn zero_is_preserved() { assert_eq!(keep_timeout(Some(0)), Some(0)); }\n}\n",
        },
        "command": ["cargo", "test", "--quiet"],
        "source_file": "src/lib.rs",
        "find": "pub fn keep_timeout(value: Option<u64>) -> Option<u64> { value }",
        "replace": "pub fn keep_timeout(value: Option<u64>) -> Option<u64> { value.filter(|v| *v > 0) }",
        "selected_verifier_path": "cargo test --quiet zero_is_preserved",
    },
    {
        "id": "rust_case_sensitive_token",
        "language_family": "rust",
        "repo_family": "stage12025_rust_controlled_fixture",
        "files": {
            "Cargo.toml": "[package]\nname = \"stage12025_rust_case_token\"\nversion = \"0.1.0\"\nedition = \"2021\"\n",
            "src/lib.rs": "pub fn token(value: &str) -> String { value.to_string() }\n\n#[cfg(test)]\nmod tests {\n    use super::*;\n    #[test]\n    fn case_is_preserved() { assert_eq!(token(\"ApiKey\"), \"ApiKey\"); }\n}\n",
        },
        "command": ["cargo", "test", "--quiet"],
        "source_file": "src/lib.rs",
        "find": "pub fn token(value: &str) -> String { value.to_string() }",
        "replace": "pub fn token(value: &str) -> String { value.to_lowercase() }",
        "selected_verifier_path": "cargo test --quiet case_is_preserved",
    },
    {
        "id": "web_zero_port_preserved",
        "language_family": "web_js_ts_html",
        "repo_family": "stage12025_web_controlled_fixture",
        "files": {
            "package.json": "{\"type\":\"module\",\"scripts\":{\"test\":\"node test_port.js\"}}\n",
            "port.js": "export function normalizePort(value) { return value; }\n",
            "test_port.js": "import assert from 'node:assert/strict';\nimport { normalizePort } from './port.js';\nassert.equal(normalizePort(0), 0);\nassert.equal(normalizePort(8080), 8080);\n",
        },
        "command": ["npm", "test", "--", "--silent"],
        "source_file": "port.js",
        "find": "return value;",
        "replace": "return value || 3000;",
        "selected_verifier_path": "npm test -- --silent zero port",
    },
    {
        "id": "web_case_sensitive_slug",
        "language_family": "web_js_ts_html",
        "repo_family": "stage12025_web_controlled_fixture",
        "files": {
            "package.json": "{\"type\":\"module\",\"scripts\":{\"test\":\"node test_slug.js\"}}\n",
            "slug.js": "export function displaySlug(value) { return value; }\n",
            "test_slug.js": "import assert from 'node:assert/strict';\nimport { displaySlug } from './slug.js';\nassert.equal(displaySlug('APIKey'), 'APIKey');\n",
        },
        "command": ["npm", "test", "--", "--silent"],
        "source_file": "slug.js",
        "find": "return value;",
        "replace": "return value.toLowerCase();",
        "selected_verifier_path": "npm test -- --silent case slug",
    },
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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def build_fixture(spec: dict[str, Any]) -> Path:
    root = FIXTURE_ROOT / spec["id"]
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    for name, text in spec["files"].items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


def run_cmd(cwd: Path, cmd: list[str], log_name: str) -> dict[str, Any]:
    env = os.environ.copy()
    env.update({"CUDA_VISIBLE_DEVICES": "", "NVIDIA_VISIBLE_DEVICES": "", "TMPDIR": str(ROOT / "tmp"), "TEMP": str(ROOT / "tmp"), "TMP": str(ROOT / "tmp")})
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)
    (ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=45, check=False)
        payload = {"command": cmd, "cwd": str(cwd), "returncode": proc.returncode, "timed_out": False, "duration_sec": round(time.time() - started, 3), "stdout_tail": (proc.stdout or "")[-3000:], "stderr_tail": (proc.stderr or "")[-3000:]}
    except subprocess.TimeoutExpired as exc:
        payload = {"command": cmd, "cwd": str(cwd), "returncode": 124, "timed_out": True, "duration_sec": round(time.time() - started, 3), "stdout_tail": exc.stdout if isinstance(exc.stdout, str) else "", "stderr_tail": exc.stderr if isinstance(exc.stderr, str) else ""}
    log = ROOT / "logs" / f"{log_name}.json"
    write_json(log, payload)
    return {**payload, "log_path": str(log)}


def options(row_id: str, language: str) -> list[dict[str, str]]:
    keyed = [(hashlib.sha256(f"{row_id}::{value}".encode()).hexdigest(), value, text) for value, text in TRANSITION_TEXT.items()]
    return [
        {
            "label": label,
            "canonical_value": value,
            "value": value,
            "text": text,
            "role": "verifier_transition_status",
            "artifact_type": f"{language}_verifier_status",
        }
        for label, (_, value, text) in zip(LABELS, sorted(keyed))
    ]


def make_row(spec: dict[str, Any], fixture_root: Path, baseline: dict[str, Any], mutant: dict[str, Any], restored: dict[str, Any]) -> dict[str, Any]:
    semantic = "FAIL_TO_PASS"
    row_id = f"stage12025::{spec['repo_family']}::{spec['id']}"
    opts = options(row_id, spec["language_family"])
    target_label = next(o["label"] for o in opts if o["canonical_value"] == semantic)
    prompt = "\n".join(
        [
            f"Language: {spec['language_family']}",
            "Perspective: transition_verifier_transition",
            "Task: choose the verifier transition proven by baseline, controlled mutation, and restored-source evidence.",
            f"Repository family: {spec['repo_family']}",
            f"Fixture root: {fixture_root}",
            f"Source file mutated: {spec['source_file']}",
            f"Selected verifier: {spec['selected_verifier_path']}",
            f"Baseline rc: {baseline['returncode']} tail: {(baseline.get('stdout_tail') or baseline.get('stderr_tail') or '')[-700:]}",
            f"Mutant rc: {mutant['returncode']} tail: {(mutant.get('stdout_tail') or mutant.get('stderr_tail') or '')[-700:]}",
            f"Restored rc: {restored['returncode']} tail: {(restored.get('stdout_tail') or restored.get('stderr_tail') or '')[-700:]}",
            "Options:",
            *[f"{o['label']}. {o['text']}" for o in opts],
            "Answer:",
        ]
    )
    return {
        "row_id": row_id,
        "root_id": row_id,
        "root_lineage_key": f"stage12025::{spec['repo_family']}::{spec['id']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": spec["repo_family"],
        "repo_family": spec["repo_family"],
        "language_family": spec["language_family"],
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12025_controlled_fail_to_pass_expansion_train_support_only",
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
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "singleton_options": False,
            "controlled_fixture_train_support_only": True,
            "baseline_mutant_restore_all_observed": True,
            "train_support_only": True,
        },
        "standalone_projection_source": {
            "projection_mode": "stage12025_controlled_fail_to_pass_expansion_rows",
            "fixture_repo": str(fixture_root),
            "selected_verifier_path": spec["selected_verifier_path"],
            "source_file": spec["source_file"],
            "observed_verifier_transition": semantic,
            "tool_or_verifier_observation": {"baseline": baseline, "mutant": mutant, "restored": restored},
        },
    }


def run_fixture(spec: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    fixture_root = build_fixture(spec)
    source = fixture_root / spec["source_file"]
    original = source.read_text()
    baseline = run_cmd(fixture_root, spec["command"], f"{spec['id']}_baseline")
    source.write_text(original.replace(spec["find"], spec["replace"], 1))
    mutant = run_cmd(fixture_root, spec["command"], f"{spec['id']}_mutant")
    source.write_text(original)
    restored = run_cmd(fixture_root, spec["command"], f"{spec['id']}_restored")
    restored_matches = source.read_text() == original
    admitted = baseline["returncode"] == 0 and mutant["returncode"] != 0 and restored["returncode"] == 0 and restored_matches
    card = {"fixture": spec, "baseline": baseline, "mutant": mutant, "restored": restored, "restored_matches_original": restored_matches, "admitted": admitted}
    return (make_row(spec, fixture_root, baseline, mutant, restored) if admitted else None), card


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    for spec in FIXTURES:
        row, card = run_fixture(spec)
        cards.append(card)
        if row:
            rows.append(row)
    write_jsonl(ROWS, rows)
    summary = {
        "stage": "stage12025_controlled_fail_to_pass_expansion_rows",
        "rows_path": str(ROWS),
        "fixture_root": str(FIXTURE_ROOT),
        "attempted_fixtures": len(FIXTURES),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(sorted(Counter(r["language_family"] for r in rows).items())),
        "status_counts": dict(sorted(Counter(r["observed_verifier_transition"] for r in rows).items())),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "probe_cards": cards,
        "decision": "admit_controlled_fail_to_pass_expansion_train_support" if rows else "no_controlled_fail_to_pass_rows_admitted",
        "claim_boundary": "Controlled fixtures are train-support only. They improve transition-status supervision but are not source-heldout or strict eval evidence.",
        "next_stage_recommendation": {
            "stage": "stage12026_transition_support_rollup_v20",
            "action": "Merge controlled FAIL_TO_PASS expansion rows and report remaining Transition-Root-250 floors.",
        },
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps({k: summary[k] for k in ["decision", "admitted_rows", "language_counts", "status_counts", "next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
