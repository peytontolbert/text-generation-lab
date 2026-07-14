#!/usr/bin/env python3
"""Build the next honest probe request with merged Python verifier support."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
STAGE = 10719
NAME = "stage10719_execution_repaired_plus_python_verifier_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

PACKAGE_DIR = ROOT / "runs/local/artifacts/stage10718_execution_repaired_plus_python_verifier_support_package"
BASE_REQUEST = ROOT / "runs/local/artifacts/stage10710_rewritten_plus_reviewed_probe_request_execution_repaired/rewritten_plus_reviewed_probe_request_execution_repaired.json"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10710_rewritten_plus_reviewed_probe_execution_repaired/runtime_model/runtime_model_bundle.json"


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

    base_request = load_json(BASE_REQUEST)
    train_rows = load_jsonl(PACKAGE_DIR / "train_rows.jsonl")
    eval_rows = load_jsonl(PACKAGE_DIR / "eval_rows.jsonl")
    strict_rows = load_jsonl(PACKAGE_DIR / "strict_rows.jsonl")

    manifest_rows = train_rows + eval_rows + strict_rows
    manifest_path = OUT_DIR / "execution_repaired_plus_python_verifier_probe_manifest.jsonl"
    write_jsonl(manifest_path, manifest_rows)

    command = list(base_request["command"])
    replacements = {
        "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage10710_rewritten_plus_reviewed_probe_request_execution_repaired/rewritten_plus_reviewed_probe_manifest_execution_repaired.jsonl":
            str(manifest_path),
        "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage10689_reviewed_v27_plus_two_fresh_rust_probe/runtime_model/runtime_model_bundle.json":
            str(INIT_RUNTIME),
        "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage10710_rewritten_plus_reviewed_probe_execution_repaired/bounded_decoder_probe":
            "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe/bounded_decoder_probe",
        "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage10710_rewritten_plus_reviewed_probe_execution_repaired/runtime_model":
            "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe/runtime_model",
        "stage10710_rewritten_plus_reviewed_probe_execution_repaired":
            "stage10719_execution_repaired_plus_python_verifier_probe",
    }
    command = [replacements.get(token, token) for token in command]
    if "--max-train-rows" in command:
        idx = command.index("--max-train-rows") + 1
        command[idx] = str(len(train_rows))

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "claim_scope": [
            "Launch the next honest multilingual probe after adding current Python verifier support to the execution-repaired train split.",
            "Keep the audited 24-row eval and strict slices unchanged so benchmark movement stays train-side only.",
            "Measure whether restored Python verifier support moves the surviving Python strict miss without reopening the benchmark boundary."
        ],
        "command": command,
        "manifest": str(manifest_path.relative_to(ROOT)),
        "rows": len(manifest_rows),
        "split_counts": {
            "train": len(train_rows),
            "eval": len(eval_rows),
            "strict_eval": len(strict_rows),
        },
        "manifest_contract_note": "Base train rows remain ordered train records even where legacy split fields are null; eval and strict rows retain explicit split labels.",
        "runtime_model_dir": "runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe/runtime_model",
        "output_dir": "runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe/bounded_decoder_probe",
        "run_id": "stage10719_execution_repaired_plus_python_verifier_probe",
        "execution_contract_gates": {
            "all_train_rows_have_target_text": all(row.get("target_text") for row in train_rows),
            "all_train_rows_have_decoder_text": all(row.get("decoder_text") for row in train_rows),
            "all_train_rows_have_loss_mask": all(bool(row.get("loss_mask")) for row in train_rows),
            "strict_frontier_unchanged_count": len(strict_rows) == 24,
            "eval_frontier_unchanged_count": len(eval_rows) == 24,
        },
        "known_limits": [
            "This remains a compact multilingual movement test with a 24-row strict frontier.",
            "The new Python support improves the train-side lane only; it does not by itself broaden heldout coverage.",
            "The Python verifier lane is still under-scaled at two root families even after this merge."
        ],
        "headline_findings": [
            "The previous execution-repaired package had zero Python verifier train rows.",
            "This request adds six Python verifier support rows: four singleton rows and two abstention-honesty rows.",
            "The next run is the first honest test of whether restored Python verifier support can move the strict Python residual without changing eval."
        ],
        "post_run_required_artifacts": [
            "bounded_decoder_probe/execution_result.json",
            "strict comparison against the audited honest 24-row frontier",
            "canary replay audit against the repaired v2.7 24-row suite",
            "language-slice accuracy and regression summary",
            "Python verifier strict-row movement audit",
        ],
        "source_artifacts": {
            "merged_package": str((PACKAGE_DIR / "execution_repaired_plus_python_verifier_support_package.json").relative_to(ROOT)),
            "base_request": str(BASE_REQUEST.relative_to(ROOT)),
            "initial_runtime_model": str(INIT_RUNTIME.relative_to(ROOT)),
        },
        "next_best_step": "Launch this request and compare its strict output against stage10710 to see whether the Python verifier lane actually moves while the rest of the multilingual frontier remains stable.",
    }

    write_json(OUT_DIR / "execution_repaired_plus_python_verifier_probe_request.json", request)


if __name__ == "__main__":
    main()
