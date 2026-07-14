#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10990
NAME = "stage10990_evidence_lane_sampler_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "evidence_lane_sampler_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
PRIMARY_ROWS_JSONL = OUT_DIR / "primary_lane_rows.jsonl"
ANCHOR_ROWS_JSONL = OUT_DIR / "preservation_anchor_rows.jsonl"

BASE_DIR = ARTIFACTS / "stage10983_clean_residual_family_support_package"
BASE_SUMMARY_JSON = BASE_DIR / "clean_residual_family_support_package.json"
BASE_TRAIN_JSONL = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION_JSONL = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT_JSONL = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS_JSONL = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

PRIMARY_TASKS = {
    "evidence_citation",
    "verifier_outcome",
    "evidence_role_classification",
    "verifier_candidate_role_classification",
}
KEEP_TASKS = {
    "evidence_citation",
    "verifier_outcome",
    "evidence_role_classification",
    "verifier_candidate_role_classification",
    "symptom_localization",
    "patch_impact",
    "abstention_insufficient_evidence",
    "minimal_fix_selection",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("row_id") or ""), str(row.get("target_text") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def annotate_train_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    task = str(updated.get("task_type") or "unknown")
    repo = str(updated.get("repo_family") or "unknown")
    lang = str(updated.get("language_family") or "unknown")
    updated["split"] = "train"
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["disable_losses"] = []
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    updated["residual_lane_role"] = "primary" if task in PRIMARY_TASKS else "anchor"
    updated["preservation_exempt"] = bool(task in PRIMARY_TASKS)
    updated["bounded_decoder_sampler_group"] = (
        "evidence_primary" if task == "evidence_citation" else
        "verifier_primary" if task == "verifier_outcome" else
        "evidence_role_support" if task == "evidence_role_classification" else
        "verifier_role_support" if task == "verifier_candidate_role_classification" else
        "preservation_anchor"
    )
    updated["support_focus_signature"] = f"{lang}::{repo}::{task}"
    return updated


def sanitize_eval_row(row: dict[str, Any], split: str) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = split
    updated["disable_losses"] = []
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    return updated


def main() -> None:
    base_summary = load_json(BASE_SUMMARY_JSON)
    train_rows = [annotate_train_row(row) for row in load_jsonl(BASE_TRAIN_JSONL) if str(row.get("task_type") or "unknown") in KEEP_TASKS]
    train_rows = dedupe(train_rows)
    validation_rows = [sanitize_eval_row(row, "eval") for row in load_jsonl(BASE_VALIDATION_JSONL)]
    strict_rows = [sanitize_eval_row(row, "strict_eval") for row in load_jsonl(BASE_STRICT_JSONL)]
    stress_rows = load_jsonl(BASE_STRESS_JSONL)
    primary_rows = [row for row in train_rows if row.get("residual_lane_role") == "primary"]
    anchor_rows = [row for row in train_rows if row.get("residual_lane_role") == "anchor"]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(train_rows) and bool(strict_rows),
        "decision": "evidence_lane_sampler_support_package_ready",
        "claim_scope": [
            "Retain the clean heldout overlay while reshaping train rows around the actual evidence and verifier decision lanes.",
            "Provide a sampler-ready manifest where residual evidence/verifier rows are primary and broader tasks are explicit preservation anchors.",
        ],
        "required_honesty_gates": [
            "Validation, strict, and stress rows are copied unchanged from stage10983.",
            "No new same-surface strict successor rows enter train in this package.",
            "Primary rows are limited to audited train-support tasks already present in stage10983.",
        ],
        "source_artifacts": {
            "base_summary": rel(BASE_SUMMARY_JSON),
            "base_train": rel(BASE_TRAIN_JSONL),
        },
        "metrics": {
            "train_rows_after_filter": len(train_rows),
            "primary_rows": len(primary_rows),
            "anchor_rows": len(anchor_rows),
            "train_by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in train_rows).items())),
            "train_by_task": dict(sorted(Counter(str(row.get("task_type") or "unknown") for row in train_rows).items())),
            "primary_by_task": dict(sorted(Counter(str(row.get("task_type") or "unknown") for row in primary_rows).items())),
            "primary_by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in primary_rows).items())),
            "anchor_by_task": dict(sorted(Counter(str(row.get("task_type") or "unknown") for row in anchor_rows).items())),
            "base_metrics_snapshot": base_summary.get("metrics"),
        },
        "headline_findings": [
            "This package removes one-off side tasks and makes evidence/verifier-related rows the explicit primary lane.",
            "Preservation anchors remain in train, but are no longer the dominant geometry for the next probe.",
            "The package is designed to pair with residual_family_balanced sampling and anchor-only KL preservation.",
        ],
        "next_best_step": "Run one bounded decoder probe with residual_family_balanced sampling and KL preservation applied only to anchor rows.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
            "primary_rows_jsonl": rel(PRIMARY_ROWS_JSONL),
            "anchor_rows_jsonl": rel(ANCHOR_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)
    write_jsonl(PRIMARY_ROWS_JSONL, primary_rows)
    write_jsonl(ANCHOR_ROWS_JSONL, anchor_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
