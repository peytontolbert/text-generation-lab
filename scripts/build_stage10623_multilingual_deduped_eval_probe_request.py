#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10623
NAME = "stage10623_multilingual_deduped_eval_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "multilingual_deduped_eval_probe_request.json"
COMMAND_JSON = OUT_DIR / "multilingual_deduped_eval_probe_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_REQUEST = ROOT / "runs/local/artifacts/stage10620_reviewed_plus_bootstrap_multilingual_probe_request_capped/reviewed_plus_bootstrap_multilingual_probe_request_capped.json"
DEDUPED_MANIFEST = ROOT / "runs/local/artifacts/stage10622_multilingual_deduped_eval_package/multilingual_deduped_eval_manifest.jsonl"

TMPDIR = Path("/data/tmp")
RUN_ID = "stage10623_multilingual_deduped_eval_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10623_multilingual_deduped_eval_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10623_multilingual_deduped_eval_probe/runtime_model"


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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    source_request = load_json(SOURCE_REQUEST)
    rows = load_jsonl(DEDUPED_MANIFEST)
    split_counts = Counter(str(row.get("split") or "unknown") for row in rows)

    command = list(source_request["command"])
    manifest_idx = command.index("--manifest") + 1
    command[manifest_idx] = str(DEDUPED_MANIFEST)
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
        "decision": "multilingual_deduped_eval_probe_ready",
        "claim_scope": [
            "Rerun the stage10620 multilingual target_100m probe against the deduped eval package.",
            "Hold training rows fixed while repairing eval/strict row-level honesty.",
            "Produce a clean successor score on 24 strict rows without duplicate logical decisions.",
        ],
        "source_request": display(SOURCE_REQUEST),
        "manifest": display(DEDUPED_MANIFEST),
        "run_id": RUN_ID,
        "output_dir": OUTPUT_DIR,
        "runtime_model_dir": RUNTIME_MODEL_DIR,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "required_honesty_gates": source_request.get("required_honesty_gates"),
        "post_run_required_artifacts": source_request.get("post_run_required_artifacts"),
        "known_limits": source_request.get("known_limits"),
        "command": command,
    }
    write_json(COMMAND_JSON, {"command": command, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)})
    write_json(REQUEST_JSON, request)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "request": display(REQUEST_JSON),
            "rows": len(rows),
            "strict_eval_rows": split_counts.get("strict_eval", 0),
        },
    )
    print(json.dumps({"stage": STAGE, "passed": True, "rows": len(rows), "strict_eval_rows": split_counts.get("strict_eval", 0)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
