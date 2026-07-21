#!/usr/bin/env python3
"""Build a conservative verifier rehydration queue for Stage12201 patch contexts.

No commands are executed. Rows remain level_2 until verifier output is captured
from the same root/commit lineage.
"""
from __future__ import annotations

import json
import shlex
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12217_patch_trace_verifier_rehydration_queue"
SRC = ROOT / "runs/local/artifacts/stage12201_patch_evidence_recovery/recovered_episode_records.jsonl"
TRACES = ROOT / "runs/local/artifacts/stage12201_patch_evidence_recovery/recovered_patch_traces.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

HEAVY_REPOS = {
    "Megatron-LM", "cuda-quantum", "Model-Optimizer", "NeMo", "TensorRT-LLM", "TransformerEngine", "DeepSpeed", "torchtune", "transformers"
}

PREFERRED_REPOS = {
    "openai-agents-python", "pip", "sphinx", "langchain", "autogen", "agent-framework", "agent-governance-toolkit",
    "distilabel", "archai", "lerobot", "llama-stack", "mem0", "cccl", "cpython"
}


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if line:
                yield line_no, json.loads(line)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def load_traces() -> dict[str, dict[str, Any]]:
    return {r["episode_id"]: r for _, r in iter_jsonl(TRACES)}


def choose_test(row: dict[str, Any]) -> str | None:
    tests = row.get("selected_tests") or []
    py = [t for t in tests if isinstance(t, str) and t.endswith(".py") and "/conftest.py" not in t and "fixtures" not in t.lower()]
    if py:
        return py[0]
    cpp = [t for t in tests if isinstance(t, str) and (t.endswith(".cpp") or t.endswith(".cc"))]
    if cpp:
        return cpp[0]
    ts = [t for t in tests if isinstance(t, str) and (t.endswith(".test.ts") or t.endswith(".spec.ts") or t.endswith(".ts"))]
    if ts:
        return ts[0]
    return None


def command_for(row: dict[str, Any], test: str) -> tuple[list[str] | None, str, list[str]]:
    lang = row.get("language")
    repo = row.get("repo_family")
    blockers: list[str] = []
    if repo in HEAVY_REPOS:
        blockers.append("heavy_gpu_or_large_framework_risk")
    if lang == "python":
        if repo == "cpython":
            return (["./python", "-m", "test", "-v", Path(test).stem.replace("test_", "test_")], "cpython_test_runner", blockers + ["requires_built_cpython_binary"])
        return (["python", "-m", "pytest", "-q", "-c", "/dev/null", "-o", "cache_dir=/data/tmp/stage12217_pytest_cache", test], "pytest_single_file", blockers)
    if lang == "c_cpp":
        return (None, "manual_ctest_needed", blockers + ["no_existing_build_dir_or_ctest_target_in_stage12201"])
    if lang == "web_js_ts_html":
        return (["npm", "test", "--", test], "npm_test_guess", blockers + ["package_manager_workspace_unknown"])
    return (None, "unknown_language", blockers + ["unknown_language"])


def score(row: dict[str, Any], command: list[str] | None, blockers: list[str], root_exists: bool, test: str | None) -> int:
    s = 0
    if root_exists: s += 5
    if test: s += 3
    if command: s += 3
    if row.get("repo_family") in PREFERRED_REPOS: s += 3
    if row.get("repo_family") in HEAVY_REPOS: s -= 5
    s -= len(blockers)
    return s


def main() -> int:
    traces = load_traces()
    queue = []
    blocked = []
    for line_no, row in iter_jsonl(SRC):
        trace = traces.get(row["episode_id"], {})
        root = Path(row.get("root_id") or "")
        root_exists = root.exists()
        test = choose_test(row)
        command, verifier_kind, blockers = command_for(row, test) if test else (None, "no_selected_test_command", ["no_runnable_selected_test_candidate"])
        if not root_exists:
            blockers.append("local_root_missing")
        if command and root_exists and not blockers:
            feasibility = "possible_level_3_if_verifier_rehydrated"
        elif command and root_exists and all(b in {"heavy_gpu_or_large_framework_risk", "package_manager_workspace_unknown", "requires_built_cpython_binary"} for b in blockers):
            feasibility = "possible_level_3_if_blockers_resolved"
        else:
            feasibility = "blocked_or_level_2_only"
        item = {
            "episode_id": row["episode_id"],
            "repo_family": row.get("repo_family"),
            "language_family": row.get("language"),
            "root_id": row.get("root_id"),
            "root_exists": root_exists,
            "repo_commit_before": row.get("repo_commit_before"),
            "repo_commit_after": row.get("repo_commit_after"),
            "patch_diff_ref": trace.get("diff_ref"),
            "patch_diff_digest": trace.get("diff_digest"),
            "changed_paths": row.get("changed_paths") or [],
            "selected_test_candidate": test,
            "proposed_cwd": row.get("root_id"),
            "proposed_command_argv": command,
            "proposed_command": " ".join(shlex.quote(x) for x in command) if command else None,
            "cpu_only": True,
            "gpu_requirement": "none",
            "network_required": False,
            "verifier_kind": verifier_kind,
            "classification": feasibility,
            "blockers": blockers,
            "admission_level_current": row.get("admission_level"),
            "admission_level_after_successful_rehydration": "level_3_single_step_closed_loop_with_patch_trace" if feasibility.startswith("possible_level_3") else None,
            "score": score(row, command, blockers, root_exists, test),
            "source_record_ref": row.get("source_record_ref"),
        }
        if feasibility.startswith("possible"):
            queue.append(item)
        else:
            blocked.append(item)
    queue.sort(key=lambda r: (-r["score"], str(r["repo_family"])))
    blocked.sort(key=lambda r: (-r["score"], str(r["repo_family"])))
    top = queue[:10]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT_DIR / "patch_trace_verifier_rehydration_queue.jsonl", queue)
    write_jsonl(OUT_DIR / "top10_patch_trace_verifier_rehydration_queue.jsonl", top)
    write_jsonl(OUT_DIR / "blocked_patch_trace_rehydration_candidates.jsonl", blocked)
    summary = {
        "stage": STAGE,
        "decision": "patch_trace_rehydration_queue_ready" if queue else "blocked_no_rehydration_candidates",
        "source_stage": "stage12201_patch_evidence_recovery",
        "candidate_count": len(queue) + len(blocked),
        "queue_count": len(queue),
        "top10_count": len(top),
        "blocked_count": len(blocked),
        "classification_counts": dict(Counter(r["classification"] for r in queue + blocked)),
        "language_counts": dict(Counter(r["language_family"] for r in queue)),
        "repo_family_top10": [r["repo_family"] for r in top],
        "training_allowed": False,
        "tests_executed": False,
        "claim_boundary": "Queue only. Stage12201 rows remain level_2 until same-root verifier commands are executed and admitted.",
        "artifact_paths": {
            "queue": str(OUT_DIR / "patch_trace_verifier_rehydration_queue.jsonl"),
            "top10": str(OUT_DIR / "top10_patch_trace_verifier_rehydration_queue.jsonl"),
            "blocked": str(OUT_DIR / "blocked_patch_trace_rehydration_candidates.jsonl"),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if queue else 2

if __name__ == "__main__":
    raise SystemExit(main())
