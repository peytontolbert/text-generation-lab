#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10121
NAME = "stage10121_true_source_backed_root_bundle_signoff_workbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
WORKBOOK = OUT_DIR / "true_source_backed_root_bundle_signoff_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_ROOT_BUNDLE_SIGNOFF_WORKBOOK_STAGE10121.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REVIEW_MANIFEST = ROOT / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/true_source_backed_maintainer_root_bundle_review_packet_manifest.json"
SOURCE_BUNDLES = ROOT / "runs/local/artifacts/stage10119_true_source_backed_maintainer_root_bundle_preview/true_source_backed_maintainer_root_bundle_preview.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _gold_stub(bundle: dict[str, Any]) -> dict[str, Any]:
    perspective_gold_answers = []
    for row in bundle.get("perspective_rows") or []:
        prompt_contract = row.get("prompt_contract") if isinstance(row.get("prompt_contract"), dict) else {}
        perspective_gold_answers.append(
            {
                "perspective": row.get("perspective"),
                "abstention_option_required": bool(prompt_contract.get("abstention_option_required")),
                "candidate_paths": list(prompt_contract.get("candidate_paths") or []),
                "selected_tests": list(prompt_contract.get("selected_tests") or []),
                "visible_evidence_keys": list(prompt_contract.get("visible_evidence_keys") or []),
                "gold_answer_kind": None,
                "gold_answer_value": None,
                "reviewer_rationale": "",
            }
        )
    return {
        "bundle_id": bundle.get("bundle_id"),
        "language_family": bundle.get("language_family"),
        "repo_id": bundle.get("repo_id"),
        "status": "pending_human_review",
        "bundle_gold_ready_for_eval": False,
        "required_human_action": (
            "Record one human-maintainer gold answer for each perspective row, using abstention when the bounded visible evidence does not honestly justify a singleton answer."
        ),
        "perspective_gold_answers": perspective_gold_answers,
    }


def build_workbook() -> dict[str, Any]:
    review_manifest = load_json(REVIEW_MANIFEST)
    bundles = load_jsonl(SOURCE_BUNDLES)
    failures: list[str] = []
    if review_manifest.get("passed") is not True:
        failures.append("stage10120_not_passed")
    if len(bundles) != 8:
        failures.append("stage10119_bundles_not_8")

    bundle_by_id = {str(bundle.get("bundle_id") or ""): bundle for bundle in bundles}
    review_rows = review_manifest.get("rows") if isinstance(review_manifest.get("rows"), list) else []

    rows: list[dict[str, Any]] = []
    queue_position = 1
    for review_row in review_rows:
        bundle_id = str(review_row.get("bundle_id") or "")
        bundle = bundle_by_id.get(bundle_id)
        if bundle is None:
            failures.append(f"missing_source_bundle::{bundle_id}")
            continue
        paths = review_row.get("review_packet_paths") if isinstance(review_row.get("review_packet_paths"), dict) else {}
        packet_dir = ROOT / str(paths.get("packet_dir") or "")
        gold_path = packet_dir / "perspective_gold_adjudication.json"
        write_json(gold_path, _gold_stub(bundle))

        rows.append(
            {
                "queue_position": queue_position,
                "bundle_id": bundle_id,
                "language_family": review_row.get("language_family"),
                "repo_id": review_row.get("repo_id"),
                "task": "expert_maintainer_rubric_review",
                "review_file": paths.get("expert_maintainer_rubric_review"),
                "recommendation_draft": paths.get("rubric_recommendation_draft"),
                "required_human_action": "Review the root-bundle rubric and decide whether this bundle is a valid maintainer-grade evaluation unit.",
            }
        )
        queue_position += 1
        rows.append(
            {
                "queue_position": queue_position,
                "bundle_id": bundle_id,
                "language_family": review_row.get("language_family"),
                "repo_id": review_row.get("repo_id"),
                "task": "cell_specific_anti_cheat_review",
                "review_file": paths.get("anti_cheat_review_card"),
                "recommendation_draft": paths.get("anti_cheat_recommendation_draft"),
                "required_human_action": "Review the anti-cheat card and decide whether this bundle stays admissible for a future same-surface model comparison.",
            }
        )
        queue_position += 1
        rows.append(
            {
                "queue_position": queue_position,
                "bundle_id": bundle_id,
                "language_family": review_row.get("language_family"),
                "repo_id": review_row.get("repo_id"),
                "task": "perspective_gold_adjudication",
                "review_file": display(gold_path),
                "recommendation_draft": None,
                "required_human_action": "Record one gold answer and rationale for each perspective row before any bundle is eligible for scoring.",
            }
        )
        queue_position += 1

    metrics = {
        "signoff_tasks": len(rows),
        "rubric_tasks": sum(1 for row in rows if row["task"] == "expert_maintainer_rubric_review"),
        "anti_cheat_tasks": sum(1 for row in rows if row["task"] == "cell_specific_anti_cheat_review"),
        "perspective_gold_tasks": sum(1 for row in rows if row["task"] == "perspective_gold_adjudication"),
        "bundle_count": len(review_rows),
    }
    if metrics["signoff_tasks"] != 24:
        failures.append("signoff_tasks_not_24")
    if metrics["perspective_gold_tasks"] != 8:
        failures.append("perspective_gold_tasks_not_8")

    return {"passed": not failures, "failures": failures, "row_count": len(rows), "rows": rows, "metrics": metrics}


def main() -> None:
    built = build_workbook()
    write_json(WORKBOOK, built)
    next_step = (
        "Work the 24 bundle signoff tasks in order, then run a bundle adjudication compiler that only admits bundles with completed rubric, anti-cheat, and perspective-gold files."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"workbook": display(WORKBOOK), "doc": display(DOC)},
        "decision": (
            "Materialized the source-backed root-bundle signoff workbook and added perspective-gold adjudication stubs to every packet dir, "
            "so human review now has an explicit place to record bundle-level gold answers rather than only rubric and anti-cheat judgments."
        ),
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10121 True Source-Backed Root Bundle Signoff Workbook",
                "",
                f"Passed: `{summary['passed']}`",
                f"Signoff tasks: `{built['metrics']['signoff_tasks']}`",
                f"Perspective-gold tasks: `{built['metrics']['perspective_gold_tasks']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
