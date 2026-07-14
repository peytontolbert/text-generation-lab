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
STAGE = 10994
NAME = "stage10994_mixed_semantic_evidence_lane_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "mixed_semantic_evidence_lane_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_ROWS_JSONL = OUT_DIR / "added_semantic_rows.jsonl"

BASE_DIR = ARTIFACTS / "stage10990_evidence_lane_sampler_support_package"
BASE_SUMMARY_JSON = BASE_DIR / "evidence_lane_sampler_support_package.json"
BASE_TRAIN_JSONL = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION_JSONL = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT_JSONL = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS_JSONL = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

SEMANTIC_DIR = ARTIFACTS / "stage10925_reviewed_evidence_role_semantic_support_package"
SEMANTIC_SUMMARY_JSON = SEMANTIC_DIR / "reviewed_evidence_role_semantic_support_package.json"
SEMANTIC_ROWS_JSONL = SEMANTIC_DIR / "support_rows.jsonl"


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


def annotate_base_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = "train"
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["disable_losses"] = []
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    return updated


def annotate_semantic_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = annotate_base_row(row)
    updated["residual_lane_role"] = "primary_semantic"
    updated["preservation_exempt"] = True
    updated["bounded_decoder_sampler_group"] = "evidence_semantic"
    updated["semantic_interface_branch"] = True
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
    semantic_summary = load_json(SEMANTIC_SUMMARY_JSON)
    base_train = [annotate_base_row(row) for row in load_jsonl(BASE_TRAIN_JSONL)]
    semantic_rows = [annotate_semantic_row(row) for row in load_jsonl(SEMANTIC_ROWS_JSONL)]
    validation_rows = [sanitize_eval_row(row, "eval") for row in load_jsonl(BASE_VALIDATION_JSONL)]
    strict_rows = [sanitize_eval_row(row, "strict_eval") for row in load_jsonl(BASE_STRICT_JSONL)]
    stress_rows = load_jsonl(BASE_STRESS_JSONL)
    merged_train = dedupe(base_train + semantic_rows)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(merged_train) and bool(strict_rows),
        "decision": "mixed_semantic_evidence_lane_support_package_ready",
        "claim_scope": [
            "Add semantic evidence-role supervision on top of the evidence-lane sampler package to test a deeper target/interface change.",
            "Keep the same 23-row validation and strict overlays fixed so this branch is judged against the honest heldout frontier.",
        ],
        "required_honesty_gates": [
            "Validation and strict rows remain unchanged from stage10990.",
            "All semantic rows remain train_support_only and strict_eval_eligible=false.",
            "This branch is diagnostic because the semantic support rows include same-family overlap material from stage10925.",
        ],
        "metrics": {
            "train_rows_before": len(base_train),
            "semantic_rows_added": len(semantic_rows),
            "train_rows_after": len(merged_train),
            "semantic_by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in semantic_rows).items())),
            "semantic_by_target": dict(sorted(Counter(str(row.get("target_text") or "unknown") for row in semantic_rows).items())),
            "semantic_by_objective": dict(sorted(Counter(str(row.get("objective_family") or "unknown") for row in semantic_rows).items())),
            "train_by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in merged_train).items())),
            "train_by_task": dict(sorted(Counter(str(row.get("task_type") or "unknown") for row in merged_train).items())),
            "base_metrics_snapshot": base_summary.get("metrics"),
            "semantic_metrics_snapshot": semantic_summary.get("metrics"),
        },
        "headline_findings": [
            "This is the first branch that combines evidence-lane geometry control with explicit semantic evidence-role targets.",
            "It is diagnostic-only because the semantic support source still contains overlap-family material, but it directly tests whether the target interface is the missing lever.",
            "If this branch cannot move the successor evidence slice, more letter-space tuning is not the right next path.",
        ],
        "next_best_step": "Run one diagnostic probe with encoder_option_retrieval_dynamic_productized and residual-family-balanced sampling, then audit overlay preservation and residual-slice movement.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
            "added_rows_jsonl": rel(ADDED_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_jsonl(TRAIN_JSONL, merged_train)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)
    write_jsonl(ADDED_ROWS_JSONL, semantic_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
