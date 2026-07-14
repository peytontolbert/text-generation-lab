#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10619
NAME = "stage10619_reviewed_plus_bootstrap_multilingual_probe_request_deempty"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "reviewed_plus_bootstrap_multilingual_probe_request_deempty.json"
COMMAND_JSON = OUT_DIR / "reviewed_plus_bootstrap_multilingual_probe_command_deempty.json"
MANIFEST_JSONL = OUT_DIR / "reviewed_plus_bootstrap_multilingual_probe_manifest_deempty.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_REQUEST = ROOT / "runs/local/artifacts/stage10618_reviewed_plus_bootstrap_multilingual_probe_request/reviewed_plus_bootstrap_multilingual_probe_request.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage10618_reviewed_plus_bootstrap_multilingual_probe_request/reviewed_plus_bootstrap_multilingual_probe_manifest.jsonl"
BROKEN_AUDIT = ROOT / "runs/local/artifacts/stage10618_reviewed_plus_bootstrap_multilingual_probe/bounded_decoder_probe/probe_contract_audit.json"

TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
TMPDIR = Path("/data/tmp")
RUN_ID = "stage10619_reviewed_plus_bootstrap_multilingual_probe_deempty"
OUTPUT_DIR = "runs/local/artifacts/stage10619_reviewed_plus_bootstrap_multilingual_probe_deempty/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10619_reviewed_plus_bootstrap_multilingual_probe_deempty/runtime_model"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    source_request = load_json(SOURCE_REQUEST)
    broken_audit = load_json(BROKEN_AUDIT)
    rows = load_jsonl(SOURCE_MANIFEST)

    cleaned_rows = [row for row in rows if str(row.get("target_text", "")).strip()]
    removed_rows = [row for row in rows if not str(row.get("target_text", "")).strip()]
    write_jsonl(MANIFEST_JSONL, cleaned_rows)

    command = list(source_request["command"])
    manifest_idx = command.index("--manifest") + 1
    command[manifest_idx] = str(ROOT / MANIFEST_JSONL)
    output_idx = command.index("--output-dir") + 1
    command[output_idx] = str(ROOT / OUTPUT_DIR)
    runtime_idx = command.index("--runtime-model-save-dir") + 1
    command[runtime_idx] = str(ROOT / RUNTIME_MODEL_DIR)
    run_idx = command.index("--run-id") + 1
    command[run_idx] = RUN_ID
    train_idx = command.index("--max-train-rows") + 1
    eval_idx = command.index("--max-eval-rows") + 1
    strict_idx = command.index("--max-strict-rows") + 1

    split_counts = Counter(str(row.get("split") or "unknown") for row in cleaned_rows)
    command[train_idx] = str(split_counts.get("train", 0))
    command[eval_idx] = str(split_counts.get("eval", 0))
    command[strict_idx] = str(split_counts.get("strict_eval", 0))

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "reviewed_plus_bootstrap_multilingual_probe_deempty_ready",
        "claim_scope": [
            "Repair the stage10618 probe request by removing only rows with empty decoder targets.",
            "Preserve the capped admitted multilingual package otherwise unchanged.",
            "This is a contract-fix successor, not a changed training strategy.",
        ],
        "source_request": display(SOURCE_REQUEST),
        "source_broken_contract_audit": display(BROKEN_AUDIT),
        "manifest": display(MANIFEST_JSONL),
        "run_id": RUN_ID,
        "output_dir": OUTPUT_DIR,
        "runtime_model_dir": RUNTIME_MODEL_DIR,
        "rows": len(cleaned_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "removed_empty_target_rows": {
            "count": len(removed_rows),
            "language_counts": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in removed_rows).items())),
            "source_kind_counts": dict(sorted(Counter(str(row.get("package_source_kind") or "unknown") for row in removed_rows).items())),
            "sample_row_ids": [str(row.get("row_id") or "") for row in removed_rows[:25]],
        },
        "why_removed": (broken_audit.get("errors") or []),
        "required_honesty_gates": source_request.get("required_honesty_gates"),
        "post_run_required_artifacts": source_request.get("post_run_required_artifacts"),
        "known_limits": source_request.get("known_limits"),
        "next_best_step": "Launch this cleaned successor request and verify that the contract passes before interpreting any training result.",
        "command": command,
    }

    write_json(COMMAND_JSON, {"command": command, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)})
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY, {"stage": STAGE, "passed": True, "request": display(REQUEST_JSON), "manifest": display(MANIFEST_JSONL)})
    print(json.dumps({"stage": STAGE, "passed": True, "rows": len(cleaned_rows), "removed": len(removed_rows)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
