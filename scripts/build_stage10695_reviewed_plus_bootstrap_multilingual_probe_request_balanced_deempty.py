#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10695
NAME = "stage10695_reviewed_plus_bootstrap_multilingual_probe_request_balanced_deempty"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "reviewed_plus_bootstrap_multilingual_probe_request_balanced_deempty.json"
COMMAND_JSON = OUT_DIR / "reviewed_plus_bootstrap_multilingual_probe_command_balanced_deempty.json"
MANIFEST_JSONL = OUT_DIR / "reviewed_plus_bootstrap_multilingual_probe_manifest_balanced_deempty.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_REQUEST = ROOT / "runs/local/artifacts/stage10694_reviewed_plus_bootstrap_multilingual_probe_request_balanced/reviewed_plus_bootstrap_multilingual_probe_request_balanced.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage10694_reviewed_plus_bootstrap_multilingual_probe_request_balanced/reviewed_plus_bootstrap_multilingual_probe_manifest_balanced.jsonl"

RUN_ID = "stage10695_reviewed_plus_bootstrap_multilingual_probe_balanced_deempty"
OUTPUT_DIR = "runs/local/artifacts/stage10695_reviewed_plus_bootstrap_multilingual_probe_balanced_deempty/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10695_reviewed_plus_bootstrap_multilingual_probe_balanced_deempty/runtime_model"


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
    rows = load_jsonl(SOURCE_MANIFEST)

    kept_rows: list[dict[str, Any]] = []
    removed_rows: list[dict[str, Any]] = []
    for row in rows:
        decoder_text = str(row.get("decoder_text") or "").strip()
        target_text = str(row.get("target_text") or "").strip()
        if decoder_text or target_text:
            kept_rows.append(row)
        else:
            removed_rows.append(row)

    kept_rows.sort(key=lambda row: (str(row.get("split") or ""), str(row.get("row_id") or "")))
    write_jsonl(MANIFEST_JSONL, kept_rows)

    split_counts = Counter(str(row.get("split") or "unknown") for row in kept_rows)
    removed_split_counts = Counter(str(row.get("split") or "unknown") for row in removed_rows)
    removed_language_counts = Counter(str(row.get("language_family") or "unknown") for row in removed_rows)

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
    command[train_idx] = str(split_counts.get("train", 0))
    command[eval_idx] = str(split_counts.get("eval", 0))
    command[strict_idx] = str(split_counts.get("strict_eval", 0))

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "reviewed_plus_bootstrap_multilingual_probe_balanced_deempty_ready",
        "claim_scope": [
            "Repair the balanced multilingual probe request by removing rows that still have genuinely empty decoder targets.",
            "Do not invent or impute targets for diagnostic support rows whose source manifest lacks a gold decoder target.",
            "Preserve the balanced capped train split and the strict multilingual eval split unchanged where possible.",
        ],
        "source_request": display(SOURCE_REQUEST),
        "manifest": display(MANIFEST_JSONL),
        "run_id": RUN_ID,
        "output_dir": OUTPUT_DIR,
        "runtime_model_dir": RUNTIME_MODEL_DIR,
        "rows": len(kept_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "removed_rows": {
            "count": len(removed_rows),
            "split_counts": dict(sorted(removed_split_counts.items())),
            "language_counts": dict(sorted(removed_language_counts.items())),
            "sample_row_ids": [str(row.get("row_id") or "") for row in removed_rows[:25]],
        },
        "why_removed": [
            "Rows had empty decoder_text and empty target_text in the source manifest.",
            "These rows are diagnostic_support_only/visible_evidence_key carryovers and are not safe to impute.",
        ],
        "required_honesty_gates": source_request.get("required_honesty_gates"),
        "post_run_required_artifacts": source_request.get("post_run_required_artifacts"),
        "known_limits": source_request.get("known_limits"),
        "next_best_step": "Launch this deempty balanced request and confirm that model execution starts before evaluating metrics.",
        "command": command,
    }

    write_json(COMMAND_JSON, {"command": command, "cwd": str(ROOT)})
    write_json(REQUEST_JSON, request)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "request": display(REQUEST_JSON),
            "manifest": display(MANIFEST_JSONL),
        },
    )
    print(json.dumps({"stage": STAGE, "passed": True, "rows": len(kept_rows), "removed_rows": len(removed_rows)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
