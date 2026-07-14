#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10556
NAME = "stage10556_masked_projection_successor_with_v27_preservation_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "masked_projection_successor_with_v27_preservation_probe_request.json"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_REQUEST = ROOT / "runs/local/artifacts/stage10551_cuda_masked_projection_successor_probe_request/cuda_masked_projection_successor_probe_request.json"
SOURCE_PACKAGE = ROOT / "runs/local/artifacts/stage10555_masked_projection_successor_with_v27_preservation_package/masked_projection_successor_with_v27_preservation_package.json"
SOURCE_ROWS = ROOT / "runs/local/artifacts/stage10555_masked_projection_successor_with_v27_preservation_package/masked_projection_successor_with_v27_preservation_rows.jsonl"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10551_cuda_masked_projection_successor_probe/runtime_model/runtime_model_bundle.json"
PRESERVATION_REF = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"

RUN_ID = "stage10556_masked_projection_successor_with_v27_preservation_probe"
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage10556_masked_projection_successor_with_v27_preservation_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = ROOT / "runs/local/artifacts/stage10556_masked_projection_successor_with_v27_preservation_probe/runtime_model"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rewrite_command(command: list[str]) -> list[str]:
    updated = list(command)
    replacements = {
        "--manifest": str(SOURCE_ROWS),
        "--max-train-rows": "2280",
        "--max-eval-rows": "5",
        "--max-strict-rows": "54",
        "--max-steps": "128",
        "--learning-rate": "1e-5",
        "--decoder-ce-weight": "1.0",
        "--bounded-choice-aux-weight": "1.0",
        "--runtime-model-save-dir": str(RUNTIME_MODEL_DIR),
        "--initialize-from-runtime-model": str(INIT_RUNTIME),
        "--preservation-reference-runtime-model": str(PRESERVATION_REF),
        "--output-dir": str(OUTPUT_DIR),
        "--run-id": RUN_ID,
    }
    for flag, new_value in replacements.items():
        if flag in updated:
            idx = updated.index(flag)
            updated[idx + 1] = new_value
    return updated


def main() -> None:
    source_request = load_json(SOURCE_REQUEST)
    source_package = load_json(SOURCE_PACKAGE)
    command = rewrite_command(list(source_request.get("command") or []))
    rows = source_package["rows"]
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(source_package.get("passed")),
        "decision": "masked_projection_successor_with_v27_preservation_probe_ready",
        "claim_scope": [
            "Corrective successor probe that keeps the stage10543 long-context strict slice unchanged but restores bounded-choice preservation signal from non-strict reviewed v2.7 support rows.",
            "This is a promotion candidate only if it improves raw seq2seq behavior on the 54 strict successor rows without regressing the repaired 24-row v2.7 canary.",
            "Same-manifest Gemma comparison remains generation-only on the strict successor slice and must not be relabeled as bounded-choice evidence.",
        ],
        "source_request": str(SOURCE_REQUEST.relative_to(ROOT)),
        "source_package": str(SOURCE_PACKAGE.relative_to(ROOT)),
        "manifest": str(SOURCE_ROWS.relative_to(ROOT)),
        "run_id": RUN_ID,
        "output_dir": str(OUTPUT_DIR.relative_to(ROOT)),
        "runtime_model_dir": str(RUNTIME_MODEL_DIR.relative_to(ROOT)),
        "rows": rows["all"],
        "split_counts": {
            "train": rows["train"],
            "eval": rows["eval"],
            "strict_eval": rows["strict_eval"],
        },
        "language_counts_by_split": source_package.get("language_counts"),
        "strict_target_subtypes": source_package.get("target_subtypes", {}).get("strict_eval"),
        "support_mix": source_package.get("support_mix"),
        "command": command,
        "training_changes": {
            "initialize_from_runtime_model": {
                "from": "stage10531_long_target_cap_corrected_probe",
                "to": "stage10551_cuda_masked_projection_successor_probe",
            },
            "bounded_choice_aux_weight": {"from": "0.0", "to": "1.0"},
            "learning_rate": {"from": "2e-5", "to": "1e-5"},
            "max_steps": {"from": "256", "to": "128"},
            "support_rows_added": source_package["support_mix"]["reviewed_v27_support_rows"],
        },
        "required_honesty_gates": [
            "stage10554 contract_block_reason must remain attached to the strict successor slice so no bounded-choice claim is made there",
            "reviewed v2.7 support rows must remain train-only and non-overlapping with the 24-row repaired canary",
            "same-manifest Gemma comparison must use the exact 54 strict rows from stage10555",
            "promotion requires no regression on the repaired 24-row canary and no new prompt-target leak findings",
        ],
        "known_limits": [
            "The strict 54-row successor slice is still generation-only and cannot yet be scored through semantic candidate options.",
            "This probe tests whether mixed preservation support can repair the raw generator collapse; it does not itself solve the long-context strict contract gap.",
        ],
        "next_best_step": (
            "Launch this corrective probe, then rerun the same 54-row raw seq2seq comparison and the 24-row repaired-v2.7 canary. "
            "If the raw collapse persists, the next move is dataset-side target/interface redesign rather than another decoder-only sweep."
        ),
    }
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY_JSON, request)
    print(json.dumps({"stage": STAGE, "passed": request["passed"], "run_id": RUN_ID}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
