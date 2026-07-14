#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11707_web_nonverifier_support_fit_delta_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_nonverifier_support_fit_delta_audit.json"
ROW_CARDS = OUT / "web_nonverifier_support_fit_delta_rows.jsonl"

BASE_SCRIPT = ROOT / "scripts/build_stage11697_web_gap_margin_delta_audit.py"
spec = importlib.util.spec_from_file_location("stage11697_base_for_11707", BASE_SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to import {BASE_SCRIPT}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

SUPPORT_ROWS = ART / "stage11704_web_remaining_nonverifier_support_package/web_remaining_nonverifier_support_rows.jsonl"
BASELINE_RUNTIME = ART / "stage11685_counterfactual_identity_semantic_head_fixed_probe/runtime_model/runtime_model_bundle.json"
PROBE_RUNTIME = ART / "stage11705_web_nonverifier_guarded_probe/runtime_model/runtime_model_bundle.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def summarize(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups = sorted({str(row.get(key) or "") for row in rows})
    out = {}
    for group in groups:
        subset = [row for row in rows if str(row.get(key) or "") == group]
        base_correct = sum(1 for row in subset if row.get("baseline_correct") is True)
        probe_correct = sum(1 for row in subset if row.get("probe_correct") is True)
        out[group] = {
            "rows": len(subset),
            "baseline_correct": base_correct,
            "baseline_accuracy": base_correct / len(subset) if subset else None,
            "probe_correct": probe_correct,
            "probe_accuracy": probe_correct / len(subset) if subset else None,
            "delta_correct": probe_correct - base_correct,
        }
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [base.base.base.normalize_row(row) for row in load_jsonl(SUPPORT_ROWS)]
    baseline, baseline_meta = base.score_rows(BASELINE_RUNTIME, rows, "stage11685_support_fit")
    probe, probe_meta = base.score_rows(PROBE_RUNTIME, rows, "stage11705_support_fit")
    by_id = {str(row.get("row_id")): row for row in rows}
    probe_by_id = {str(row.get("row_id")): row for row in probe}
    joined: list[dict[str, Any]] = []
    for b in baseline:
        rid = str(b.get("row_id"))
        p = probe_by_id[rid]
        src = by_id[rid]
        joined.append(
            {
                "row_id": rid,
                "root_id": src.get("root_id"),
                "repo_id": src.get("repo_id") or src.get("repo_family"),
                "task_type": src.get("task_type"),
                "lane": src.get("stage11704_lane"),
                "baseline_predicted_label": b.get("predicted_label"),
                "baseline_correct": b.get("correct"),
                "baseline_margin": b.get("target_minus_top_wrong_margin"),
                "probe_predicted_label": p.get("predicted_label"),
                "probe_correct": p.get("correct"),
                "probe_margin": p.get("target_minus_top_wrong_margin"),
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
    base_correct = sum(1 for row in joined if row["baseline_correct"] is True)
    probe_correct = sum(1 for row in joined if row["probe_correct"] is True)
    summary = {
        "stage": 11707,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": (
            "stage11705_fit_support_but_did_not_transfer"
            if probe_correct > base_correct
            else "stage11705_did_not_fit_support_or_transfer"
        ),
        "metrics": {
            "rows": len(joined),
            "baseline_correct": base_correct,
            "baseline_accuracy": base_correct / len(joined) if joined else None,
            "probe_correct": probe_correct,
            "probe_accuracy": probe_correct / len(joined) if joined else None,
            "delta_correct": probe_correct - base_correct,
            "status_counts": dict(Counter(row["status_change"] for row in joined).most_common()),
            "by_lane": summarize(joined, "lane"),
            "by_task": summarize(joined, "task_type"),
            "by_repo": summarize(joined, "repo_id"),
        },
        "interpretation": [
            "If support fit improves while Stage11706 heldout does not, the non-verifier issue is transfer/generalization, not optimizer failure.",
            "If support fit is flat, the semantic candidate head objective/sampler is not absorbing the new support rows.",
        ],
        "runtime": {
            "baseline_runtime": rel(BASELINE_RUNTIME),
            "baseline_weights_sha256": baseline_meta["bundle"].get("weights_sha256"),
            "probe_runtime": rel(PROBE_RUNTIME),
            "probe_weights_sha256": probe_meta["bundle"].get("weights_sha256"),
        },
        "source_artifacts": {"support_rows": rel(SUPPORT_ROWS)},
        "outputs": {"summary": rel(SUMMARY), "row_cards": rel(ROW_CARDS)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
