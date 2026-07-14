#!/usr/bin/env python3
"""Build a corrected probe request that frontloads Python verifier support."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
OUT_DIR = ROOT / "runs/local/artifacts/stage10721_frontloaded_python_verifier_probe_request"

BASE_PACKAGE = ROOT / "runs/local/artifacts/stage10718_execution_repaired_plus_python_verifier_support_package"
BASE_REQUEST = ROOT / "runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe_request/execution_repaired_plus_python_verifier_probe_request.json"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe/runtime_model/runtime_model_bundle.json"

SUPPORT_MARKERS = (
    "stage10236::localsess_code_assist",
    "stage10499::localsess_code_assist_hf_local_multitest_repaired",
    "multitarget_abstain_support",
)


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    train_rows = load_jsonl(BASE_PACKAGE / "train_rows.jsonl")
    eval_rows = load_jsonl(BASE_PACKAGE / "eval_rows.jsonl")
    strict_rows = load_jsonl(BASE_PACKAGE / "strict_rows.jsonl")
    base_request = load_json(BASE_REQUEST)

    support_rows = [row for row in train_rows if any(marker in str(row.get("row_id") or "") for marker in SUPPORT_MARKERS)]
    non_support_rows = [row for row in train_rows if row not in support_rows]
    frontloaded_train = support_rows + non_support_rows

    manifest_rows = frontloaded_train + eval_rows + strict_rows
    manifest_path = OUT_DIR / "frontloaded_python_verifier_probe_manifest.jsonl"
    write_jsonl(manifest_path, manifest_rows)

    command = list(base_request["command"])
    replacements = {
        "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe_request/execution_repaired_plus_python_verifier_probe_manifest.jsonl":
            str(manifest_path),
        "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe/runtime_model/runtime_model_bundle.json":
            str(INIT_RUNTIME),
        "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe/bounded_decoder_probe":
            "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage10721_frontloaded_python_verifier_probe/bounded_decoder_probe",
        "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe/runtime_model":
            "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage10721_frontloaded_python_verifier_probe/runtime_model",
        "stage10719_execution_repaired_plus_python_verifier_probe":
            "stage10721_frontloaded_python_verifier_probe",
    }
    command = [replacements.get(token, token) for token in command]
    if "--max-steps" in command:
        command[command.index("--max-steps") + 1] = "160"
    if "--max-train-rows" in command:
        command[command.index("--max-train-rows") + 1] = str(len(frontloaded_train))

    request = {
        "stage": 10721,
        "stage_name": "stage10721_frontloaded_python_verifier_probe_request",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "claim_scope": [
            "Correct the stage10719 sampling gap by frontloading Python verifier support and increasing steps to cover the full train split.",
            "Keep eval and strict slices unchanged so movement remains attributable to train-side curriculum only.",
            "Test whether the restored Python verifier support can move the strict residual once it is actually sampled."
        ],
        "headline_findings": [
            "Stage10719 added six Python verifier support rows but sampled none of them because they sat at train positions 281-286 under a 256-sample run budget.",
            "This request moves those support rows to the front of train and raises max_steps from 128 to 160.",
            "The next run is the first honest test of the Python support after fixing the sampling path bug."
        ],
        "command": command,
        "manifest": str(manifest_path.relative_to(ROOT)),
        "rows": len(manifest_rows),
        "split_counts": {
            "train": len(frontloaded_train),
            "eval": len(eval_rows),
            "strict_eval": len(strict_rows),
        },
        "frontload_audit": {
            "support_rows_frontloaded": [row["row_id"] for row in support_rows],
            "frontloaded_prefix_length": len(support_rows),
            "max_steps": 160,
            "batch_size": 2,
            "sample_budget": 320,
            "train_rows": len(frontloaded_train),
        },
        "known_limits": [
            "The strict frontier is still only 24 rows.",
            "The Python verifier lane still only covers two root families.",
            "This fixes a sampling bug, not the broader root-supply weakness."
        ],
        "next_best_step": "Launch this corrected request and compare against stage10719. If Python still does not move after actual sampling, the next bottleneck is the decision representation itself rather than support reachability.",
        "outputs": {
            "request_json": "runs/local/artifacts/stage10721_frontloaded_python_verifier_probe_request/frontloaded_python_verifier_probe_request.json",
            "manifest_jsonl": str(manifest_path.relative_to(ROOT)),
        },
    }

    write_json(OUT_DIR / "frontloaded_python_verifier_probe_request.json", request)


if __name__ == "__main__":
    main()
