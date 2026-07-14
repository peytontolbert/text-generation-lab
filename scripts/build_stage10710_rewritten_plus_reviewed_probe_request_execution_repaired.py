#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10710
NAME = "stage10710_rewritten_plus_reviewed_probe_request_execution_repaired"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "rewritten_plus_reviewed_probe_request_execution_repaired.json"
COMMAND_JSON = OUT_DIR / "rewritten_plus_reviewed_probe_command_execution_repaired.json"
MANIFEST_JSONL = OUT_DIR / "rewritten_plus_reviewed_probe_manifest_execution_repaired.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PACKAGE_JSON = ROOT / "runs/local/artifacts/stage10709_rewritten_plus_reviewed_training_package_execution_repaired/rewritten_plus_reviewed_training_package_execution_repaired.json"
TRAIN_ROWS = ROOT / "runs/local/artifacts/stage10709_rewritten_plus_reviewed_training_package_execution_repaired/train_rows.jsonl"
EVAL_ROWS = ROOT / "runs/local/artifacts/stage10709_rewritten_plus_reviewed_training_package_execution_repaired/eval_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10709_rewritten_plus_reviewed_training_package_execution_repaired/strict_rows.jsonl"
CANARY_ROWS = ROOT / "runs/local/artifacts/stage10709_rewritten_plus_reviewed_training_package_execution_repaired/canary_rows.jsonl"
SOURCE_REQUEST = ROOT / "runs/local/artifacts/stage10707_rewritten_plus_reviewed_multilingual_probe_request_honest_strict/rewritten_plus_reviewed_multilingual_probe_request_honest_strict.json"

RUN_ID = "stage10710_rewritten_plus_reviewed_probe_execution_repaired"
OUTPUT_DIR = "runs/local/artifacts/stage10710_rewritten_plus_reviewed_probe_execution_repaired/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10710_rewritten_plus_reviewed_probe_execution_repaired/runtime_model"


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
    package = load_json(PACKAGE_JSON)
    source_request = load_json(SOURCE_REQUEST)
    train_rows = load_jsonl(TRAIN_ROWS)
    eval_rows = load_jsonl(EVAL_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)
    canary_rows = load_jsonl(CANARY_ROWS)

    manifest_rows = []
    for split_name, rows in (("train", train_rows), ("eval", eval_rows), ("strict_eval", strict_rows)):
        for row in rows:
            copied = json.loads(json.dumps(row))
            copied["split"] = split_name
            manifest_rows.append(copied)
    manifest_rows.sort(key=lambda row: (str(row.get("split") or ""), str(row.get("row_id") or "")))
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    command = list(source_request["command"])
    command[command.index("--manifest") + 1] = str(ROOT / MANIFEST_JSONL)
    command[command.index("--output-dir") + 1] = str(ROOT / OUTPUT_DIR)
    command[command.index("--runtime-model-save-dir") + 1] = str(ROOT / RUNTIME_MODEL_DIR)
    command[command.index("--run-id") + 1] = RUN_ID
    command[command.index("--max-train-rows") + 1] = str(len(train_rows))
    command[command.index("--max-eval-rows") + 1] = str(len(eval_rows))
    command[command.index("--max-strict-rows") + 1] = str(len(strict_rows))

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "rewritten_plus_reviewed_probe_request_execution_repaired_ready",
        "claim_scope": [
            "Rerun the honest multilingual probe with execution-contract-repaired rewritten support rows.",
            "Preserve the audited 24-row eval and strict frontier exactly and keep the v2.7 canary separate for post-run regression checks.",
            "This request fixes the packaging failure path from stage10707 without changing the benchmark claim.",
        ],
        "source_artifacts": {
            "execution_repaired_package": display(PACKAGE_JSON),
            "source_request_template": display(SOURCE_REQUEST),
            "canary_rows": display(CANARY_ROWS),
        },
        "rows": len(manifest_rows),
        "split_counts": {
            "train": len(train_rows),
            "eval": len(eval_rows),
            "strict_eval": len(strict_rows),
            "canary": len(canary_rows),
        },
        "execution_contract_gates": {
            "all_train_rows_have_decoder_text": all(str(row.get("decoder_text") or "") for row in train_rows),
            "all_train_rows_have_target_text": all(str(row.get("target_text") or "") for row in train_rows),
            "all_train_rows_have_loss_mask": all(bool(row.get("loss_mask")) for row in train_rows),
            "strict_frontier_unchanged_count": len(strict_rows) == 24,
        },
        "post_run_required_artifacts": [
            "bounded_decoder_probe/execution_result.json",
            "strict comparison against the audited honest 24-row frontier",
            "canary replay audit against the repaired v2.7 24-row suite",
            "language-slice accuracy and regression summary",
        ],
        "known_limits": [
            "The strict frontier is still only 24 rows, so this remains a compact multilingual movement test rather than a broad final benchmark.",
            "Rewritten support remains train/validation-only and is not being promoted directly into heldout evaluation here.",
        ],
        "next_best_step": "Launch the repaired request and check whether execution now proceeds past preflight into actual training and strict evaluation.",
        "run_id": RUN_ID,
        "output_dir": OUTPUT_DIR,
        "runtime_model_dir": RUNTIME_MODEL_DIR,
        "manifest": display(MANIFEST_JSONL),
        "command": command,
    }

    write_json(COMMAND_JSON, {"command": command, "cwd": str(ROOT)})
    write_json(REQUEST_JSON, request)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": request["decision"],
            "request_json": display(REQUEST_JSON),
        },
    )
    print(json.dumps({"stage": STAGE, "passed": True, "rows": len(manifest_rows), "train": len(train_rows), "eval": len(eval_rows), "strict": len(strict_rows)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
