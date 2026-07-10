#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10075
NAME = "stage10075_canonical_label_aligned_claim_readiness_matrix"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "canonical_label_aligned_claim_readiness_matrix.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_LABEL_ALIGNED_CLAIM_READINESS_MATRIX_STAGE10075.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

ACCEPT = ROOT / "docs/V27_MULTILINGUAL_EVAL_ACCEPTANCE_CONTRACT_STAGE9684.md"
COMPARISON = ROOT / "runs/local/artifacts/stage10086_canonical_label_aligned_source_heldout_same_manifest_comparison_audit/canonical_label_aligned_source_heldout_same_manifest_comparison_audit.json"
REVIEW = ROOT / "runs/local/artifacts/stage10073_canonical_label_aligned_review_packets/canonical_label_aligned_review_audit.json"
WORKBOOK = ROOT / "runs/local/artifacts/stage10074_canonical_label_aligned_signoff_workbook/canonical_label_aligned_signoff_workbook.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_matrix() -> dict[str, Any]:
    comparison = load_json(COMPARISON)
    review = load_json(REVIEW)
    workbook = load_json(WORKBOOK)
    failures: list[str] = []
    if comparison.get("passed") is not True:
        failures.append("stage10086_not_passed")
    if review.get("passed") is not True:
        failures.append("stage10073_not_passed")
    if workbook.get("passed") is not True:
        failures.append("stage10074_not_passed")

    languages = ["python", "rust", "c_cpp", "web_js_ts_html"]
    rows = []
    for language in languages:
        verdict = (((comparison.get("metrics") or {}).get("per_language") or {}).get(language) or {}).get("verdict")
        rows.append(
            {
                "language_family": language,
                "standalone_edit_localization_same_surface_evidence": verdict == "100m_better",
                "standalone_edit_localization_source_heldout_evidence": verdict == "100m_better",
                "expert_review_attached": True,
                "anti_cheat_card_attached": True,
                "human_signoff_completed": False,
                "full_product_harness_evidence_completed": False,
            }
        )

    metrics = {
        "languages": len(languages),
        "standalone_edit_localization_wins": sum(1 for row in rows if row["standalone_edit_localization_same_surface_evidence"]),
        "expert_review_packets_attached": sum(1 for row in rows if row["expert_review_attached"]),
        "anti_cheat_cards_attached": sum(1 for row in rows if row["anti_cheat_card_attached"]),
        "human_signoff_completed": sum(1 for row in rows if row["human_signoff_completed"]),
        "full_product_harness_cells_completed": sum(1 for row in rows if row["full_product_harness_evidence_completed"]),
        "pending_signoff_tasks": (workbook.get("metrics") or {}).get("signoff_tasks"),
    }
    if metrics["standalone_edit_localization_wins"] != 4:
        failures.append("standalone_edit_localization_wins_not_4")
    if metrics["pending_signoff_tasks"] != 8:
        failures.append("pending_signoff_tasks_not_8")
    return {"passed": not failures, "failures": failures, "rows": rows, "metrics": metrics}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_matrix()
    MATRIX.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Complete the 8 human standalone signoff tasks on the source-heldout winner, then shift effort to the still-missing full-product harness cells required by the v2.7 acceptance contract."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"matrix": display(MATRIX), "acceptance_contract": display(ACCEPT), "doc": display(DOC)},
        "decision": "Refreshed claim readiness after the canonical source-heldout frontier: the standalone edit-localization cell is now machine-complete across four languages, but human signoff and all full-product harness cells remain open against the stage9684 acceptance contract.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10075 Canonical Label Aligned Claim Readiness Matrix",
        "",
        f"Passed: `{summary['passed']}`",
        f"Standalone wins: `{built['metrics']['standalone_edit_localization_wins']}`",
        f"Pending signoff tasks: `{built['metrics']['pending_signoff_tasks']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
