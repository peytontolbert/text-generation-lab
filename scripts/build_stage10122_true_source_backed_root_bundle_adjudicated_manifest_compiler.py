#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10122
NAME = "stage10122_true_source_backed_root_bundle_adjudicated_manifest_compiler"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ADMITTED = OUT_DIR / "true_source_backed_root_bundle_adjudicated_manifest.json"
BLOCKED = OUT_DIR / "true_source_backed_root_bundle_blocked_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_ROOT_BUNDLE_ADJUDICATED_MANIFEST_COMPILER_STAGE10122.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REVIEW_MANIFEST = ROOT / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/true_source_backed_maintainer_root_bundle_review_packet_manifest.json"
SIGNOFF_WORKBOOK = ROOT / "runs/local/artifacts/stage10121_true_source_backed_root_bundle_signoff_workbook/true_source_backed_root_bundle_signoff_workbook.json"
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


def _path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    return root / value


def _load_bundle_index(path: Path) -> dict[str, dict[str, Any]]:
    return {str(bundle.get("bundle_id") or ""): bundle for bundle in load_jsonl(path)}


def _require_completed_rubric(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if payload.get("status") != "completed":
        failures.append("rubric_status_not_completed")
    if payload.get("bundle_valid_for_eval") is not True:
        failures.append("rubric_bundle_not_marked_valid")
    if not payload.get("reviewer_id"):
        failures.append("rubric_missing_reviewer_id")
    if not payload.get("decision_rationale"):
        failures.append("rubric_missing_decision_rationale")
    return failures


def _require_completed_anti_cheat(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if payload.get("status") != "completed":
        failures.append("anti_cheat_status_not_completed")
    if payload.get("admissible_for_same_surface_comparison") is not True:
        failures.append("anti_cheat_not_marked_admissible")
    if not payload.get("reviewer_id"):
        failures.append("anti_cheat_missing_reviewer_id")
    if not payload.get("decision_rationale"):
        failures.append("anti_cheat_missing_decision_rationale")
    return failures


def _require_completed_gold(payload: dict[str, Any], expected_perspectives: int) -> list[str]:
    failures: list[str] = []
    answers = payload.get("perspective_gold_answers")
    if payload.get("status") != "completed":
        failures.append("gold_status_not_completed")
    if payload.get("bundle_gold_ready_for_eval") is not True:
        failures.append("gold_bundle_not_ready")
    if not payload.get("reviewer_id"):
        failures.append("gold_missing_reviewer_id")
    if not isinstance(answers, list):
        return failures + ["gold_answers_missing"]
    if len(answers) != expected_perspectives:
        failures.append("gold_answer_count_mismatch")
    for idx, answer in enumerate(answers):
        if not answer.get("gold_answer_kind"):
            failures.append(f"gold_answer_kind_missing::{idx}")
        if answer.get("gold_answer_value") in (None, ""):
            failures.append(f"gold_answer_value_missing::{idx}")
        if not answer.get("reviewer_rationale"):
            failures.append(f"gold_answer_rationale_missing::{idx}")
    return failures


def build_adjudicated_manifest(
    *,
    root: Path = ROOT,
    review_manifest_path: Path = REVIEW_MANIFEST,
    signoff_workbook_path: Path = SIGNOFF_WORKBOOK,
    source_bundles_path: Path = SOURCE_BUNDLES,
) -> dict[str, Any]:
    review_manifest = load_json(review_manifest_path)
    signoff_workbook = load_json(signoff_workbook_path)
    source_index = _load_bundle_index(source_bundles_path)
    failures: list[str] = []
    if review_manifest.get("passed") is not True:
        failures.append("stage10120_not_passed")
    if signoff_workbook.get("passed") is not True:
        failures.append("stage10121_not_passed")

    workbook_rows = signoff_workbook.get("rows") if isinstance(signoff_workbook.get("rows"), list) else []
    workbook_tasks_by_bundle: dict[str, set[str]] = {}
    for row in workbook_rows:
        bundle_id = str(row.get("bundle_id") or "")
        workbook_tasks_by_bundle.setdefault(bundle_id, set()).add(str(row.get("task") or ""))

    admitted_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    review_rows = review_manifest.get("rows") if isinstance(review_manifest.get("rows"), list) else []
    reason_counts: Counter[str] = Counter()

    for review_row in review_rows:
        bundle_id = str(review_row.get("bundle_id") or "")
        bundle = source_index.get(bundle_id)
        if bundle is None:
            reason_counts["missing_source_bundle"] += 1
            blocked_rows.append(
                {
                    "bundle_id": bundle_id,
                    "language_family": review_row.get("language_family"),
                    "repo_id": review_row.get("repo_id"),
                    "blocked_reasons": ["missing_source_bundle"],
                }
            )
            continue

        paths = review_row.get("review_packet_paths") if isinstance(review_row.get("review_packet_paths"), dict) else {}
        rubric_path = _path(root, paths.get("expert_maintainer_rubric_review"))
        anti_cheat_path = _path(root, paths.get("anti_cheat_review_card"))
        gold_path = _path(root, str(Path(paths.get("packet_dir", "")) / "perspective_gold_adjudication.json"))

        blocked_reasons: list[str] = []
        if workbook_tasks_by_bundle.get(bundle_id) != {
            "expert_maintainer_rubric_review",
            "cell_specific_anti_cheat_review",
            "perspective_gold_adjudication",
        }:
            blocked_reasons.append("signoff_workbook_task_set_incomplete")

        rubric = load_json(rubric_path) if rubric_path and rubric_path.exists() else {}
        anti_cheat = load_json(anti_cheat_path) if anti_cheat_path and anti_cheat_path.exists() else {}
        gold = load_json(gold_path) if gold_path and gold_path.exists() else {}

        if not rubric:
            blocked_reasons.append("rubric_review_missing")
        else:
            blocked_reasons.extend(_require_completed_rubric(rubric))
        if not anti_cheat:
            blocked_reasons.append("anti_cheat_review_missing")
        else:
            blocked_reasons.extend(_require_completed_anti_cheat(anti_cheat))
        if not gold:
            blocked_reasons.append("perspective_gold_missing")
        else:
            blocked_reasons.extend(_require_completed_gold(gold, expected_perspectives=len(bundle.get("perspective_rows") or [])))

        if blocked_reasons:
            for reason in blocked_reasons:
                reason_counts[reason] += 1
            blocked_rows.append(
                {
                    "bundle_id": bundle_id,
                    "language_family": review_row.get("language_family"),
                    "repo_id": review_row.get("repo_id"),
                    "blocked_reasons": blocked_reasons,
                    "review_packet_paths": paths,
                }
            )
            continue

        admitted_rows.append(
            {
                "bundle_id": bundle_id,
                "language_family": review_row.get("language_family"),
                "repo_id": review_row.get("repo_id"),
                "perspective_rows": bundle.get("perspective_rows"),
                "selected_tests": bundle.get("selected_tests"),
                "seed_paths": bundle.get("seed_paths"),
                "candidate_paths": bundle.get("candidate_paths"),
                "maintainer_visible_evidence": bundle.get("maintainer_visible_evidence"),
                "rubric_review": display(rubric_path) if rubric_path else None,
                "anti_cheat_review": display(anti_cheat_path) if anti_cheat_path else None,
                "perspective_gold_adjudication": display(gold_path) if gold_path else None,
            }
        )

    metrics = {
        "review_bundles_seen": len(review_rows),
        "admitted_bundles": len(admitted_rows),
        "blocked_bundles": len(blocked_rows),
        "blocked_reason_counts": dict(sorted(reason_counts.items())),
        "admitted_language_counts": dict(sorted(Counter(row["language_family"] for row in admitted_rows).items())),
        "blocked_language_counts": dict(sorted(Counter(row["language_family"] for row in blocked_rows).items())),
    }

    admitted_manifest = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "decision_boundary": "Only admit source-backed root bundles with completed rubric, completed anti-cheat, and completed perspective-gold adjudication.",
        "row_count": len(admitted_rows),
        "rows": admitted_rows,
        "metrics": metrics,
        "failures": failures,
    }
    blocked_manifest = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "decision_boundary": admitted_manifest["decision_boundary"],
        "row_count": len(blocked_rows),
        "rows": blocked_rows,
        "metrics": metrics,
        "failures": failures,
    }
    return {"passed": not failures, "failures": failures, "admitted_manifest": admitted_manifest, "blocked_manifest": blocked_manifest, "metrics": metrics}


def main() -> None:
    built = build_adjudicated_manifest()
    write_json(ADMITTED, built["admitted_manifest"])
    write_json(BLOCKED, built["blocked_manifest"])
    next_step = (
        "Complete human rubric, anti-cheat, and perspective-gold signoff for at least one root bundle, then rerun the adjudication compiler to open the first maintainer-grade scoring set."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "admitted_manifest": display(ADMITTED),
            "blocked_manifest": display(BLOCKED),
            "doc": display(DOC),
        },
        "decision": (
            "Compiled a strict admission gate for source-backed root bundles: every bundle is either admitted with all three human signoffs complete or blocked with explicit missing-review reasons."
        ),
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10122 True Source-Backed Root Bundle Adjudicated Manifest Compiler",
                "",
                f"Passed: `{summary['passed']}`",
                f"Admitted bundles: `{built['metrics']['admitted_bundles']}`",
                f"Blocked bundles: `{built['metrics']['blocked_bundles']}`",
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
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "metrics": built["metrics"],
                "failures": built["failures"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
