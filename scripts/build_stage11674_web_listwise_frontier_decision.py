#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11674
NAME = "stage11674_web_listwise_frontier_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_listwise_frontier_decision.json"

BASE = ART / "stage11670_web_canonical_verifier_value_contrast_postrun_audit/web_canonical_verifier_value_contrast_postrun_audit.json"
LISTWISE = ART / "stage11673_web_canonical_verifier_value_listwise_postrun_audit/web_canonical_verifier_value_listwise_postrun_audit.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def score(data: dict[str, Any], name: str) -> dict[str, Any]:
    results = data["results"]
    return {
        "name": name,
        "decision": data["decision"],
        "runtime": data.get("runtime"),
        "weights_sha256": data.get("runtime_weights_sha256"),
        "canonical_heldout": f"{results['canonical_heldout']['correct']}/{results['canonical_heldout']['rows']}",
        "original_web_heldout": f"{results['original_web_heldout']['correct']}/{results['original_web_heldout']['rows']}",
        "filtered_strict": f"{results['filtered_strict']['correct']}/{results['filtered_strict']['rows']}",
        "filtered_validation": f"{results['filtered_validation']['correct']}/{results['filtered_validation']['rows']}",
        "old_canary_strict": f"{results['old_canary_strict']['correct']}/{results['old_canary_strict']['rows']}",
        "old_canary_validation": f"{results['old_canary_validation']['correct']}/{results['old_canary_validation']['rows']}",
        "residual_bank": f"{results['residual_bank']['correct']}/{results['residual_bank']['rows']}",
        "telemetry": data.get("training_contrast_summary"),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base = load_json(BASE)
    listwise = load_json(LISTWISE)
    base_misses = {m["row_id"]: m for m in base["results"]["canonical_heldout"]["misses"]}
    listwise_misses = {m["row_id"]: m for m in listwise["results"]["canonical_heldout"]["misses"]}
    fixed = sorted(set(base_misses) - set(listwise_misses))
    new_misses = sorted(set(listwise_misses) - set(base_misses))
    gates = {
        "canonical_heldout_improved_by_one": base["results"]["canonical_heldout"]["correct"] == 50
        and listwise["results"]["canonical_heldout"]["correct"] == 51,
        "no_new_canonical_misses": not new_misses,
        "protected_gates_preserved": all(
            [
                listwise["results"]["filtered_strict"]["correct"] == 22,
                listwise["results"]["old_canary_strict"]["correct"] == 23,
                listwise["results"]["filtered_validation"]["correct"] == 20,
                listwise["results"]["old_canary_validation"]["correct"] == 21,
                listwise["results"]["residual_bank"]["correct"] == 7,
            ]
        ),
        "original_web_still_below_routed_frontier": listwise["results"]["original_web_heldout"]["correct"] < 39,
        "canonical_still_below_gemma": listwise["results"]["canonical_heldout"]["correct"] <= 52,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "listwise_objective_validated_but_not_promoted" if all(gates.values()) else "listwise_objective_decision_needs_review",
        "baseline": score(base, "stage11670_verifier_value_contrast"),
        "listwise": score(listwise, "stage11673_verifier_value_listwise"),
        "fixed_canonical_misses": fixed,
        "new_canonical_misses": new_misses,
        "remaining_canonical_misses": list(listwise_misses.values()),
        "gates": gates,
        "interpretation": [
            "The same-role verifier-value listwise objective fixed one verifier-outcome row with no protected-gate regression.",
            "This validates the Stage11668 diagnosis that same-role candidate identity was a real blocker.",
            "It is not promotable as product Web progress because original Web heldout remains 27/66, below the 38/66 routed frontier.",
            "It is not yet a Gemma Web win because canonical heldout is 51/66, below Gemma's 52/66 same-manifest Web score.",
        ],
        "next_recommended_experiment": {
            "target": "raise canonical Web heldout above 52/66 and restore original Web transfer above 38/66",
            "intervention": [
                "increase same-role verifier candidate identity coverage for MCP/SEP-style verifier rows",
                "add same-role candidate identity/listwise objectives for symptom_localization and minimal_fix_selection",
                "keep head-only until original Web heldout beats the routed 38/66 frontier",
            ],
            "do_not_claim": [
                "do not promote Stage11673 as selected product scorer",
                "do not claim broad Web superiority over Gemma yet",
            ],
        },
        "source_artifacts": {"baseline": rel(BASE), "listwise": rel(LISTWISE)},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({
        "decision": summary["decision"],
        "fixed_canonical_misses": fixed,
        "gates": gates,
        "next_recommended_experiment": summary["next_recommended_experiment"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
