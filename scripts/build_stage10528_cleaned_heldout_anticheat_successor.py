#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10528
NAME = "stage10528_cleaned_heldout_anticheat_successor"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/split_aware_multitarget_bootstrap_manifest_with_heldout.json"
SOURCE_ROWS = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/multitarget_bootstrap_with_heldout_rows.jsonl"
SOURCE_TRAIN = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/train_rows.jsonl"
SOURCE_VALIDATION = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/validation_rows.jsonl"
SOURCE_STRICT = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/strict_eval_rows.jsonl"
SOURCE_REFERENCE = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/reference_rows.jsonl"
SOURCE_DIAGNOSTIC = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/diagnostic_rows.jsonl"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage10527_bootstrap_heldout_expert_eval_appropriateness_audit/bootstrap_heldout_expert_eval_appropriateness_audit.json"

MANIFEST_JSON = OUT_DIR / "cleaned_heldout_anticheat_successor.json"
ROWS_JSONL = OUT_DIR / "cleaned_multitarget_bootstrap_with_heldout_rows.jsonl"
TRAIN_JSONL = OUT_DIR / "train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "strict_eval_rows.jsonl"
REFERENCE_JSONL = OUT_DIR / "reference_rows.jsonl"
DIAGNOSTIC_JSONL = OUT_DIR / "diagnostic_rows.jsonl"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"


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


def contains_target_verbatim(row: dict[str, Any]) -> bool:
    input_text = str(row.get("input_text") or "")
    target_text = str(row.get("target_text") or "").strip()
    if not input_text or not target_text or len(target_text) < 8:
        return False
    return target_text in input_text


def clean_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    anti_cheat = dict(updated.get("anti_cheat") or {})
    anti_cheat["same_root_train_eval_forbidden"] = True
    anti_cheat["prompt_target_leak"] = contains_target_verbatim(updated)
    anti_cheat["prompt_target_leak_source"] = "stage10528_visible_surface_recomputed"
    anti_cheat["metadata_cleaned_stage"] = STAGE
    updated["anti_cheat"] = anti_cheat
    return updated


def main() -> None:
    source_manifest = load_json(SOURCE_MANIFEST)
    source_audit = load_json(SOURCE_AUDIT) if SOURCE_AUDIT.exists() else {}
    all_rows = [clean_row(row) for row in load_jsonl(SOURCE_ROWS)]
    train_rows = [clean_row(row) for row in load_jsonl(SOURCE_TRAIN)]
    validation_rows = [clean_row(row) for row in load_jsonl(SOURCE_VALIDATION)]
    strict_rows = [clean_row(row) for row in load_jsonl(SOURCE_STRICT)]
    reference_rows = [clean_row(row) for row in load_jsonl(SOURCE_REFERENCE)]
    diagnostic_rows = [clean_row(row) for row in load_jsonl(SOURCE_DIAGNOSTIC)]

    strict_prompt_target_leak_true = sum(1 for row in strict_rows if ((row.get("anti_cheat") or {}).get("prompt_target_leak")) is True)
    strict_prompt_target_leak_false = sum(1 for row in strict_rows if ((row.get("anti_cheat") or {}).get("prompt_target_leak")) is False)

    manifest = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": bool(source_manifest.get("passed")),
        "claim_boundary": [
            "This successor preserves the stage10521 bootstrap-heldout data and split structure.",
            "It only refreshes anti_cheat metadata so prompt_target_leak reflects the visible surface rather than stale inherited flags.",
            "Comparison and review should prefer this successor over stage10521 when interpreting anti-cheat metadata.",
        ],
        "inputs": {
            "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
            "source_audit": str(SOURCE_AUDIT.relative_to(ROOT)),
        },
        "metrics": {
            "all_rows": len(all_rows),
            "train_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "strict_eval_rows": len(strict_rows),
            "reference_rows": len(reference_rows),
            "diagnostic_rows": len(diagnostic_rows),
            "strict_rows_by_language": dict(sorted(Counter(row["language_family"] for row in strict_rows).items())),
            "strict_rows_by_target_subtype": dict(sorted(Counter(row["target_subtype"] for row in strict_rows).items())),
            "strict_prompt_target_leak_true": strict_prompt_target_leak_true,
            "strict_prompt_target_leak_false": strict_prompt_target_leak_false,
        },
        "anti_cheat_refresh": {
            "refreshed_field": "anti_cheat.prompt_target_leak",
            "strict_rows_before_true": (((source_audit.get("anti_cheat_audit") or {}).get("metadata_prompt_target_leak_true_count")) or 0),
            "strict_rows_after_true": strict_prompt_target_leak_true,
            "strict_rows_after_false": strict_prompt_target_leak_false,
            "stage10527_actual_prompt_target_leak_true_count": (((source_audit.get("anti_cheat_audit") or {}).get("actual_prompt_target_leak_true_count")) or 0),
        },
        "root_split_audit": source_manifest.get("root_split_audit") or {},
        "next_best_step": (
            "Use this cleaned successor for post-run comparison and future review packets so anti-cheat metadata matches the actual visible surface. "
            "Then expand heldout verifier_outcome and patch-sketch rows rather than over-reading the current decisive_evidence/retrieve_answer_abstain slice."
        ),
        "outputs": {
            "all_rows": str(ROWS_JSONL.relative_to(ROOT)),
            "train_rows": str(TRAIN_JSONL.relative_to(ROOT)),
            "validation_rows": str(VALIDATION_JSONL.relative_to(ROOT)),
            "strict_rows": str(STRICT_JSONL.relative_to(ROOT)),
            "reference_rows": str(REFERENCE_JSONL.relative_to(ROOT)),
            "diagnostic_rows": str(DIAGNOSTIC_JSONL.relative_to(ROOT)),
        },
    }

    write_jsonl(ROWS_JSONL, all_rows)
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(REFERENCE_JSONL, reference_rows)
    write_jsonl(DIAGNOSTIC_JSONL, diagnostic_rows)
    write_json(MANIFEST_JSON, manifest)
    write_json(SUMMARY_JSON, manifest)
    print(json.dumps({"stage": STAGE, "passed": manifest["passed"], "strict_prompt_target_leak_true": strict_prompt_target_leak_true}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
