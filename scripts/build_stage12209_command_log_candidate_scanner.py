#!/usr/bin/env python3
"""Scan local command-log artifacts for additional Level-3 pass/fail candidates.

Metadata-only: no command execution, no training. Produces candidate inventory for
manual/admission-stage wrapping.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12209_command_log_candidate_scanner"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
CONSUMED_HINTS = {
    "stage12143__python__PyCQA_flake8__selected_normalize_pypi_name.json",
    "stage12143__python__PyCQA_flake8__selected_inline_noqa.json",
    "stage12118__python__034__pytest_dev_pluggy__pytest_run_refined.json",
    "stage12118__c_cpp__002__Neargye_magic_enum__exact_selected_ctest.json",
    "stage12118__c_cpp__019__fastfloat_fast_float__exact_selected_ctest.json",
}
HELDOUT_MARKERS = ("heldout", "strict_eval", "sealed", "eval")
COMMAND_MARKERS = ("pytest", "ctest", "cargo test", "npm test", "vitest", "pnpm test", "node --test", "python -m pytest")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(errors="ignore"))
    except Exception:
        return None


def command_text(row: dict[str, Any]) -> str:
    cmd = row.get("command_text") or row.get("command") or row.get("cmd")
    if isinstance(cmd, list):
        return " ".join(map(str, cmd))
    return str(cmd or "")


def exit_code(row: dict[str, Any]) -> int | None:
    for k in ("exit_code", "returncode", "return_code"):
        if k in row and row[k] is not None:
            try:
                return int(row[k])
            except Exception:
                return None
    return None


def stdout_tail(row: dict[str, Any]) -> str:
    return str(row.get("stdout_tail") or row.get("stdout") or row.get("output_preview") or "")


def stderr_tail(row: dict[str, Any]) -> str:
    return str(row.get("stderr_tail") or row.get("stderr") or "")


def infer_language(path: Path, row: dict[str, Any], cmd: str) -> str:
    if row.get("language"):
        return str(row.get("language"))
    text = " ".join([str(path), cmd, str(row.get("repo_family") or "")]).lower()
    if "cargo test" in text or "rust" in text:
        return "rust"
    if "ctest" in text or "cmake" in text or "c_cpp" in text or "cpp" in text:
        return "c_cpp"
    if "npm" in text or "vitest" in text or "pnpm" in text or "typescript" in text or "web" in text:
        return "web_js_ts_html"
    if "pytest" in text or "python" in text:
        return "python"
    return "unknown"


def selected_like(cmd: str) -> bool:
    low = cmd.lower()
    return any(marker in low for marker in COMMAND_MARKERS)


def is_heldout(path: Path, row: dict[str, Any]) -> bool:
    text = (str(path) + " " + json.dumps(row, sort_keys=True, default=str)[:2000]).lower()
    return any(marker in text for marker in HELDOUT_MARKERS) or row.get("do_not_train") is True


def repo_family(path: Path, row: dict[str, Any]) -> str:
    return str(row.get("repo_family") or row.get("git_repo_family") or row.get("candidate_id") or row.get("queue_id") or path.parent.parent.name)


def iter_candidate_json_files() -> list[Path]:
    files = []
    for path in (ROOT / "runs/local/artifacts").rglob("*.json"):
        s = str(path)
        if any(tok in s for tok in ("command_logs", "logs")) or any(tok in path.name for tok in ("result", "execution", "verifier", "smoke")):
            files.append(path)
    return files


def main() -> int:
    rows = []
    rejected = []
    for path in iter_candidate_json_files():
        if path.name in CONSUMED_HINTS:
            continue
        data = read_json(path)
        if not isinstance(data, dict):
            continue
        cmd = command_text(data)
        rc = exit_code(data)
        if not cmd or rc is None:
            continue
        if not selected_like(cmd):
            rejected.append({"path": str(path), "reason": "command_not_selected_verifier_like", "command": cmd[:200]})
            continue
        if data.get("timeout") is True or data.get("timed_out") is True:
            rejected.append({"path": str(path), "reason": "timeout", "command": cmd[:200]})
            continue
        out = stdout_tail(data); err = stderr_tail(data)
        if not out and not err:
            rejected.append({"path": str(path), "reason": "missing_stdout_stderr_tail", "command": cmd[:200]})
            continue
        heldout = is_heldout(path, data)
        lang = infer_language(path, data, cmd)
        status = "PASS_CURRENT_STATE" if rc == 0 else "FAIL_CURRENT_STATE"
        rows.append({
            "path": str(path.relative_to(ROOT)),
            "repo_family": repo_family(path, data),
            "language": lang,
            "command": cmd,
            "cwd": data.get("cwd") or data.get("workdir"),
            "returncode": rc,
            "status": status,
            "heldout_or_do_not_train_risk": heldout,
            "stdout_tail_preview": out[-300:],
            "stderr_tail_preview": err[-300:],
        })
    rows.sort(key=lambda r: (r["heldout_or_do_not_train_risk"], r["language"], r["repo_family"], r["path"]))
    clean = [r for r in rows if not r["heldout_or_do_not_train_risk"]]
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "candidate_command_logs.jsonl", rows)
    write_jsonl(OUT / "clean_candidate_command_logs.jsonl", clean)
    write_jsonl(OUT / "rejected_command_logs.jsonl", rejected[:1000])
    summary = {
        "stage": STAGE,
        "decision": "candidate_command_logs_indexed",
        "candidate_count": len(rows),
        "clean_candidate_count": len(clean),
        "rejected_count_sampled": min(len(rejected), 1000),
        "language_counts": dict(Counter(r["language"] for r in rows)),
        "clean_language_counts": dict(Counter(r["language"] for r in clean)),
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "clean_status_counts": dict(Counter(r["status"] for r in clean)),
        "top_clean_repo_families": Counter(r["repo_family"] for r in clean).most_common(20),
        "artifact_paths": {
            "all_candidates": str(OUT / "candidate_command_logs.jsonl"),
            "clean_candidates": str(OUT / "clean_candidate_command_logs.jsonl"),
            "rejected_sample": str(OUT / "rejected_command_logs.jsonl"),
        },
        "claim_boundary": "Inventory only; no rows admitted, no training, no eval claim.",
    }
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
