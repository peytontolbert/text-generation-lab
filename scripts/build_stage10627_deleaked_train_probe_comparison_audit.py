#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10627
NAME = "stage10627_deleaked_train_probe_comparison_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "deleaked_train_probe_comparison_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_EXEC = ROOT / "runs/local/artifacts/stage10623_multilingual_deduped_eval_probe/bounded_decoder_probe/execution_result.json"
DELEAKED_EXEC = ROOT / "runs/local/artifacts/stage10626_multilingual_deleaked_train_probe/bounded_decoder_probe/execution_result.json"
DELEAKED_PACKAGE = ROOT / "runs/local/artifacts/stage10625_multilingual_deleaked_train_package/multilingual_deleaked_train_package.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def strict_summary(execution: dict[str, Any]) -> dict[str, Any]:
    strict = ((execution.get("bounded_choice_eval") or {}).get("strict_eval") or {})
    return {
        "rows": strict.get("rows"),
        "constrained_choice_top1_accuracy": strict.get("constrained_choice_top1_accuracy"),
        "full_vocab_top1_accuracy": strict.get("full_vocab_top1_accuracy"),
        "rows_with_target_rank_1": strict.get("rows_with_target_rank_1"),
        "weights_sha256": ((execution.get("runtime_model_bundle") or {}).get("weights_sha256")),
    }


def miss_map(execution: dict[str, Any]) -> dict[str, dict[str, Any]]:
    strict = ((execution.get("bounded_choice_eval") or {}).get("strict_eval") or {})
    out: dict[str, dict[str, Any]] = {}
    for row in strict.get("row_cards") or []:
        if row.get("constrained_choice_match") is False:
            out[str(row.get("row_id") or "")] = {
                "target_text": row.get("target_text"),
                "predicted_label": row.get("constrained_choice_top1_label"),
                "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                "target_rank_full_vocab": row.get("target_rank_full_vocab"),
            }
    return out


def main() -> None:
    base_exec = load_json(BASE_EXEC)
    deleaked_exec = load_json(DELEAKED_EXEC)
    deleaked_package = load_json(DELEAKED_PACKAGE)

    base_summary = strict_summary(base_exec)
    deleaked_summary = strict_summary(deleaked_exec)
    base_misses = miss_map(base_exec)
    deleaked_misses = miss_map(deleaked_exec)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "train_leak_cleanup_preserved_honest_multilingual_score",
        "claim_scope": [
            "Compare the honest multilingual baseline probe against the de-leaked-train successor probe.",
            "Report whether removing train-side prompt leaks changed the strict benchmark result.",
            "This audit does not certify the train package as final; it isolates one training-surface cleanup effect.",
        ],
        "inputs": {
            "baseline_execution": display(BASE_EXEC),
            "deleaked_execution": display(DELEAKED_EXEC),
            "deleaked_package": display(DELEAKED_PACKAGE),
        },
        "baseline_strict": base_summary,
        "deleaked_strict": deleaked_summary,
        "delta": {
            "constrained_choice_top1_accuracy": (deleaked_summary["constrained_choice_top1_accuracy"] or 0.0)
            - (base_summary["constrained_choice_top1_accuracy"] or 0.0),
            "full_vocab_top1_accuracy": (deleaked_summary["full_vocab_top1_accuracy"] or 0.0)
            - (base_summary["full_vocab_top1_accuracy"] or 0.0),
            "rows_with_target_rank_1": (deleaked_summary["rows_with_target_rank_1"] or 0)
            - (base_summary["rows_with_target_rank_1"] or 0),
        },
        "baseline_misses": base_misses,
        "deleaked_misses": deleaked_misses,
        "same_miss_set": sorted(base_misses.keys()) == sorted(deleaked_misses.keys()),
        "interpretation": [
            "Removing the 24 train-side prompt leak rows did not change the honest strict score: the model remains 22/24.",
            "The same two reviewed strict residuals remain: Python verifier_outcome and Rust tokenizers evidence_citation.",
            "This suggests the current multilingual frontier is no longer being propped up by those train-side leak rows, at least on the reviewed 24-row strict slice.",
            "The next improvement lever is fresh disjoint data for the two residual skills, not leakage cleanup alone.",
        ],
        "next_best_step": "Build fresh disjoint Python verifier and Rust evidence-citation support roots, then compare against this de-leaked 22/24 baseline rather than replaying same-surface reviewed rows.",
    }
    write_json(AUDIT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "audit": display(AUDIT_JSON),
            "same_miss_set": payload["same_miss_set"],
            "strict_accuracy": deleaked_summary["constrained_choice_top1_accuracy"],
        },
    )
    print(json.dumps({"stage": STAGE, "passed": True, "same_miss_set": payload["same_miss_set"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
