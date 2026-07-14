#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10962
NAME = "stage10962_explicit_ledger_plateau_decision"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "explicit_ledger_plateau_decision.json"

POSTRUN_JSON = ARTIFACTS / "stage10961_clean_explicit_ledger_postrun_audit" / "clean_explicit_ledger_postrun_audit.json"
ANTICHEAT_JSON = ARTIFACTS / "stage10958_explicit_ledger_anticheat_audit" / "explicit_ledger_anticheat_audit.json"
WORK_ITEMS_JSONL = ARTIFACTS / "stage10957_immediate_evidence_materialization_request" / "materialization_work_items.jsonl"
SCORER_DECISION_JSON = ARTIFACTS / "stage10955_evidence_scorer_blend_decision" / "evidence_scorer_blend_decision.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    postrun = load_json(POSTRUN_JSON)
    anticheat = load_json(ANTICHEAT_JSON)
    scorer = load_json(SCORER_DECISION_JSON)
    work_items = load_jsonl(WORK_ITEMS_JSONL)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "explicit_ledger_geometry_clean_but_not_sufficient",
        "claim_scope": [
            "Record the outcome of the anti-cheat-clean explicit-ledger branch after stage10960/stage10961.",
            "Set the next honest frontier after the cleaned geometry failed to improve the fresh successor slice.",
        ],
        "source_artifacts": {
            "postrun_audit": rel(POSTRUN_JSON),
            "anticheat_audit": rel(ANTICHEAT_JSON),
            "work_items": rel(WORK_ITEMS_JSONL),
            "scorer_exhaustion_decision": rel(SCORER_DECISION_JSON),
        },
        "headline": {
            "overlay_strict_accuracy": ((postrun.get("overlay") or {}).get("strict_accuracy")),
            "fresh_slice_accuracy": (((postrun.get("fresh_successor_slice") or {}).get("overall") or {}).get("exact_accuracy")),
            "fresh_slice_improved_rows": ((postrun.get("fresh_successor_slice") or {}).get("improved_rows")),
            "fresh_slice_regressed_rows": ((postrun.get("fresh_successor_slice") or {}).get("regressed_rows")),
            "anticheat_passed": anticheat.get("passed"),
            "linear_scorer_fix_remaining": False,
        },
        "findings": [
            "The cleaned explicit-ledger package is anti-cheat cleaner than the earlier branch and preserves the 22/23 strict overlay.",
            "The fresh 3-row successor slice stayed flat at 1/3 with zero changed rows, so row cleanup alone did not break the B-vs-F boundary.",
            "The only remaining honest branches are richer row supply and/or scorer architecture changes beyond generic option-retrieval similarity.",
        ],
        "next_ordered_branches": [
            {
                "priority": 1,
                "branch": "fresh_row_supply",
                "work": [
                    "Expand python_repository_library_evidence_b_vs_f_replenishment into multiple fresh roots, not one successor row.",
                    "Expand cpp_parametergolf_evidence_b_vs_f_replenishment with additional verifier-ledger-positive roots plus counterfamily controls.",
                    "Materialize one fresh non-aliased Rust E-vs-F family before claiming multilingual evidence progress."
                ],
            },
            {
                "priority": 2,
                "branch": "scorer_architecture",
                "work": [
                    "Prototype evidence-role-specific scoring instead of one generic encoder_option_retrieval similarity score.",
                    "Add pairwise candidate_change_surface vs verifier_and_test_constraint scoring heads or losses.",
                    "Evaluate any new scorer under the same frozen 23-row overlay and the fresh successor slice."
                ],
            },
            {
                "priority": 3,
                "branch": "web_supply_governance",
                "work": [
                    "Keep overlap web rows stress-only.",
                    "Acquire a pure-web selected-test family before any stronger multilingual headline claim."
                ],
            },
        ],
        "immediate_recommendation": {
            "next_branch": "fresh_row_supply",
            "why": "Scorer-tuning and cleaned-geometry branches are both exhausted without moving the successor slice.",
            "top_work_items": work_items[:4],
        },
    }

    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
