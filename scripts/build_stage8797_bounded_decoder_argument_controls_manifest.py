#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from bounded_decoder_argument_controls_builder import build_bounded_decoder_argument_controls, build_card, read_jsonl, write_jsonl

STAGE = 8797
NAME = "stage8797_bounded_decoder_argument_controls_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage8645_bounded_decoder_arguments_neutral_manifest/bounded_decoder_arguments_neutral_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDED_DECODER_ARGUMENT_CONTROLS_MANIFEST_STAGE8797.md"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_bounded_decoder_argument_controls_builder.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    rows = build_bounded_decoder_argument_controls(read_jsonl(SOURCE))
    manifest = OUT_DIR / "bounded_decoder_argument_controls_manifest.jsonl"
    write_jsonl(manifest, rows)
    control_card = build_card(rows)
    control_card_path = OUT_DIR / "bounded_decoder_argument_controls_card.json"
    control_card_path.write_text(json.dumps(control_card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures = []
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if control_card["rows"] != 504:
        failures.append("row_count_changed_from_stage8645")
    if control_card["authority_rows"] != 0:
        failures.append("authority_rows_nonzero")
    if control_card["training_loss_rows"] != 0:
        failures.append("training_loss_rows_nonzero")
    if control_card["gate_status"]["complete_gate_status_rows"] != control_card["rows"]:
        failures.append("incomplete_gate_status")
    if control_card["raw_source_rows"] != 0 or control_card["raw_decoder_text_rows"] != 0:
        failures.append("raw_source_or_decoder_text_visible")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "rows": control_card["rows"],
            "authority_rows": control_card["authority_rows"],
            "training_loss_rows": control_card["training_loss_rows"],
            "complete_gate_status_rows": control_card["gate_status"]["complete_gate_status_rows"],
            "raw_source_rows": control_card["raw_source_rows"],
            "raw_decoder_text_rows": control_card["raw_decoder_text_rows"],
            "labels": control_card["labels"],
            "splits": control_card["splits"],
            "failures": failures,
        },
        "artifacts": {
            "manifest": str(manifest.relative_to(ROOT)),
            "control_card": str(control_card_path.relative_to(ROOT)),
            "source_manifest": str(SOURCE.relative_to(ROOT)),
            "builder": "scripts/bounded_decoder_argument_controls_builder.py",
            "tests": "tests/test_bounded_decoder_argument_controls_builder.py",
        },
        "decision": (
            "Built bounded decoder argument candidate-control manifest with recovered gate_status and all training/decoder/runtime losses closed."
            if not failures
            else "Bounded decoder argument candidate-control manifest failed."
        ),
        "next_best_step": "Run shortcut and gate audit over Stage8797 before graph attachment or any bounded decoder CE package work.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8797 Bounded Decoder Argument Controls Manifest",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Wrapped the recovered Stage8645 bounded-decoder argument rows with complete recovered `gate_status`, closed loss masks, closed authority, and explicit anti-cheat fields.",
        "",
        f"Rows: `{control_card['rows']}`",
        f"Complete gate-status rows: `{control_card['gate_status']['complete_gate_status_rows']}`",
        f"Training loss rows: `{control_card['training_loss_rows']}`",
        f"Authority rows: `{control_card['authority_rows']}`",
        "",
        "This is candidate-control packaging only. It does not authorize decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, or promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
