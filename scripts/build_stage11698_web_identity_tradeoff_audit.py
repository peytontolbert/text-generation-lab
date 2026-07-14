#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "scripts/build_stage11697_web_gap_margin_delta_audit.py"
spec = importlib.util.spec_from_file_location("stage11697_base_for_11698", BASE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to load {BASE}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

ROUTE_BASE = base.base
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11698_web_identity_tradeoff_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_identity_tradeoff_audit.json"
ROW_CARDS = OUT / "web_identity_tradeoff_rows.jsonl"

BRIDGED_ROWS = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridged_rows.jsonl"
GAP_ROWS = ART / "stage11692_web_bridged_miss_family_audit/web_bridged_gemma_margin_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    all_rows = [ROUTE_BASE.base.normalize_row(row) for row in base.load_jsonl(BRIDGED_ROWS)]
    identity_rows = [row for row in all_rows if ROUTE_BASE.route(row) == "identity"]
    gap_ids = {str(row.get("row_id")) for row in base.load_jsonl(GAP_ROWS)}
    baseline, baseline_meta = base.score_rows(base.BASELINE_RUNTIME, identity_rows, "stage11685_identity_all")
    probe, probe_meta = base.score_rows(base.PROBE_RUNTIME, identity_rows, "stage11695_identity_all")
    probe_by_id = {str(row["row_id"]): row for row in probe}
    joined: list[dict[str, Any]] = []
    for b in baseline:
        row_id = str(b["row_id"])
        p = probe_by_id[row_id]
        delta = None
        if b.get("target_minus_top_wrong_margin") is not None and p.get("target_minus_top_wrong_margin") is not None:
            delta = float(p["target_minus_top_wrong_margin"]) - float(b["target_minus_top_wrong_margin"])
        row = next(row for row in identity_rows if str(row.get("row_id")) == row_id)
        joined.append(
            {
                "row_id": row_id,
                "task_type": row.get("task_type"),
                "repo_id": row.get("repo_id"),
                "is_gemma_margin_gap_row": row_id in gap_ids,
                "target_label": b.get("target_label"),
                "target_role": b.get("target_role"),
                "baseline_predicted_label": b.get("predicted_label"),
                "baseline_predicted_role": b.get("predicted_role"),
                "baseline_correct": b.get("correct"),
                "baseline_target_minus_top_wrong_margin": b.get("target_minus_top_wrong_margin"),
                "probe_predicted_label": p.get("predicted_label"),
                "probe_predicted_role": p.get("predicted_role"),
                "probe_correct": p.get("correct"),
                "probe_target_minus_top_wrong_margin": p.get("target_minus_top_wrong_margin"),
                "target_margin_delta": delta,
                "prediction_changed": b.get("predicted_label") != p.get("predicted_label"),
                "status_change": (
                    "wrong_to_correct"
                    if b.get("correct") is not True and p.get("correct") is True
                    else "correct_to_wrong"
                    if b.get("correct") is True and p.get("correct") is not True
                    else "stayed_correct"
                    if p.get("correct") is True
                    else "stayed_wrong"
                ),
            }
        )
    write_jsonl(ROW_CARDS, joined)
    status_counts = Counter(row["status_change"] for row in joined)
    by_task_status = {}
    for task in sorted({str(row.get("task_type")) for row in joined}):
        subset = [row for row in joined if str(row.get("task_type")) == task]
        by_task_status[task] = dict(Counter(row["status_change"] for row in subset).most_common())
    regressions = [row for row in joined if row["status_change"] == "correct_to_wrong"]
    gains = [row for row in joined if row["status_change"] == "wrong_to_correct"]
    gap_gains = [row for row in gains if row["is_gemma_margin_gap_row"]]
    non_gap_regressions = [row for row in regressions if not row["is_gemma_margin_gap_row"]]
    gates = {
        "identity_rows_40": len(joined) == 40,
        "gap_gains_3": len(gap_gains) == 3,
        "no_non_gap_regressions": len(non_gap_regressions) == 0,
        "net_identity_gain_positive": (sum(1 for row in joined if row.get("probe_correct")) - sum(1 for row in joined if row.get("baseline_correct"))) > 0,
    }
    decision = (
        "stage11695_identity_gain_offset_by_regressions"
        if len(gap_gains) > 0 and len(regressions) > 0
        else "stage11695_identity_clean_gain"
        if len(gap_gains) > 0 and not regressions
        else "stage11695_identity_no_gain"
    )
    summary = {
        "stage": 11698,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "metrics": {
            "identity_rows": len(joined),
            "baseline_correct": sum(1 for row in joined if row.get("baseline_correct")),
            "probe_correct": sum(1 for row in joined if row.get("probe_correct")),
            "status_counts": dict(status_counts.most_common()),
            "gap_gains": len(gap_gains),
            "all_regressions": len(regressions),
            "non_gap_regressions": len(non_gap_regressions),
            "by_task_status": by_task_status,
            "regression_rows": [
                {k: row.get(k) for k in ["row_id", "task_type", "repo_id", "target_label", "target_role", "baseline_predicted_label", "probe_predicted_label", "target_margin_delta"]}
                for row in regressions
            ],
            "gain_rows": [
                {k: row.get(k) for k in ["row_id", "task_type", "repo_id", "target_label", "target_role", "baseline_predicted_label", "probe_predicted_label", "target_margin_delta"]}
                for row in gains
            ],
        },
        "gates": gates,
        "recommended_next": [
            "Preserve the Stage11695 verifier_outcome gain, but prevent regressions on already-correct same-role identity rows.",
            "Next probe should add preservation/listwise replay specifically for the correct_to_wrong rows, not more generic source/fix support.",
            "Use row-level status_change as promotion criterion: require gap gains with zero non-gap regressions.",
        ],
        "runtime": {
            "baseline_runtime": rel(base.BASELINE_RUNTIME),
            "baseline_weights_sha256": baseline_meta["bundle"].get("weights_sha256"),
            "probe_runtime": rel(base.PROBE_RUNTIME),
            "probe_weights_sha256": probe_meta["bundle"].get("weights_sha256"),
        },
        "source_artifacts": {"bridged_rows": rel(BRIDGED_ROWS), "gap_rows": rel(GAP_ROWS)},
        "outputs": {"summary": rel(SUMMARY), "row_cards": rel(ROW_CARDS)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "metrics": summary["metrics"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
