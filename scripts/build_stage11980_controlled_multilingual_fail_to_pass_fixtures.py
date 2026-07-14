#!/usr/bin/env python3
"""Create controlled C++/Rust/JS FAIL_TO_PASS transition fixture rows."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11980
NAME = "stage11980_controlled_multilingual_fail_to_pass_fixtures"
OUT = ART / NAME
FIXTURE = OUT / "fixture_repos"
SUMMARY = OUT / "controlled_multilingual_fail_to_pass_fixtures.json"
ROWS = OUT / "controlled_multilingual_fail_to_pass_review_rows.jsonl"
LABELS = list("ABCDEFGH")

FIXTURES = [
    {
        "id": "cpp_zero_timeout",
        "language_family": "c_cpp",
        "repo_family": "stage11980_cpp_controlled_fixture",
        "files": {
            "timeout.hpp": "#pragma once\ninline int normalize_timeout(int value) { return value; }\n",
            "test_timeout.cpp": "#include <cassert>\n#include \"timeout.hpp\"\nint main() { assert(normalize_timeout(0) == 0); assert(normalize_timeout(5) == 5); return 0; }\n",
        },
        "command": ["bash", "-lc", "g++ -std=c++17 test_timeout.cpp -o test_timeout && ./test_timeout"],
        "source_file": "timeout.hpp",
        "find": "return value;",
        "replace": "return value ? value : -1;",
        "selected_verifier_path": "test_timeout.cpp",
        "mutation": "Treat zero timeout as -1, breaking the focused zero-preservation verifier.",
    },
    {
        "id": "rust_zero_timeout",
        "language_family": "rust",
        "repo_family": "stage11980_rust_controlled_fixture",
        "files": {
            "Cargo.toml": "[package]\nname = \"stage11980_rust_fixture\"\nversion = \"0.1.0\"\nedition = \"2021\"\n",
            "src/lib.rs": "pub fn normalize_timeout(value: Option<u64>) -> Option<u64> { value }\n\n#[cfg(test)]\nmod tests {\n    use super::*;\n    #[test]\n    fn zero_timeout_is_preserved() { assert_eq!(normalize_timeout(Some(0)), Some(0)); }\n}\n",
        },
        "command": ["cargo", "test", "--quiet"],
        "source_file": "src/lib.rs",
        "find": "pub fn normalize_timeout(value: Option<u64>) -> Option<u64> { value }",
        "replace": "pub fn normalize_timeout(value: Option<u64>) -> Option<u64> { value.filter(|v| *v != 0) }",
        "selected_verifier_path": "cargo test --quiet",
        "mutation": "Drop Some(0), breaking the focused zero-timeout Rust verifier.",
    },
    {
        "id": "web_zero_timeout",
        "language_family": "web_js_ts_html",
        "repo_family": "stage11980_web_controlled_fixture",
        "files": {
            "package.json": "{\"type\":\"module\",\"scripts\":{\"test\":\"node test_timeout.js\"}}\n",
            "timeout.js": "export function normalizeTimeout(value) { return value; }\n",
            "test_timeout.js": "import assert from 'node:assert/strict';\nimport { normalizeTimeout } from './timeout.js';\nassert.equal(normalizeTimeout(0), 0);\nassert.equal(normalizeTimeout(5), 5);\n",
        },
        "command": ["npm", "test", "--", "--silent"],
        "source_file": "timeout.js",
        "find": "return value;",
        "replace": "return value || null;",
        "selected_verifier_path": "npm test -- --silent",
        "mutation": "Treat zero as null, breaking the focused JavaScript zero-preservation verifier.",
    },
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def build_fixture(spec: dict[str, Any]) -> Path:
    root = FIXTURE / spec["id"]
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    for name, text in spec["files"].items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def run_cmd(cwd: Path, cmd: list[str], log_name: str) -> dict[str, Any]:
    env = os.environ.copy()
    env.update({"CUDA_VISIBLE_DEVICES": "", "NVIDIA_VISIBLE_DEVICES": "", "TMPDIR": str(OUT / "tmp"), "TEMP": str(OUT / "tmp"), "TMP": str(OUT / "tmp")})
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    (OUT / "tmp").mkdir(parents=True, exist_ok=True)
    started = time.time()
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=45, check=False)
    payload = {"command": cmd, "cwd": str(cwd), "returncode": proc.returncode, "timed_out": False, "duration_sec": round(time.time() - started, 3), "stdout_tail": (proc.stdout or "")[-3000:], "stderr_tail": (proc.stderr or "")[-3000:]}
    write_json(OUT / "logs" / f"{log_name}.json", payload)
    return {**payload, "log_path": rel(OUT / "logs" / f"{log_name}.json")}


def shuffled(row_id: str, values: list[str]) -> list[dict[str, str]]:
    keyed = [(hashlib.sha256(f"{row_id}::{i}::{v}".encode()).hexdigest(), v) for i, v in enumerate(values)]
    return [{"label": label, "value": value} for label, (_, value) in zip(LABELS, sorted(keyed))]


def make_row(spec: dict[str, Any], baseline: dict[str, Any], mutant: dict[str, Any], restored: dict[str, Any], fixture_root: Path) -> dict[str, Any]:
    row_id = f"stage11980::{spec['repo_family']}::{spec['id']}"
    target_value = "baseline passed, controlled mutation failed focused verifier, restored source passed"
    options = shuffled(row_id, [target_value, "baseline failed before mutation", "mutation did not fail focused verifier", "restore was not verified"])
    target_label = next(o["label"] for o in options if o["value"] == target_value)
    prompt = "\n".join([
        f"Language: {spec['language_family']}",
        "Perspective: transition_verifier_transition",
        "Task: choose the verifier transition proven by baseline/mutant/restored source-backed evidence.",
        f"Repository family: {spec['repo_family']}",
        f"Source file: {spec['source_file']}",
        f"Selected verifier: {spec['selected_verifier_path']}",
        f"Mutation: {spec['mutation']}",
        f"Baseline rc/stdout: {baseline['returncode']} {(baseline.get('stdout_tail') or baseline.get('stderr_tail') or '').strip()}",
        f"Mutant rc/stdout: {mutant['returncode']} {(mutant.get('stdout_tail') or mutant.get('stderr_tail') or '').strip()}",
        f"Restored rc/stdout: {restored['returncode']} {(restored.get('stdout_tail') or restored.get('stderr_tail') or '').strip()}",
        "Options:", *[f"{o['label']}. {o['value']}" for o in options], "Answer:"
    ])
    return {"row_id": row_id, "source_root_id": row_id, "source_bundle_id": row_id, "repo_id": spec["repo_family"], "repo_family": spec["repo_family"], "language_family": spec["language_family"], "task_type": "transition_verifier_transition", "surface": "controlled_multilingual_fail_to_pass_transition_review_bounded_choice", "split": "train", "split_role": "review_queue_only", "train_support_only": True, "strict_eval_eligible": False, "selected_test_anchor": True, "verifier_anchor": True, "input_text": prompt, "prompt_text": prompt, "target_text": target_label, "decoder_text": target_label, "opaque_options": options, "target_semantic_value": target_value, "observed_verifier_transition": "FAIL_TO_PASS", "anti_cheat": {"deterministic_option_shuffle": True, "target_label_not_visible_before_options": True, "target_value_not_visible_before_options": True, "singleton_options": False, "controlled_fixture_train_support_only": True, "baseline_mutant_restore_all_observed": True, "review_queue_only": True}, "standalone_projection_source": {"projection_mode": NAME, "fixture_repo": rel(fixture_root), "selected_verifier_path": spec["selected_verifier_path"], "source_file": spec["source_file"], "observed_verifier_transition": "FAIL_TO_PASS", "tool_or_verifier_observation": {"baseline": baseline, "mutant": mutant, "restored": restored}}}


def main() -> None:
    rows=[]; cards=[]
    for spec in FIXTURES:
        root=build_fixture(spec)
        source=root/spec["source_file"]
        baseline=run_cmd(root,spec["command"],f"{spec['id']}_baseline")
        original=source.read_text(encoding="utf-8")
        source.write_text(original.replace(spec["find"],spec["replace"],1),encoding="utf-8")
        mutant=run_cmd(root,spec["command"],f"{spec['id']}_mutant")
        source.write_text(original,encoding="utf-8")
        restored=run_cmd(root,spec["command"],f"{spec['id']}_restored")
        admitted=baseline["returncode"]==0 and mutant["returncode"]!=0 and restored["returncode"]==0
        cards.append({"fixture":spec,"baseline":baseline,"mutant":mutant,"restored":restored,"admitted":admitted})
        if admitted:
            rows.append(make_row(spec,baseline,mutant,restored,root))
    write_jsonl(ROWS,rows)
    by_lang={}
    for r in rows: by_lang[r['language_family']]=by_lang.get(r['language_family'],0)+1
    artifact={"stage":STAGE,"stage_name":NAME,"created_at_utc":now(),"decision":"controlled_multilingual_fail_to_pass_complete_review_queue_only","summary":{"fixtures":len(FIXTURES),"admitted_rows":len(rows),"admitted_by_language":by_lang},"quality_scope":"controlled_fixture_train_support_only_not_strict_eval_not_source_heldout","probe_cards":cards,"outputs":{"summary":rel(SUMMARY),"rows":rel(ROWS),"fixture_root":rel(FIXTURE),"logs":rel(OUT/'logs')},"next_stage_recommendation":{"stage":"stage11981_multilingual_transition_support_rollup","action":"Merge Stage11979 Python support with Stage11980 C++/Rust/Web fixture FAIL_TO_PASS support while preserving support-only claim boundaries."}}
    write_json(SUMMARY,artifact)
    print(json.dumps({"decision":artifact["decision"],"summary":artifact["summary"],"quality_scope":artifact["quality_scope"],"next":artifact["next_stage_recommendation"]},indent=2,sort_keys=True))

if __name__ == "__main__":
    main()
