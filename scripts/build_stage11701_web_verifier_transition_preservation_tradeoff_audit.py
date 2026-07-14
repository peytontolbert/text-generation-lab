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
BASE = ROOT / "scripts/build_stage11697_web_gap_margin_delta_audit.py"
spec = importlib.util.spec_from_file_location("stage11697_base_for_11701", BASE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to load {BASE}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
ROUTE_BASE = base.base

ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11701_web_verifier_transition_preservation_tradeoff_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_verifier_transition_preservation_tradeoff_audit.json"
ROW_CARDS = OUT / "web_verifier_transition_preservation_tradeoff_rows.jsonl"

BRIDGED_ROWS = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridged_rows.jsonl"
RUNTIMES = {
    "stage11685": ART / "stage11685_counterfactual_identity_semantic_head_fixed_probe/runtime_model/runtime_model_bundle.json",
    "stage11695": ART / "stage11695_web_identity_gap_topup_probe/runtime_model/runtime_model_bundle.json",
    "stage11699": ART / "stage11699_web_verifier_transition_preservation_probe/runtime_model/runtime_model_bundle.json",
}


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
    scored_by_runtime = {}
    runtime_meta = {}
    for name, runtime in RUNTIMES.items():
        cards, meta = base.score_rows(runtime, identity_rows, name)
        scored_by_runtime[name] = {str(row["row_id"]): row for row in cards}
        runtime_meta[name] = {"runtime": rel(runtime), "weights_sha256": meta["bundle"].get("weights_sha256")}
    rows = []
    for row in identity_rows:
        row_id = str(row.get("row_id"))
        rec = {"row_id": row_id, "task_type": row.get("task_type"), "repo_id": row.get("repo_id")}
        for name in RUNTIMES:
            card = scored_by_runtime[name][row_id]
            rec[f"{name}_predicted_label"] = card.get("predicted_label")
            rec[f"{name}_correct"] = card.get("correct")
            rec[f"{name}_margin"] = card.get("target_minus_top_wrong_margin")
        rec["stage11695_status_vs_11685"] = (
            "wrong_to_correct" if rec["stage11685_correct"] is not True and rec["stage11695_correct"] is True else
            "correct_to_wrong" if rec["stage11685_correct"] is True and rec["stage11695_correct"] is not True else
            "stayed_correct" if rec["stage11695_correct"] is True else "stayed_wrong"
        )
        rec["stage11699_status_vs_11685"] = (
            "wrong_to_correct" if rec["stage11685_correct"] is not True and rec["stage11699_correct"] is True else
            "correct_to_wrong" if rec["stage11685_correct"] is True and rec["stage11699_correct"] is not True else
            "stayed_correct" if rec["stage11699_correct"] is True else "stayed_wrong"
        )
        rec["stage11699_status_vs_11695"] = (
            "regained" if rec["stage11695_correct"] is not True and rec["stage11699_correct"] is True else
            "regressed" if rec["stage11695_correct"] is True and rec["stage11699_correct"] is not True else
            "preserved_correct" if rec["stage11699_correct"] is True else "preserved_wrong"
        )
        rows.append(rec)
    write_jsonl(ROW_CARDS, rows)

    def correct(name: str) -> int:
        return sum(1 for row in rows if row.get(f"{name}_correct") is True)

    status_9995 = Counter(row["stage11699_status_vs_11695"] for row in rows)
    status_9985 = Counter(row["stage11699_status_vs_11685"] for row in rows)
    regressions_from_95 = [row for row in rows if row["stage11699_status_vs_11695"] == "regressed"]
    regained_from_95 = [row for row in rows if row["stage11699_status_vs_11695"] == "regained"]
    gates = {
        "identity_rows_40": len(rows) == 40,
        "stage11699_beats_stage11695": correct("stage11699") > correct("stage11695"),
        "stage11699_at_least_stage11695": correct("stage11699") >= correct("stage11695"),
        "no_regressions_from_stage11695": len(regressions_from_95) == 0,
        "has_regains_from_stage11695": len(regained_from_95) > 0,
    }
    decision = (
        "stage11699_tradeoff_improved"
        if gates["stage11699_beats_stage11695"] and gates["no_regressions_from_stage11695"]
        else "stage11699_preservation_pass_no_net_gain"
        if gates["stage11699_at_least_stage11695"]
        else "stage11699_tradeoff_regressed"
    )
    summary = {
        "stage": 11701,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "metrics": {
            "identity_rows": len(rows),
            "stage11685_correct": correct("stage11685"),
            "stage11695_correct": correct("stage11695"),
            "stage11699_correct": correct("stage11699"),
            "stage11699_vs_11695_status_counts": dict(status_9995.most_common()),
            "stage11699_vs_11685_status_counts": dict(status_9985.most_common()),
            "regressions_from_stage11695": regressions_from_95,
            "regains_from_stage11695": regained_from_95,
        },
        "gates": gates,
        "runtime": runtime_meta,
        "recommended_next": [
            "If no net gain, stop scalar replay tuning and use a task/repo-conditional verifier-transition head or explicit transition-value scorer.",
            "Treat OpenHands PASS_TARGETED_TEST_SELECTION and MCP pass_targeted_test_selection as separate normalization families until a canonical transition-value encoder is implemented.",
        ],
        "outputs": {"summary": rel(SUMMARY), "row_cards": rel(ROW_CARDS)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "metrics": summary["metrics"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
