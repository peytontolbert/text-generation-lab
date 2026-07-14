#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10464
NAME = "stage10464_rust_citation_fresh_root_inventory"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_JSON = OUT_DIR / "rust_citation_fresh_root_inventory.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "rust_citation_fresh_root_supply_inventory_ready",
        "current_live_residual": {
            "row_id": "stage10126::tokenizers::tokenizers::rust::evidence_citation::reviewed_v27_compact",
            "target": "E",
            "predicted": "F",
            "task_boundary": "symptom_or_call_path_analogue should beat verifier_and_test_constraint",
        },
        "current_supply_state": {
            "disjoint_candle_core_rows_exist": True,
            "exact_e_vs_f_disjoint_contrast_exists": False,
            "same_surface_tokenizers_contrast_exists": True,
        },
        "candidate_root_families": [
            {
                "bundle_id": "stage10126::candle::candle-core::rust",
                "role": "disjoint rust citation support family",
                "available_rows": 5,
                "why_useful": "real rust evidence-citation rows with permutation variants, but they mostly target candidate_change_surface rather than the tokenizers E-vs-F boundary",
                "promotion_status": "useful_support_but_not_sufficient_for_exact_residual",
            },
            {
                "bundle_id": "stage10126::tokenizers::tokenizers::rust",
                "role": "same-surface diagnostic contrast family",
                "available_rows": 6,
                "why_useful": "contains the exact E-vs-F opposition needed to test boundary movability",
                "promotion_status": "diagnostic_only_non_promotable",
            },
        ],
        "identified_gap": [
            "no fresh disjoint rust root currently exposes both symptom_or_call_path_analogue and verifier_and_test_constraint as competing visible options",
            "at least one non-tokenizers repo family with that exact opposition is still missing",
        ],
        "builder_requirements": [
            "create at least 6 new rust evidence-citation roots with real E-vs-F style opposition",
            "include both symptom_or_call_path_analogue and verifier_and_test_constraint in the visible option set",
            "source at least one repo family beyond tokenizers",
            "keep tokenizers same-surface rows diagnostic-only and out of promotable support manifests",
        ],
    }
    write_json(OUT_JSON, payload)
    write_json(SUMMARY, {"stage": STAGE, "passed": True, "inventory": str(OUT_JSON.relative_to(ROOT))})
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
