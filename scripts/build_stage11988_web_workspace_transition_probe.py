#!/usr/bin/env python3
"""Workspace-aware web transition materialization for pnpm/npm monorepos."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11988
NAME = "stage11988_web_workspace_transition_probe"
OUT = ART / NAME
SUMMARY = OUT / "web_workspace_transition_probe.json"
ROWS = OUT / "web_workspace_transition_rows.jsonl"
TMP = Path(os.environ.get("TMPDIR") or "/data/tmp") / NAME
LABELS = list("ABCDEFGHI")
STATUS_OPTIONS = [
    ("PASS_TO_PASS", "focused web verifier/test executed from local workspace source and passed"),
    ("PASS_CURRENT_BUILD", "typecheck/build/static check completed successfully but no test body executed"),
    ("PASS_CURRENT_BUILD_AND_RUN", "build/typecheck completed and a runnable verifier also passed"),
    ("FAIL_TO_FAIL", "web verifier ran and failed in current local source state"),
    ("NOT_EXERCISED", "web command did not exercise the selected verifier path"),
    ("INSUFFICIENT_EVIDENCE", "workspace dependencies or package manager state are underhydrated"),
    ("VERIFIER_REMOVED", "verifier evidence was removed and row should abstain"),
]
CANDIDATES = [
    {"repo_family": "modelcontextprotocol__typescript-sdk", "workspace": "/data/repositories/modelcontextprotocol__typescript-sdk", "package": "@modelcontextprotocol/core", "script": "test", "kind": "pnpm_test"},
    {"repo_family": "modelcontextprotocol__typescript-sdk", "workspace": "/data/repositories/modelcontextprotocol__typescript-sdk", "package": "@modelcontextprotocol/client", "script": "test", "kind": "pnpm_test"},
    {"repo_family": "modelcontextprotocol__typescript-sdk", "workspace": "/data/repositories/modelcontextprotocol__typescript-sdk", "package": "@modelcontextprotocol/server", "script": "test", "kind": "pnpm_test"},
    {"repo_family": "modelcontextprotocol__typescript-sdk", "workspace": "/data/repositories/modelcontextprotocol__typescript-sdk", "package": "@modelcontextprotocol/middleware-node", "script": "test", "kind": "pnpm_test"},
    {"repo_family": "modelcontextprotocol__typescript-sdk", "workspace": "/data/repositories/modelcontextprotocol__typescript-sdk", "package": "@modelcontextprotocol/middleware-hono", "script": "test", "kind": "pnpm_test"},
    {"repo_family": "modelcontextprotocol__typescript-sdk", "workspace": "/data/repositories/modelcontextprotocol__typescript-sdk", "package": "@modelcontextprotocol/examples-shared", "script": "typecheck", "kind": "pnpm_typecheck"},
    {"repo_family": "modelcontextprotocol__typescript-sdk", "workspace": "/data/repositories/modelcontextprotocol__typescript-sdk", "package": "@modelcontextprotocol/examples-server", "script": "typecheck", "kind": "pnpm_typecheck"},
    {"repo_family": "modelcontextprotocol__typescript-sdk", "workspace": "/data/repositories/modelcontextprotocol__typescript-sdk", "package": "@modelcontextprotocol/test-integration", "script": "test", "kind": "pnpm_test"},
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


def run_cmd(candidate: dict[str, str]) -> dict[str, Any]:
    cmd = ["pnpm", "--dir", candidate["workspace"], "--filter", candidate["package"], "run", candidate["script"]]
    log_dir = OUT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({"CUDA_VISIBLE_DEVICES": "", "NVIDIA_VISIBLE_DEVICES": "", "TMPDIR": str(TMP), "TEMP": str(TMP), "TMP": str(TMP), "CI": "1", "NO_COLOR": "1"})
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(Path(candidate["workspace"])), env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=90, check=False)
        rc = proc.returncode; stdout = proc.stdout or ""; stderr = proc.stderr or ""; timed_out = False
    except subprocess.TimeoutExpired as exc:
        rc = 124; stdout = exc.stdout if isinstance(exc.stdout, str) else ""; stderr = exc.stderr if isinstance(exc.stderr, str) else ""; timed_out = True
    payload = {"command": cmd, "cwd": candidate["workspace"], "returncode": rc, "timed_out": timed_out, "duration_sec": round(time.time()-started,3), "stdout_tail": stdout[-6000:], "stderr_tail": stderr[-4000:]}
    log_path = log_dir / (candidate["package"].replace("/", "__").replace("@", "at_") + "_" + candidate["script"] + ".json")
    write_json(log_path, payload)
    return {**payload, "log_path": rel(log_path)}


def test_count(text: str) -> int | None:
    match = re.search(r"Tests\s+(\d+)\s+passed", text)
    if match:
        return int(match.group(1))
    total = 0; found = False
    for m in re.finditer(r"(\d+)\s+passed", text):
        found = True; total += int(m.group(1))
    return total if found else None


def classify(candidate: dict[str, str], result: dict[str, Any]) -> str:
    text = f"{result.get('stdout_tail') or ''}\n{result.get('stderr_tail') or ''}"
    low = text.lower()
    if result.get("returncode") == 0 and not result.get("timed_out"):
        if candidate["kind"].endswith("test") and (test_count(text) or 0) > 0:
            return "PASS_TO_PASS"
        return "PASS_CURRENT_BUILD"
    if result.get("timed_out") or any(s in low for s in ["command not found", "cannot find module", "no such file", "not found", "missing script", "node_modules"]):
        return "INSUFFICIENT_EVIDENCE"
    return "NOT_EXERCISED"


def shuffled_options(row_id: str, target_status: str) -> tuple[list[dict[str, Any]], str]:
    keyed = []
    for status, text in STATUS_OPTIONS:
        keyed.append((hashlib.sha256(f"{row_id}::{status}".encode()).hexdigest(), status, text))
    options=[]; target_label=""
    for label, (_, status, text) in zip(LABELS, sorted(keyed)):
        option={"label": label, "value": status, "text": text, "role": "verifier_transition_status", "artifact_type": "web_workspace_verifier_status", "canonical_value": status}
        options.append(option)
        if status == target_status:
            target_label = label
    return options, target_label


def make_row(candidate: dict[str, str], result: dict[str, Any]) -> dict[str, Any]:
    status = classify(candidate, result)
    base = f"stage11988::{candidate['repo_family']}::{candidate['package']}::{candidate['script']}::{status}"
    row_id = base + "::" + hashlib.sha1((base + str(result.get('returncode'))).encode()).hexdigest()[:10]
    options, target_label = shuffled_options(row_id, status)
    text = str(result.get('stdout_tail') or '') + "\n" + str(result.get('stderr_tail') or '')
    count = test_count(text)
    input_text = (
        "Language: web_js_ts_html\n"
        "Perspective: transition_verifier_transition\n"
        "Task: choose the verifier transition supported by the observed workspace-aware web command.\n"
        f"Repository family: {candidate['repo_family']}\n"
        f"Workspace root: {candidate['workspace']}\n"
        f"Package: {candidate['package']}\n"
        f"Script: {candidate['script']}\n"
        f"Observed command: {' '.join(result.get('command') or [])}\n"
        f"Return code: {result.get('returncode')}\n"
        f"Observed test count: {count}\n"
        f"Stdout tail: {str(result.get('stdout_tail') or '')[-1400:]}\n"
        f"Stderr tail: {str(result.get('stderr_tail') or '')[-800:]}\n"
        "Options:\n" + "\n".join(f"{o['label']}. {o['text']}" for o in options) + "\nAnswer:"
    )
    return {
        "row_id": row_id,
        "root_id": base,
        "root_lineage_key": f"stage11988::{candidate['repo_family']}::{candidate['package']}",
        "source_root_id": base,
        "source_bundle_id": base,
        "repo_id": candidate["repo_family"],
        "repo_family": candidate["repo_family"],
        "language_family": "web_js_ts_html",
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage11988_review_queue_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "observed_verifier_transition": status,
        "selected_test_anchor": status == "PASS_TO_PASS",
        "input_text": input_text,
        "prompt_text": input_text,
        "decoder_text": target_label,
        "target_text": target_label,
        "bounded_choice_target_label": target_label,
        "target": {"bounded_choice_target_label": target_label, "decoder_text": target_label, "semantic_value": status},
        "opaque_options": options,
        "standalone_projection_source": {"projection_mode": "stage11988_web_workspace_transition_probe", "observed_verifier_transition": status, "selected_verifier_path": f"{candidate['package']}#{candidate['script']}", "tool_or_verifier_observation": result, "opaque_options": options, "gold_label": target_label, "gold_value": status, "observed_test_count": count},
        "loss_mask": {"bounded_choice_aux": True, "decoder_ce": True, "structured_aux": True, "transition_projection": True},
        "anti_cheat": {"deterministic_option_shuffle": True, "singleton_options": False, "target_label_not_visible_before_options": True, "target_value_not_visible_before_options": False, "target_value_visible_as_observed_verifier_result": True, "review_queue_only": True, "not_merged_into_train": True},
        "stage11988_candidate": candidate,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True); TMP.mkdir(parents=True, exist_ok=True)
    rows=[]; cards=[]
    for cand in CANDIDATES:
        result = run_cmd(cand)
        row = make_row(cand, result)
        rows.append(row)
        cards.append({"candidate": cand, "transition": row["observed_verifier_transition"], "returncode": result["returncode"], "timed_out": result["timed_out"], "log_path": result["log_path"]})
    write_jsonl(ROWS, rows)
    artifact={
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "web_workspace_transition_probe_complete_review_only",
        "claim_boundary": "review/admission supply only; no training or promotion claim",
        "summary": {"rows_emitted": len(rows), "status_counts": dict(Counter(r["observed_verifier_transition"] for r in rows)), "repo_family_counts": dict(Counter(r["repo_family"] for r in rows)), "package_counts": dict(Counter((r["stage11988_candidate"]["package"]) for r in rows))},
        "candidate_cards": cards,
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS), "logs": rel(OUT / "logs")},
        "next_stage_recommendation": {"stage": "stage11989_web_workspace_admission_audit", "action": "Admit only rows with real test counts or clean typecheck/build evidence; merge into support v3 without training unless diagnostic."},
    }
    write_json(SUMMARY, artifact)
    print(json.dumps({"decision": artifact["decision"], "summary": artifact["summary"], "next": artifact["next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
