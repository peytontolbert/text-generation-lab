#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11613
NAME = "stage11613_web_fail_to_pass_mutation_executor"
OUT = ART / NAME
SUMMARY = OUT / "web_fail_to_pass_mutation_executor.json"
RESULTS = OUT / "web_fail_to_pass_mutation_results.jsonl"
ADMITTED = OUT / "web_fail_to_pass_mutation_admitted_roots.jsonl"
REJECTED = OUT / "web_fail_to_pass_mutation_rejected_roots.jsonl"
WORK_ITEMS = ART / "stage11612_web_fail_to_pass_mutation_materialization_request/web_fail_to_pass_mutation_work_items.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_absolute() and path.is_relative_to(ROOT) else str(path)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(command: list[str], cwd: Path, log_path: Path, timeout_s: int) -> dict[str, Any]:
    started = time.time()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(command, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout_s)
        output = proc.stdout or ""
        log_path.write_text(output, encoding="utf-8", errors="replace")
        return {
            "command": command,
            "cwd": str(cwd),
            "returncode": int(proc.returncode),
            "elapsed_seconds": round(time.time() - started, 3),
            "log_path": rel(log_path),
            "output_preview": output[:2000],
        }
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        output += "\n[TIMEOUT]\n"
        log_path.write_text(output, encoding="utf-8", errors="replace")
        return {
            "command": command,
            "cwd": str(cwd),
            "returncode": 124,
            "elapsed_seconds": round(time.time() - started, 3),
            "log_path": rel(log_path),
            "output_preview": output[:2000],
            "timeout": True,
        }


def materialize_mutant(original: bytes, work_item: dict[str, Any]) -> bytes:
    marker = f"stage11613_fail_to_pass_mutant::{work_item.get('root_id')}"
    suffix = f"\n\n/* {marker} */\nthrow new Error({json.dumps(marker)});\n".encode("utf-8")
    return original + suffix


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-items", type=int, default=1)
    parser.add_argument("--timeout-s", type=int, default=90)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--append", action="store_true", help="Append to existing Stage11613 result files instead of clearing them.")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    if not args.append:
        for path in (RESULTS, ADMITTED, REJECTED):
            path.write_text("", encoding="utf-8")
    else:
        for path in (RESULTS, ADMITTED, REJECTED):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
    work_items = load_jsonl(WORK_ITEMS)
    selected = work_items[args.start:args.start + args.max_items]
    admitted = []
    rejected = []
    prior_results = load_jsonl(RESULTS) if args.append else []
    for index, item in enumerate(selected, start=args.start):
        repo_path = Path(str(item.get("repo_path") or ""))
        source_rel = str(item.get("candidate_change_surface") or "")
        source_path = repo_path / source_rel
        command = [str(x) for x in item.get("baseline_pass_command") or []]
        root_safe = str(item.get("root_id") or f"idx_{index}").replace("/", "_").replace(":", "_")
        result: dict[str, Any] = {
            "stage": STAGE,
            "work_item_index": index,
            "work_item_id": item.get("work_item_id"),
            "root_id": item.get("root_id"),
            "repo_path": str(repo_path),
            "candidate_change_surface": source_rel,
            "selected_verifier_path": item.get("selected_verifier_path"),
            "started_at_utc": now(),
            "admitted": False,
            "blockers": [],
        }
        if not repo_path.exists():
            result["blockers"].append("repo_path_missing")
        if not source_path.exists():
            result["blockers"].append("candidate_source_missing")
        if not command:
            result["blockers"].append("missing_baseline_command")
        if result["blockers"]:
            append_jsonl(REJECTED, result)
            append_jsonl(RESULTS, result)
            rejected.append(result)
            continue
        original = source_path.read_bytes()
        result["original_sha256"] = sha256_bytes(original)
        logs_dir = OUT / "logs" / root_safe
        baseline = run_command(command, repo_path, logs_dir / "baseline_pass.log", args.timeout_s)
        result["baseline"] = baseline
        if baseline["returncode"] != 0:
            result["blockers"].append("baseline_did_not_pass")
            append_jsonl(REJECTED, result)
            append_jsonl(RESULTS, result)
            rejected.append(result)
            continue
        mutant = materialize_mutant(original, item)
        source_path.write_bytes(mutant)
        result["mutant_sha256"] = sha256_bytes(mutant)
        try:
            mutant_run = run_command(command, repo_path, logs_dir / "mutant_fail.log", args.timeout_s)
            result["mutant"] = mutant_run
        finally:
            source_path.write_bytes(original)
        restored = source_path.read_bytes()
        result["restored_sha256"] = sha256_bytes(restored)
        restore_ok = restored == original
        result["restore_byte_exact"] = restore_ok
        restored_run = run_command(command, repo_path, logs_dir / "restored_pass.log", args.timeout_s)
        result["restored"] = restored_run
        if mutant_run["returncode"] == 0:
            result["blockers"].append("mutant_did_not_fail")
        if not restore_ok:
            result["blockers"].append("restore_not_byte_exact")
        if restored_run["returncode"] != 0:
            result["blockers"].append("restored_did_not_pass")
        if not result["blockers"]:
            result["admitted"] = True
            result["observed_transition"] = "FAIL_TO_PASS"
            result["admission_status"] = "mutation_execution_admitted_pending_gold_rows_and_anticheat"
            append_jsonl(ADMITTED, result)
            admitted.append(result)
        else:
            append_jsonl(REJECTED, result)
            rejected.append(result)
        append_jsonl(RESULTS, result)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "mutation_execution_admitted_roots" if admitted else "no_mutation_roots_admitted",
        "items_attempted": len(selected),
        "prior_result_rows": len(prior_results),
        "new_admitted_roots": len(admitted),
        "new_rejected_roots": len(rejected),
        "total_result_rows": len(load_jsonl(RESULTS)),
        "total_admitted_roots": len(load_jsonl(ADMITTED)),
        "total_rejected_roots": len(load_jsonl(REJECTED)),
        "admitted_roots": len(admitted),
        "rejected_roots": len(rejected),
        "admitted_root_ids": [row.get("root_id") for row in admitted],
        "rejection_blockers": {blocker: sum(1 for row in rejected if blocker in row.get("blockers", [])) for blocker in sorted({b for row in rejected for b in row.get("blockers", [])})},
        "claim_boundary": [
            "This stage executes controlled bug-injection smoke materialization only.",
            "Admitted roots are not train/eval rows until six-perspective gold answers and anti-cheat review are generated.",
            "The mutation is artificial and must be labelled controlled bug injection, not organic issue replay.",
        ],
        "next_required_actions": [
            "For admitted roots, generate six-perspective maintainer rows using baseline/mutant/restored logs.",
            "Run prompt-target leak and option-shuffle audits before training.",
            "Keep these roots split-clean from Web heldout and from any strict promotion slice unless explicitly assigned.",
        ],
        "source_artifacts": {"work_items": rel(WORK_ITEMS)},
        "outputs": {"summary": rel(SUMMARY), "results": rel(RESULTS), "admitted": rel(ADMITTED), "rejected": rel(REJECTED)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({
        "decision": summary["decision"],
        "items_attempted": summary["items_attempted"],
        "new_admitted_roots": summary["new_admitted_roots"],
        "new_rejected_roots": summary["new_rejected_roots"],
        "total_admitted_roots": summary["total_admitted_roots"],
        "total_rejected_roots": summary["total_rejected_roots"],
        "admitted_root_ids": summary["admitted_root_ids"],
        "rejection_blockers": summary["rejection_blockers"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
