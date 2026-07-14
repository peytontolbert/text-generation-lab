#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10707
NAME = "stage10707_rewritten_plus_reviewed_multilingual_probe_request_honest_strict"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "rewritten_plus_reviewed_multilingual_probe_request_honest_strict.json"
COMMAND_JSON = OUT_DIR / "rewritten_plus_reviewed_multilingual_probe_command_honest_strict.json"
MANIFEST_JSONL = OUT_DIR / "rewritten_plus_reviewed_multilingual_probe_manifest_honest_strict.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PACKAGE_JSON = ROOT / "runs/local/artifacts/stage10706_rewritten_plus_reviewed_multilingual_training_package_honest_strict/rewritten_plus_reviewed_multilingual_training_package_honest_strict.json"
TRAIN_ROWS = ROOT / "runs/local/artifacts/stage10706_rewritten_plus_reviewed_multilingual_training_package_honest_strict/train_rows.jsonl"
EVAL_ROWS = ROOT / "runs/local/artifacts/stage10706_rewritten_plus_reviewed_multilingual_training_package_honest_strict/eval_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10706_rewritten_plus_reviewed_multilingual_training_package_honest_strict/strict_rows.jsonl"
CANARY_ROWS = ROOT / "runs/local/artifacts/stage10706_rewritten_plus_reviewed_multilingual_training_package_honest_strict/canary_rows.jsonl"
SOURCE_REQUEST = ROOT / "runs/local/artifacts/stage10697_reviewed_plus_bootstrap_multilingual_probe_request_balanced_deduped/reviewed_plus_bootstrap_multilingual_probe_request_balanced_deduped.json"

RUN_ID = "stage10707_rewritten_plus_reviewed_multilingual_probe_honest_strict"
OUTPUT_DIR = "runs/local/artifacts/stage10707_rewritten_plus_reviewed_multilingual_probe_honest_strict/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10707_rewritten_plus_reviewed_multilingual_probe_honest_strict/runtime_model"


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
    for row in train_rows:
        copied = json.loads(json.dumps(row))
        copied["split"] = "train"
        manifest_rows.append(copied)
    for row in eval_rows:
        copied = json.loads(json.dumps(row))
        copied["split"] = "eval"
        manifest_rows.append(copied)
    for row in strict_rows:
        copied = json.loads(json.dumps(row))
        copied["split"] = "strict_eval"
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
        "decision": "rewritten_plus_reviewed_multilingual_probe_request_honest_strict_ready",
        "claim_scope": [
            "Build the next target-100M probe request from the corrected rewritten-plus-reviewed multilingual package.",
            "Use the audited honest 24-row eval/strict frontier while allowing the expanded rewritten support only in train.",
            "Keep the repaired v2.7 canary separate for post-run regression checks rather than mixing it into main train counts.",
        ],
        "source_artifacts": {
            "corrected_package": display(PACKAGE_JSON),
            "source_probe_request_template": display(SOURCE_REQUEST),
            "canary_rows": display(CANARY_ROWS),
        },
        "rows": len(manifest_rows),
        "split_counts": {
            "train": len(train_rows),
            "eval": len(eval_rows),
            "strict_eval": len(strict_rows),
            "canary": len(canary_rows),
        },
        "required_honesty_gates": [
            "strict and eval rows must remain the audited honest 24-row frontier",
            "rewritten support rows must stay out of strict and eval",
            "post-run report must separate main strict accuracy from canary replay accuracy",
            "quarantined rewritten residue must stay excluded from the executable manifest",
        ],
        "post_run_required_artifacts": [
            "bounded_decoder_probe/execution_result.json",
            "strict comparison against the audited 24-row honest frontier",
            "canary replay audit against the repaired v2.7 24-row suite",
            "language-slice accuracy and regression summary",
        ],
        "known_limits": [
            "The honest frontier remains tiny at 24 strict rows, so this probe is still a compact multilingual movement test rather than a broad final benchmark.",
            "Rewritten support has not yet been promoted into heldout evaluation; it only strengthens training support in this request.",
        ],
        "next_best_step": "Launch this honest-strict request and test whether rewritten multilingual support moves the 22/24 frontier without regressions.",
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
