#!/usr/bin/env python3
"""Create real-source controlled FAIL_TO_PASS rows from passing Rust/Web roots.

This mutates source files in-place with backup/restore guards, runs baseline/mutant/restored
commands, and refuses rows unless baseline and restored pass while mutant fails.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage11999_real_source_fail_to_pass_mutations")
ROWS = ROOT / "real_source_fail_to_pass_rows.jsonl"
SUMMARY = ROOT / "real_source_fail_to_pass_mutations.json"
SUMMARY_MIRROR = Path("runs/summaries/stage11999_real_source_fail_to_pass_mutations.json")
LABELS = list("ABCDEFGH")

SPECS = [
    {
        "id": "rust_git_libgit_sys_lib_rs_syntax_guard",
        "language_family": "rust",
        "repo_family": "git",
        "root": "/data/repositories/git/contrib/libgit-sys",
        "source_file": "src/lib.rs",
        "commands": [["cargo", "test", "--quiet", "--no-fail-fast"]],
        "selected_verifier_path": "cargo test --quiet --no-fail-fast",
        "mutation_text": "\nfn __stage11999_forced_compile_error( {\n",
        "mutation_kind": "source_compile_error",
    },
    {
        "id": "rust_llama_tree_sitter_python_lib_rs_syntax_guard",
        "language_family": "rust",
        "repo_family": "llama-adapter",
        "root": "/data/repositories/LLaMA-Adapter/gorilla/gorilla-main/eval/eval-scripts/codebleu/parser/tree-sitter-python",
        "source_file": "bindings/rust/lib.rs",
        "commands": [["cargo", "test", "--quiet", "--no-fail-fast"]],
        "selected_verifier_path": "cargo test --quiet --no-fail-fast",
        "mutation_text": "\nfn __stage11999_forced_compile_error( {\n",
        "mutation_kind": "source_compile_error",
    },
    {
        "id": "web_mcp_core_index_ts_syntax_guard",
        "language_family": "web_js_ts_html",
        "repo_family": "modelcontextprotocol__typescript-sdk",
        "root": "/data/repositories/modelcontextprotocol__typescript-sdk",
        "source_file": "packages/core/src/index.ts",
        "commands": [["pnpm", "--dir", "/data/repositories/modelcontextprotocol__typescript-sdk", "--filter", "@modelcontextprotocol/core", "run", "typecheck"], ["pnpm", "--dir", "/data/repositories/modelcontextprotocol__typescript-sdk", "--filter", "@modelcontextprotocol/core", "run", "test"]],
        "selected_verifier_path": "@modelcontextprotocol/core typecheck + test",
        "mutation_text": "\nexport const __stage11999_forced_compile_error = ;\n",
        "mutation_kind": "typescript_compile_error",
    },
    {
        "id": "web_mcp_client_index_ts_syntax_guard",
        "language_family": "web_js_ts_html",
        "repo_family": "modelcontextprotocol__typescript-sdk",
        "root": "/data/repositories/modelcontextprotocol__typescript-sdk",
        "source_file": "packages/client/src/index.ts",
        "commands": [["pnpm", "--dir", "/data/repositories/modelcontextprotocol__typescript-sdk", "--filter", "@modelcontextprotocol/client", "run", "typecheck"], ["pnpm", "--dir", "/data/repositories/modelcontextprotocol__typescript-sdk", "--filter", "@modelcontextprotocol/client", "run", "test"]],
        "selected_verifier_path": "@modelcontextprotocol/client typecheck + test",
        "mutation_text": "\nexport const __stage11999_forced_compile_error = ;\n",
        "mutation_kind": "typescript_compile_error",
    },
    {
        "id": "web_mcp_server_index_ts_syntax_guard",
        "language_family": "web_js_ts_html",
        "repo_family": "modelcontextprotocol__typescript-sdk",
        "root": "/data/repositories/modelcontextprotocol__typescript-sdk",
        "source_file": "packages/server/src/index.ts",
        "commands": [["pnpm", "--dir", "/data/repositories/modelcontextprotocol__typescript-sdk", "--filter", "@modelcontextprotocol/server", "run", "typecheck"], ["pnpm", "--dir", "/data/repositories/modelcontextprotocol__typescript-sdk", "--filter", "@modelcontextprotocol/server", "run", "test"]],
        "selected_verifier_path": "@modelcontextprotocol/server typecheck + test",
        "mutation_text": "\nexport const __stage11999_forced_compile_error = ;\n",
        "mutation_kind": "typescript_compile_error",
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


def run_cmd(spec_id: str, phase: str, idx: int, cmd: list[str], cwd: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env.update({
        "CUDA_VISIBLE_DEVICES": "",
        "NVIDIA_VISIBLE_DEVICES": "",
        "TMPDIR": "/data/tmp",
        "TEMP": "/data/tmp",
        "TMP": "/data/tmp",
    })
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=60, check=False)
        payload = {"command": cmd, "cwd": str(cwd), "returncode": proc.returncode, "timed_out": False, "duration_sec": round(time.time()-started, 3), "stdout_tail": (proc.stdout or "")[-4000:], "stderr_tail": (proc.stderr or "")[-4000:]}
    except subprocess.TimeoutExpired as exc:
        payload = {"command": cmd, "cwd": str(cwd), "returncode": 124, "timed_out": True, "duration_sec": round(time.time()-started, 3), "stdout_tail": exc.stdout if isinstance(exc.stdout, str) else "", "stderr_tail": exc.stderr if isinstance(exc.stderr, str) else ""}
    log = ROOT / "logs" / f"{spec_id}_{phase}_{idx}.json"
    write_json(log, payload)
    payload["log_path"] = str(log)
    return payload


def run_all(spec: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    cwd = Path(spec["root"])
    return [run_cmd(spec["id"], phase, i, cmd, cwd) for i, cmd in enumerate(spec["commands"])]


def all_pass(results: list[dict[str, Any]]) -> bool:
    return bool(results) and all(r.get("returncode") == 0 and not r.get("timed_out") for r in results)


def any_fail(results: list[dict[str, Any]]) -> bool:
    return bool(results) and any(r.get("returncode") not in (0, None) or r.get("timed_out") for r in results)


def shuffled(row_id: str) -> list[dict[str, str]]:
    values = [
        ("FAIL_TO_PASS", "baseline passed, controlled source mutation failed verifier, restored source passed"),
        ("PASS_TO_PASS", "focused verifier passed without controlled mutation evidence"),
        ("PASS_CURRENT_BUILD", "only build/typecheck passed; runnable verifier did not execute"),
        ("PASS_CURRENT_BUILD_AND_RUN", "build/typecheck and runnable verifier both passed without mutation failure"),
        ("NOT_EXERCISED", "candidate command did not exercise or collect the verifier"),
        ("INSUFFICIENT_EVIDENCE", "local environment is underhydrated, so no trustworthy transition is available"),
        ("FAIL_TO_FAIL", "baseline failed and mutant also failed"),
        ("VERIFIER_REMOVED", "verifier evidence was removed and the row should abstain"),
    ]
    keyed = [(hashlib.sha256(f"{row_id}::{i}::{v[0]}".encode()).hexdigest(), v) for i, v in enumerate(values)]
    return [{"label": label, "canonical_value": value, "value": value, "text": text, "role": "verifier_transition_status", "artifact_type": "controlled_mutation_status"} for label, (_, (value, text)) in zip(LABELS, sorted(keyed))]


def make_row(spec: dict[str, Any], baseline: list[dict[str, Any]], mutant: list[dict[str, Any]], restored: list[dict[str, Any]]) -> dict[str, Any]:
    row_id = f"stage11999::{spec['id']}::{hashlib.sha1(spec['source_file'].encode()).hexdigest()[:10]}"
    options = shuffled(row_id)
    target_label = next(o["label"] for o in options if o["canonical_value"] == "FAIL_TO_PASS")
    prompt = "\n".join([
        f"Language: {spec['language_family']}",
        "Perspective: transition_verifier_transition",
        "Task: choose the verifier transition proven by baseline, controlled source mutation, and restored-source evidence.",
        f"Repository family: {spec['repo_family']}",
        f"Source root: {spec['root']}",
        f"Source file mutated: {spec['source_file']}",
        f"Selected verifier: {spec['selected_verifier_path']}",
        f"Mutation kind: {spec['mutation_kind']}",
        "Baseline observations:",
        *[f"- rc={r['returncode']} timeout={r['timed_out']} cmd={' '.join(r['command'])} tail={(r.get('stdout_tail') or r.get('stderr_tail') or '')[-500:]}" for r in baseline],
        "Mutant observations:",
        *[f"- rc={r['returncode']} timeout={r['timed_out']} cmd={' '.join(r['command'])} tail={(r.get('stdout_tail') or r.get('stderr_tail') or '')[-500:]}" for r in mutant],
        "Restored observations:",
        *[f"- rc={r['returncode']} timeout={r['timed_out']} cmd={' '.join(r['command'])} tail={(r.get('stdout_tail') or r.get('stderr_tail') or '')[-500:]}" for r in restored],
        "Options:",
        *[f"{o['label']}. {o['text']}" for o in options],
        "Answer:",
    ])
    return {
        "row_id": row_id,
        "root_id": row_id,
        "root_lineage_key": f"stage11999::{spec['repo_family']}::{spec['source_file']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": spec["repo_family"],
        "repo_family": spec["repo_family"],
        "language_family": spec["language_family"],
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage11999_real_source_fail_to_pass_train_support_only",
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
        "opaque_options": options,
        "observed_verifier_transition": "FAIL_TO_PASS",
        "anti_cheat": {"deterministic_option_shuffle": True, "target_label_not_visible_before_options": True, "target_value_not_visible_before_options": True, "singleton_options": False, "restore_guarded_original_source": True, "train_support_only": True},
        "standalone_projection_source": {"projection_mode": "stage11999_real_source_fail_to_pass_mutations", "selected_verifier_path": spec["selected_verifier_path"], "source_file": spec["source_file"], "mutation_kind": spec["mutation_kind"], "observed_verifier_transition": "FAIL_TO_PASS", "tool_or_verifier_observation": {"baseline": baseline, "mutant": mutant, "restored": restored}},
    }


def run_spec(spec: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    root = Path(spec["root"])
    src = root / spec["source_file"]
    original = src.read_text()
    baseline = mutant = restored = []
    mutation_applied = False
    restored_matches = False
    try:
        baseline = run_all(spec, "baseline")
        src.write_text(original + spec["mutation_text"])
        mutation_applied = True
        mutant = run_all(spec, "mutant")
    finally:
        src.write_text(original)
        restored_matches = src.read_text() == original
    restored = run_all(spec, "restored")
    admitted = mutation_applied and restored_matches and all_pass(baseline) and any_fail(mutant) and all_pass(restored)
    card = {"spec": spec, "mutation_applied": mutation_applied, "restored_matches_original": restored_matches, "baseline_pass": all_pass(baseline), "mutant_failed": any_fail(mutant), "restored_pass": all_pass(restored), "admitted": admitted, "baseline": baseline, "mutant": mutant, "restored": restored}
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
        "stage": "stage11999_real_source_fail_to_pass_mutations",
        "created_at_utc": now(),
        "rows_path": str(ROWS),
        "rows_attempted": len(SPECS),
        "admitted_rows": len(rows),
        "language_counts": dict(Counter(r["language_family"] for r in rows)),
        "repo_family_counts": dict(Counter(r["repo_family"] for r in rows)),
        "status_counts": dict(Counter(r["observed_verifier_transition"] for r in rows)),
        "probe_cards": cards,
        "decision": "admit_real_source_fail_to_pass_train_support" if rows else "no_real_source_fail_to_pass_rows_admitted",
        "claim_boundary": "Real local source mutation with baseline/mutant/restored verifier evidence; train-support only, not strict/source-heldout independent task scale.",
        "next_stage_recommendation": {"stage": "stage12000_fail_to_pass_admission_and_rollup", "action": "Audit restore guards, admit rows, and merge into transition support inventory."},
    }
    write_json(SUMMARY, summary)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps({k: summary[k] for k in ["decision", "admitted_rows", "language_counts", "status_counts", "next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
