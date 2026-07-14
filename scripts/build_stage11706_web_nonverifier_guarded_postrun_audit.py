#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11706_web_nonverifier_guarded_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_nonverifier_guarded_postrun_audit.json"

STAGE11703 = ROOT / "scripts/build_stage11703_web_transition_product_policy_integration_audit.py"
spec = importlib.util.spec_from_file_location("stage11703_base_for_11706", STAGE11703)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to import {STAGE11703}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

PROBE_RUNTIME = ART / "stage11705_web_nonverifier_guarded_probe/runtime_model/runtime_model_bundle.json"
BASELINE_SUMMARY = ART / "stage11703_web_transition_product_policy_integration_audit/web_transition_product_policy_integration_audit.json"
ROW_CARDS = OUT / "web_nonverifier_guarded_product_policy_rows.jsonl"
MISS_ROWS = OUT / "web_nonverifier_guarded_remaining_misses.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    old_runtime = base.IDENTITY_RUNTIME
    try:
        base.IDENTITY_RUNTIME = PROBE_RUNTIME
        rows = [base.NORMALIZER.normalize_row(row) for row in base.load_jsonl(base.BRIDGED_ROWS)]
        cards, meta = base.product_score_rows(rows)
    finally:
        base.IDENTITY_RUNTIME = old_runtime

    misses = [row for row in cards if not row["product_correct"]]
    write_jsonl(ROW_CARDS, cards)
    write_jsonl(MISS_ROWS, misses)
    metrics = base.summarize_cards(cards)
    baseline = load_json(BASELINE_SUMMARY)
    baseline_metrics = baseline.get("metrics") or {}
    gemma = base.gemma_metrics()
    anti = base.leak_audit(rows)
    protected = base.protected_gates()
    gates = {
        "runtime_exists": PROBE_RUNTIME.exists(),
        "product_web_at_least_stage11703_60_of_66": metrics["correct"] >= 60 and metrics["rows"] == 66,
        "remaining_misses_less_than_stage11703_6": len(misses) < int((baseline.get("remaining_misses") or {}).get("rows") or 999),
        "product_beats_gemma": metrics["correct"] > gemma["correct"] and metrics["rows"] == gemma["rows"] == 66,
        "no_singletons": anti["singleton_rows"] == 0,
        "no_prompt_label_leaks": anti["prompt_label_leaks"] == 0,
        "no_prompt_target_value_leaks": anti["prompt_target_value_leaks"] == 0,
        "protected_filtered_strict": protected["filtered_strict_22_of_22"],
        "protected_old_canary_strict": protected["old_canary_strict_23_of_23"],
        "protected_residual": protected["residual_at_least_7_of_10"],
    }
    decision = "stage11705_promoted" if all(gates.values()) else "stage11705_rejected_or_diagnostic_only"
    summary = {
        "stage": 11706,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "metrics": metrics,
        "baseline_stage11703": {
            "correct": baseline_metrics.get("correct"),
            "rows": baseline_metrics.get("rows"),
            "accuracy": baseline_metrics.get("accuracy"),
            "remaining_misses": (baseline.get("remaining_misses") or {}).get("rows"),
        },
        "gemma": gemma,
        "remaining_misses": {
            "rows": len(misses),
            "row_ids": [str(row.get("row_id")) for row in misses],
            "by_task": {task: sum(1 for row in misses if row.get("task_type") == task) for task in sorted({row.get("task_type") for row in misses})},
            "by_repo": {repo: sum(1 for row in misses if row.get("repo_id") == repo) for repo in sorted({row.get("repo_id") for row in misses})},
        },
        "anti_cheat": anti,
        "protected_gates": protected,
        "gates": gates,
        "runtime": {
            "probe_runtime": rel(PROBE_RUNTIME),
            "weights_sha256": meta["bundle"].get("weights_sha256"),
        },
        "claim_boundary": [
            "This audits the Stage11705 trained head under the Stage11703 product policy.",
            "Promotion requires improving the remaining miss count without dropping below 60/66 or protected gates.",
        ],
        "outputs": {
            "summary": rel(SUMMARY),
            "row_cards": rel(ROW_CARDS),
            "remaining_misses": rel(MISS_ROWS),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "metrics": metrics, "remaining_misses": summary["remaining_misses"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
