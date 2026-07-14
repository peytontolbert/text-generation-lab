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
STAGE = 11671
NAME = "stage11671_web_canonical_contrast_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_canonical_contrast_decision.json"

NO_CONTRAST = ART / "stage11665_web_canonical_head_only_postrun_audit/web_canonical_head_only_postrun_audit.json"
ROLE_CONTRAST = ART / "stage11667_web_canonical_active_contrast_postrun_audit/web_canonical_active_contrast_postrun_audit.json"
VALUE_CONTRAST = ART / "stage11670_web_canonical_verifier_value_contrast_postrun_audit/web_canonical_verifier_value_contrast_postrun_audit.json"
MISS_GEOMETRY = ART / "stage11668_web_canonical_miss_geometry_audit/web_canonical_miss_geometry_audit.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def result_card(path: Path) -> dict[str, Any]:
    data = load_json(path)
    results = data["results"]
    return {
        "artifact": rel(path),
        "decision": data["decision"],
        "runtime": data.get("runtime"),
        "weights_sha256": data.get("runtime_weights_sha256"),
        "canonical_heldout": f"{results['canonical_heldout']['correct']}/{results['canonical_heldout']['rows']}",
        "original_web_heldout": f"{results['original_web_heldout']['correct']}/{results['original_web_heldout']['rows']}",
        "canonical_train_support": f"{results['canonical_train_support']['correct']}/{results['canonical_train_support']['rows']}",
        "filtered_strict": f"{results['filtered_strict']['correct']}/{results['filtered_strict']['rows']}",
        "old_canary_strict": f"{results['old_canary_strict']['correct']}/{results['old_canary_strict']['rows']}",
        "filtered_validation": f"{results['filtered_validation']['correct']}/{results['filtered_validation']['rows']}",
        "old_canary_validation": f"{results['old_canary_validation']['correct']}/{results['old_canary_validation']['rows']}",
        "residual_bank": f"{results['residual_bank']['correct']}/{results['residual_bank']['rows']}",
        "contrast": data.get("training_contrast_summary"),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cards = {
        "stage11665_no_active_contrast": result_card(NO_CONTRAST),
        "stage11667_role_contrast": result_card(ROLE_CONTRAST),
        "stage11670_verifier_value_contrast": result_card(VALUE_CONTRAST),
    }
    miss_geometry = load_json(MISS_GEOMETRY)
    gates = {
        "protected_gates_preserved_in_latest": all(
            [
                cards["stage11670_verifier_value_contrast"]["filtered_strict"] == "22/22",
                cards["stage11670_verifier_value_contrast"]["old_canary_strict"] == "23/23",
                cards["stage11670_verifier_value_contrast"]["filtered_validation"] == "20/22",
                cards["stage11670_verifier_value_contrast"]["old_canary_validation"] == "21/23",
                cards["stage11670_verifier_value_contrast"]["residual_bank"] == "7/10",
            ]
        ),
        "canonical_heldout_above_routed_frontier": cards["stage11670_verifier_value_contrast"]["canonical_heldout"] == "50/66",
        "original_web_heldout_below_routed_frontier": cards["stage11670_verifier_value_contrast"]["original_web_heldout"] == "27/66",
        "contrast_value_patch_did_not_improve_score": cards["stage11667_role_contrast"]["canonical_heldout"]
        == cards["stage11670_verifier_value_contrast"]["canonical_heldout"],
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "reject_canonical_contrast_reruns_as_frontier_path" if all(gates.values()) else "canonical_contrast_decision_needs_review",
        "cards": cards,
        "gates": gates,
        "miss_geometry": {
            "artifact": rel(MISS_GEOMETRY),
            "dominant_miss_families": miss_geometry.get("dominant_miss_families"),
            "miss_summary": miss_geometry.get("miss_summary"),
        },
        "interpretation": [
            "The canonical renderer is learnable and source-clean: canonical heldout is 50/66 with protected gates preserved.",
            "Active role contrast and same-role verifier-transition contrast both failed to improve canonical heldout beyond 50/66.",
            "Original Web heldout remains below the selected routed frontier, so this is not product Web progress.",
            "Remaining canonical misses are mostly candidate identity selection inside verifier/test constraints, not broad role discrimination.",
        ],
        "next_required_intervention": {
            "primary": "build verifier-candidate identity features or a listwise same-role verifier candidate objective",
            "do_not_repeat": [
                "do not rerun the same 334-row canonical package with only contrast-weight tweaks",
                "do not promote Stage11664/11666/11669 as selected frontier",
            ],
            "minimum_next_experiment": [
                "same canonical renderer",
                "head-only or scorer-head-only",
                "explicit candidate-value/listwise loss over PASS/FAIL/NOT_EXERCISED verifier options",
                "promotion requires canonical heldout >52/66 or original Web heldout >38/66 with protected gates preserved",
            ],
        },
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({
        "decision": summary["decision"],
        "cards": cards,
        "gates": gates,
        "next_required_intervention": summary["next_required_intervention"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
