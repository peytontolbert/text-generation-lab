#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10531
NAME = "stage10531_long_target_cap_corrected_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "long_target_cap_corrected_probe_request.json"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_REQUEST = ROOT / "runs/local/artifacts/stage10530_leak_clean_root_based_multitarget_probe_request/leak_clean_root_based_multitarget_probe_request.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage10530_leak_clean_root_based_multitarget_probe_request/leak_clean_root_based_multitarget_probe_manifest.jsonl"

RUN_ID = "stage10531_long_target_cap_corrected_probe"
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage10531_long_target_cap_corrected_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = ROOT / "runs/local/artifacts/stage10531_long_target_cap_corrected_probe/runtime_model"


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
        "--max-decoder-tokens": "1024",
        "--max-generation-tokens": "1024",
        "--batch-size": "1",
        "--output-dir": str(OUTPUT_DIR),
        "--runtime-model-save-dir": str(RUNTIME_MODEL_DIR),
        "--run-id": RUN_ID,
    }
    for flag, new_value in replacements.items():
        if flag in updated:
            idx = updated.index(flag)
            updated[idx + 1] = new_value
    return updated


def main() -> None:
    source = load_json(SOURCE_REQUEST)
    command = rewrite_command(list(source.get("command") or []))
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(source.get("passed")),
        "decision": "long_target_cap_corrected_probe_ready",
        "claim_scope": [
            "Length-cap-corrected successor to the leak-clean stage10530 request.",
            "Raises decoder and generation token caps so strict decisive_evidence targets are actually reachable by exact generation.",
            "Keeps the same leak-clean manifest and heldout slice.",
        ],
        "source_request": str(SOURCE_REQUEST.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "run_id": RUN_ID,
        "output_dir": str(OUTPUT_DIR.relative_to(ROOT)),
        "runtime_model_dir": str(RUNTIME_MODEL_DIR.relative_to(ROOT)),
        "rows": source.get("rows"),
        "split_counts": source.get("split_counts"),
        "language_counts_by_split": source.get("language_counts_by_split"),
        "strict_target_subtypes": source.get("strict_target_subtypes"),
        "command": command,
        "runtime_changes": {
            "max_decoder_tokens": {"from": "256", "to": "1024"},
            "max_generation_tokens": {"from": "128", "to": "1024"},
            "batch_size": {"from": "2", "to": "1"},
        },
        "required_honesty_gates": [
            *(source.get("required_honesty_gates") or []),
            "strict decisive_evidence targets must be reachable within the decoder cap",
        ],
        "known_limits": [
            *(source.get("known_limits") or []),
            "This corrects target-length reachability but does not by itself deepen heldout verifier_outcome or patch_sketch coverage.",
        ],
        "next_best_step": (
            "Launch this corrected successor instead of stage10530, then compare the resulting runtime against Gemma on the same 36 strict heldout rows "
            "and check the 24-row repaired-v2.7 canary for regression."
        ),
    }
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY_JSON, request)
    print(json.dumps({"stage": STAGE, "passed": request["passed"], "run_id": RUN_ID}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
