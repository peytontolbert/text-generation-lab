#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10129
NAME = "stage10129_true_source_backed_multilingual_adjudication_frontier"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ADMITTED = OUT_DIR / "true_source_backed_multilingual_adjudication_admitted_manifest.json"
BLOCKED = OUT_DIR / "true_source_backed_multilingual_adjudication_blocked_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_MULTILINGUAL_ADJUDICATION_FRONTIER_STAGE10129.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

FRONTIER = ROOT / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier.json"
WORKBOOK = ROOT / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier_first_wave_signoff_workbook.json"
BASE_BUNDLES = ROOT / "runs/local/artifacts/stage10119_true_source_backed_maintainer_root_bundle_preview/true_source_backed_maintainer_root_bundle_preview.jsonl"
RUST_BUNDLES = ROOT / "runs/local/artifacts/stage10126_true_source_backed_rust_root_bundle_preview/true_source_backed_rust_root_bundle_preview.jsonl"


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


def _bundle_index(base_bundles_path: Path, rust_bundles_path: Path) -> dict[str, dict[str, Any]]:
    rows = load_jsonl(base_bundles_path) + load_jsonl(rust_bundles_path)
    return {str(row.get("bundle_id") or ""): row for row in rows}


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


def build_frontier(
    *,
    frontier_path: Path = FRONTIER,
    workbook_path: Path = WORKBOOK,
    base_bundles_path: Path = BASE_BUNDLES,
    rust_bundles_path: Path = RUST_BUNDLES,
    root: Path = ROOT,
) -> dict[str, Any]:
    frontier = load_json(frontier_path)
    workbook = load_json(workbook_path)
    failures: list[str] = []
    if frontier.get("passed") is not True:
        failures.append("stage10128_not_passed")
    if workbook.get("passed") is not True:
        failures.append("stage10128_workbook_not_passed")

    bundle_index = _bundle_index(base_bundles_path, rust_bundles_path)
    rows = workbook.get("rows") if isinstance(workbook.get("rows"), list) else []
    task_sets: dict[str, set[str]] = {}
    path_sets: dict[str, dict[str, str]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for row in rows:
        bundle_id = str(row.get("bundle_id") or "")
        task_sets.setdefault(bundle_id, set()).add(str(row.get("task") or ""))
        support = row.get("supporting_paths") if isinstance(row.get("supporting_paths"), dict) else {}
        path_sets[bundle_id] = support
        metadata.setdefault(
            bundle_id,
            {
                "language_family": row.get("language_family"),
                "repo_id": row.get("repo_id"),
                "wave_rank": row.get("wave_rank"),
                "priority_score": row.get("priority_score"),
            },
        )

    admitted_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()

    for bundle_id in (frontier.get("recommended_first_wave") or {}).get("bundle_ids", []):
        bundle = bundle_index.get(bundle_id)
        info = metadata.get(bundle_id, {})
        if bundle is None:
            reason_counts["missing_source_bundle"] += 1
            blocked_rows.append(
                {
                    "bundle_id": bundle_id,
                    "language_family": info.get("language_family"),
                    "repo_id": info.get("repo_id"),
                    "wave_rank": info.get("wave_rank"),
                    "blocked_reasons": ["missing_source_bundle"],
                }
            )
            continue

        support = path_sets.get(bundle_id, {})
        blocked_reasons: list[str] = []
        if task_sets.get(bundle_id) != {
            "expert_maintainer_rubric_review",
            "cell_specific_anti_cheat_review",
            "perspective_gold_adjudication",
        }:
            blocked_reasons.append("signoff_workbook_task_set_incomplete")

        rubric = load_json(_path(root, support.get("expert_maintainer_rubric_review"))) if support.get("expert_maintainer_rubric_review") else {}
        anti = load_json(_path(root, support.get("anti_cheat_review_card"))) if support.get("anti_cheat_review_card") else {}
        gold_ref = support.get("perspective_gold_adjudication")
        if not gold_ref and support.get("packet_dir"):
            gold_ref = str(Path(support["packet_dir"]) / "perspective_gold_adjudication.json")
        gold = load_json(_path(root, gold_ref)) if gold_ref else {}

        if not rubric:
            blocked_reasons.append("rubric_review_missing")
        else:
            blocked_reasons.extend(_require_completed_rubric(rubric))
        if not anti:
            blocked_reasons.append("anti_cheat_review_missing")
        else:
            blocked_reasons.extend(_require_completed_anti_cheat(anti))
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
                    "language_family": info.get("language_family"),
                    "repo_id": info.get("repo_id"),
                    "wave_rank": info.get("wave_rank"),
                    "priority_score": info.get("priority_score"),
                    "review_packet_paths": support,
                    "blocked_reasons": blocked_reasons,
                }
            )
            continue

        admitted_rows.append(
            {
                "bundle_id": bundle_id,
                "language_family": info.get("language_family"),
                "repo_id": info.get("repo_id"),
                "wave_rank": info.get("wave_rank"),
                "priority_score": info.get("priority_score"),
                "perspective_rows": bundle.get("perspective_rows"),
                "selected_tests": bundle.get("selected_tests"),
                "seed_paths": bundle.get("seed_paths"),
                "candidate_paths": bundle.get("candidate_paths"),
                "maintainer_visible_evidence": bundle.get("maintainer_visible_evidence"),
                "rubric_review": support.get("expert_maintainer_rubric_review"),
                "anti_cheat_review": support.get("anti_cheat_review_card"),
                "perspective_gold_adjudication": gold_ref,
            }
        )

    metrics = {
        "frontier_bundles_seen": len((frontier.get("recommended_first_wave") or {}).get("bundle_ids", [])),
        "admitted_bundles": len(admitted_rows),
        "blocked_bundles": len(blocked_rows),
        "admitted_language_counts": dict(sorted(Counter(row["language_family"] for row in admitted_rows).items())),
        "blocked_language_counts": dict(sorted(Counter(row["language_family"] for row in blocked_rows).items())),
        "blocked_reason_counts": dict(sorted(reason_counts.items())),
    }
    admitted_manifest = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "decision_boundary": "Only admit first-wave multilingual bundles with completed rubric, anti-cheat, and perspective-gold adjudication.",
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
    built = build_frontier()
    write_json(ADMITTED, built["admitted_manifest"])
    write_json(BLOCKED, built["blocked_manifest"])
    next_step = (
        "Complete the 24 first-wave multilingual signoff tasks, then rerun this compiler to open the first admitted four-language maintainer-grade scoring slice."
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
            "Compiled a strict four-language adjudication frontier from the merged multilingual first wave, so admitted vs blocked status is now tracked on the exact bundle slice intended for the first honest same-surface comparison."
        ),
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10129 True Source-Backed Multilingual Adjudication Frontier",
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
    print(json.dumps({"stage": STAGE, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
