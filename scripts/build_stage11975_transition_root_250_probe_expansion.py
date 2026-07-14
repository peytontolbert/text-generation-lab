#!/usr/bin/env python3
"""Expand source-backed transition-root probes by trying multiple focused tests per root."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11975
NAME = "stage11975_transition_root_250_probe_expansion"
OUT = ART / NAME
SUMMARY = OUT / "transition_root_250_probe_expansion.json"
ROWS = OUT / "transition_root_250_probe_expansion_review_rows.jsonl"
QUEUE = ART / "stage11970_transition_root_250_materialization_plan/transition_root_250_materialization_queue.jsonl"
TMP = Path(os.environ.get("TMPDIR") or "/data/tmp") / NAME
LABELS = list("ABCDEFGH")
PRUNE = {".git", "node_modules", "target", "build", "dist", "__pycache__", ".pytest_cache", ".mypy_cache"}
PROTECTED = {"tokenizers", "candle/candle-core", "candle/candle-flash-attn", "candle/candle-nn", "openhands__openhands", "llama_stack", "code_assist"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def footprint(path: Path) -> int:
    count = 0
    for root, dirs, files in os.walk(path):
        rp = Path(root)
        if set(rp.parts) & PRUNE:
            dirs[:] = []
            continue
        depth = len(rp.relative_to(path).parts) if rp != path else 0
        if depth > 4:
            dirs[:] = []
            continue
        count += len(files)
    return count


def test_targets(path: Path, max_targets: int) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for root, dirs, files in os.walk(path):
        rp = Path(root)
        if set(rp.parts) & PRUNE:
            dirs[:] = []
            continue
        depth = len(rp.relative_to(path).parts) if rp != path else 0
        if depth > 5:
            dirs[:] = []
            continue
        for f in files:
            lf = f.lower()
            if not ((lf.startswith("test_") and lf.endswith(".py")) or lf.endswith("_test.py")):
                continue
            full = rp / f
            try:
                text = full.read_text(encoding="utf-8", errors="replace")[:5000]
                size = full.stat().st_size
            except OSError:
                text = ""
                size = 999999
            skip_penalty = 100000 if "skipif" in text or "pytest.mark.skip" in text else 0
            dep_penalty = 50000 if any(x in text for x in ["subprocess.run", "requests.", "docker", "uv ", "playwright"]) else 0
            candidates.append((skip_penalty + dep_penalty + size, str(full.relative_to(path))))
    return [target for _, target in sorted(candidates)[:max_targets]]


def run_pytest(cwd: Path, target: str, log_name: str, run: bool) -> dict[str, Any]:
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "CUDA_VISIBLE_DEVICES": "",
        "NVIDIA_VISIBLE_DEVICES": "",
        "PYTHONPATH": os.pathsep.join([str(cwd), str(cwd / "src"), env.get("PYTHONPATH", "")]),
        "PYTHONPYCACHEPREFIX": str(TMP / "pycache"),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "TMPDIR": str(TMP), "TEMP": str(TMP), "TMP": str(TMP),
    })
    cmd = ["python", "-m", "pytest", "-q", "-c", "/dev/null", "-o", f"cache_dir={TMP / 'pytest_cache'}"]
    if not run:
        cmd.append("--collect-only")
    cmd.append(target)
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=60 if run else 30, check=False)
        rc, timed_out, stdout, stderr = proc.returncode, False, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        rc, timed_out = 124, True
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
    payload = {"command": cmd, "cwd": str(cwd), "returncode": rc, "timed_out": timed_out, "duration_sec": round(time.time()-started,3), "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-4000:]}
    path = OUT / "logs" / f"{log_name}.json"
    write_json(path, payload)
    return {**payload, "log_path": rel(path)}


def passed_tests(result: dict[str, Any]) -> bool:
    combined = f"{result.get('stdout_tail') or ''}\n{result.get('stderr_tail') or ''}"
    return result.get("returncode") == 0 and " passed" in combined and " skipped" not in combined


def collected_tests(result: dict[str, Any]) -> bool:
    combined = f"{result.get('stdout_tail') or ''}\n{result.get('stderr_tail') or ''}"
    return result.get("returncode") == 0 and " collected" in combined


def shuffled(row_id: str, values: list[str]) -> list[dict[str, str]]:
    keyed = [(hashlib.sha256(f"{row_id}::{i}::{v}".encode()).hexdigest(), v) for i, v in enumerate(values)]
    return [{"label": label, "value": value} for label, (_, value) in zip(LABELS, sorted(keyed))]


def make_row(candidate: dict[str, Any], target: str, transition: str, obs: dict[str, Any]) -> dict[str, Any]:
    row_id = f"stage11975::{candidate['repo_family_key']}::{candidate['materialization_id']}::{transition}::{hashlib.sha1(target.encode()).hexdigest()[:10]}"
    if transition == "PASS_TO_PASS":
        target_value = "focused verifier executed from local source and passed"
        wrong = ["only collection/build succeeded; verifier body did not execute", "verifier failed or was underhydrated", "insufficient evidence because no local-source verifier was observed"]
    else:
        target_value = "focused verifier collected from local source but was not executed"
        wrong = ["focused verifier executed and passed", "verifier failed or was underhydrated", "insufficient evidence because no local-source verifier was observed"]
    options = shuffled(row_id, [target_value, *wrong])
    target_label = next(o['label'] for o in options if o['value'] == target_value)
    return {
        "row_id": row_id,
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": candidate["repo_family_key"],
        "repo_family": candidate["repo_family_key"],
        "language_family": (candidate.get("language_guess") or ["unknown"])[0],
        "task_type": "transition_verifier_transition",
        "surface": "transition_root_250_probe_expansion_bounded_choice",
        "split": "train",
        "split_role": "review_queue_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "selected_test_anchor": True,
        "verifier_anchor": True,
        "input_text": "\n".join([
            f"Language: {(candidate.get('language_guess') or ['unknown'])[0]}",
            "Perspective: transition_verifier_transition",
            "Task: choose the verifier transition supported by the observed local-source command.",
            f"Repository family: {candidate['repo_family_key']}",
            f"Source root: {candidate['source_path']}",
            f"Selected verifier: {target}",
            f"Observed command: {' '.join(obs.get('command') or [])}",
            f"Return code: {obs.get('returncode')}",
            f"Stdout tail: {(obs.get('stdout_tail') or '')[-1000:]}",
            "Options:",
            *[f"{o['label']}. {o['value']}" for o in options],
            "Answer:",
        ]),
        "target_text": target_label,
        "decoder_text": target_label,
        "opaque_options": options,
        "target_semantic_value": target_value,
        "observed_verifier_transition": transition,
        "anti_cheat": {"deterministic_option_shuffle": True, "target_label_not_visible_before_options": True, "target_value_not_visible_before_options": True, "singleton_options": False, "local_source_pythonpath": True, "review_queue_only": True},
        "standalone_projection_source": {"projection_mode": NAME, "selected_verifier_path": target, "observed_verifier_transition": transition, "tool_or_verifier_observation": obs},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--targets-per-root", type=int, default=5)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    queue = [r for r in read_jsonl(QUEUE) if r.get("repo_family_key") not in PROTECTED]
    queue = sorted(queue, key=lambda r: (footprint(Path(r["source_path"])), r["source_path"]))[: args.limit]
    rows: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    for candidate in queue:
        path = Path(candidate["source_path"])
        card = {"candidate": candidate, "targets": [], "admitted": False}
        for i, target in enumerate(test_targets(path, args.targets_per_root), start=1):
            collect = run_pytest(path, target, f"{candidate['materialization_id']}_{i}_collect", run=False)
            item = {"target": target, "collect": collect}
            if collected_tests(collect):
                run = run_pytest(path, target, f"{candidate['materialization_id']}_{i}_run", run=True)
                item["run"] = run
                if passed_tests(run):
                    rows.append(make_row(candidate, target, "PASS_TO_PASS", run))
                    card["admitted"] = True
                    card["admitted_transition"] = "PASS_TO_PASS"
                    card["targets"].append(item)
                    break
                else:
                    rows.append(make_row(candidate, target, "PASS_CURRENT_BUILD", collect))
            card["targets"].append(item)
    write_jsonl(ROWS, rows)
    counts = Counter(r.get("observed_verifier_transition") for r in rows)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "probe_expansion_complete_review_rows_only",
        "probe_policy": {"limit": args.limit, "targets_per_root": args.targets_per_root, "pytest_config": "/dev/null", "local_source_pythonpath": True, "no_training": True},
        "summary": {"roots_attempted": len(queue), "review_rows": len(rows), "transition_counts": dict(counts), "pass_to_pass_roots": len({r.get("repo_family") for r in rows if r.get("observed_verifier_transition") == "PASS_TO_PASS"})},
        "probe_cards": cards,
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS), "logs": rel(OUT / "logs")},
        "next_stage_recommendation": {"stage": "stage11976_transition_root_250_review_package_gate", "action": "Merge Stage11972 and Stage11975 review rows, dedupe roots, and admit only source-backed rows with clean candidate geometry."},
    }
    write_json(SUMMARY, artifact)
    print(json.dumps({"decision": artifact["decision"], "summary": artifact["summary"], "next": artifact["next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
