#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10132
NAME = "stage10132_true_source_backed_first_wave_adjudication_readiness_ledger"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
LEDGER = OUT_DIR / "true_source_backed_first_wave_adjudication_readiness_ledger.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_FIRST_WAVE_ADJUDICATION_READINESS_LEDGER_STAGE10132.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

FRONTIER = ROOT / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier.json"
QUEUE = ROOT / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier_queue.jsonl"
WORKBOOK = ROOT / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier_first_wave_signoff_workbook.json"
BLOCKED = ROOT / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_blocked_manifest.json"
ADMITTED = ROOT / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_admitted_manifest.json"
SCORING = ROOT / "runs/local/artifacts/stage10130_true_source_backed_first_wave_scoring_contract/true_source_backed_first_wave_scoring_contract.json"
GOLD_SUPPORT = ROOT / "runs/local/artifacts/stage10131_true_source_backed_first_wave_gold_adjudication_support/true_source_backed_first_wave_gold_adjudication_support.json"


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


def _review_rows_by_bundle(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    by_bundle: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        bundle_id = str(row.get("bundle_id") or "")
        task = str(row.get("task") or "")
        by_bundle.setdefault(bundle_id, {})[task] = row
    return by_bundle


def _load_review_payload(path_str: str | None, root: Path) -> dict[str, Any]:
    if not path_str:
        return {}
    path = root / path_str
    return load_json(path)


def _score_bundle_row(
    bundle_id: str,
    queue_row: dict[str, Any],
    workbook_rows: dict[str, dict[str, Any]],
    blocked_rows: dict[str, dict[str, Any]],
    admitted_rows: dict[str, dict[str, Any]],
    root: Path,
) -> dict[str, Any]:
    rubric_row = workbook_rows[bundle_id]["expert_maintainer_rubric_review"]
    anti_row = workbook_rows[bundle_id]["cell_specific_anti_cheat_review"]
    gold_row = workbook_rows[bundle_id]["perspective_gold_adjudication"]

    rubric = _load_review_payload(rubric_row.get("review_file"), root)
    anti = _load_review_payload(anti_row.get("review_file"), root)
    gold = _load_review_payload(gold_row.get("review_file"), root)
    rubric_support = rubric_row.get("supporting_paths") if isinstance(rubric_row.get("supporting_paths"), dict) else {}
    anti_support = anti_row.get("supporting_paths") if isinstance(anti_row.get("supporting_paths"), dict) else {}
    gold_support = gold_row.get("supporting_paths") if isinstance(gold_row.get("supporting_paths"), dict) else {}
    packet_dir = root / str((gold_support.get("packet_dir") or rubric_support.get("packet_dir") or anti_support.get("packet_dir") or ""))

    answers = list(gold.get("perspective_gold_answers") or [])
    gold_answered = sum(
        1
        for answer in answers
        if answer.get("gold_answer_kind") and answer.get("gold_answer_value") not in (None, "") and answer.get("reviewer_rationale")
    )
    abstention_primary_guidance = (
        ((gold.get("recommended_answer_kind_schema") or {}).get("abstention_insufficient_evidence") or {}).get("recommended_primary_kind")
        == "abstain"
    )
    blocked = blocked_rows.get(bundle_id, {})
    admitted = admitted_rows.get(bundle_id)
    blocked_reasons = list(blocked.get("blocked_reasons") or [])
    blocked_heads = sorted({reason.split("::", 1)[0] for reason in blocked_reasons})

    rubric_complete = rubric.get("status") == "completed" and rubric.get("bundle_valid_for_eval") is True
    anti_complete = anti.get("status") == "completed" and anti.get("admissible_for_same_surface_comparison") is True
    gold_complete = gold.get("status") == "completed" and gold.get("bundle_gold_ready_for_eval") is True and gold_answered == len(answers) == 8

    return {
        "bundle_id": bundle_id,
        "language_family": queue_row.get("language_family"),
        "repo_id": queue_row.get("repo_id"),
        "queue_position": queue_row.get("queue_position"),
        "priority_tier": queue_row.get("priority_tier"),
        "priority_score": queue_row.get("priority_score"),
        "claim_priority_score": queue_row.get("claim_priority_score"),
        "shortcut_risk_score": queue_row.get("shortcut_risk_score"),
        "evidence_richness_score": queue_row.get("evidence_richness_score"),
        "candidate_paths_count": queue_row.get("candidate_paths_count"),
        "selected_tests_count": queue_row.get("selected_tests_count"),
        "source_route": queue_row.get("source_route"),
        "claim_reasons": list(queue_row.get("claim_reasons") or []),
        "shortcut_risk_reasons": list(queue_row.get("shortcut_risk_reasons") or []),
        "task_status": {
            "rubric_review_complete": rubric_complete,
            "anti_cheat_review_complete": anti_complete,
            "gold_adjudication_complete": gold_complete,
            "gold_answers_filled": gold_answered,
            "gold_answers_expected": len(answers),
        },
        "support_attached": {
            "rubric_recommendation_draft": bool(rubric_support.get("rubric_recommendation_draft"))
            and (root / str(rubric_support.get("rubric_recommendation_draft"))).exists(),
            "anti_cheat_recommendation_draft": bool(anti_support.get("anti_cheat_recommendation_draft"))
            and (root / str(anti_support.get("anti_cheat_recommendation_draft"))).exists(),
            "gold_recommendation_draft": (packet_dir / "perspective_gold_recommendation_draft.json").exists(),
            "abstention_primary_guidance_attached": abstention_primary_guidance,
        },
        "adjudication_state": {
            "blocked_now": bool(blocked),
            "admitted_now": admitted is not None,
            "scoreable_now": admitted is not None and rubric_complete and anti_complete and gold_complete,
            "blocked_reason_heads": blocked_heads,
            "blocked_reason_count": len(blocked_reasons),
        },
        "eval_hacking_watchlist": {
            "high_shortcut_risk": int(queue_row.get("shortcut_risk_score") or 0) >= 8,
            "few_candidate_paths": int(queue_row.get("candidate_paths_count") or 0) <= 2,
            "no_selected_tests": int(queue_row.get("selected_tests_count") or 0) == 0,
            "abstention_requires_honesty_review": "abstention_requires_honesty_review" in set(queue_row.get("shortcut_risk_reasons") or []),
        },
        "review_files": {
            "rubric_review": rubric_row.get("review_file"),
            "anti_cheat_review": anti_row.get("review_file"),
            "gold_adjudication": gold_row.get("review_file"),
        },
    }


def build_ledger(
    *,
    frontier_path: Path = FRONTIER,
    queue_path: Path = QUEUE,
    workbook_path: Path = WORKBOOK,
    blocked_path: Path = BLOCKED,
    admitted_path: Path = ADMITTED,
    scoring_path: Path = SCORING,
    gold_support_path: Path = GOLD_SUPPORT,
    root: Path = ROOT,
) -> dict[str, Any]:
    frontier = load_json(frontier_path)
    queue_rows = load_jsonl(queue_path)
    workbook = load_json(workbook_path)
    blocked = load_json(blocked_path)
    admitted = load_json(admitted_path)
    scoring = load_json(scoring_path)
    gold_support = load_json(gold_support_path)

    failures: list[str] = []
    if frontier.get("passed") is not True:
        failures.append("stage10128_frontier_not_passed")
    if workbook.get("passed") is not True:
        failures.append("stage10128_workbook_not_passed")
    if blocked.get("passed") is not True:
        failures.append("stage10129_blocked_manifest_not_passed")
    if admitted.get("passed") is not True:
        failures.append("stage10129_admitted_manifest_not_passed")
    if scoring.get("passed") is not True:
        failures.append("stage10130_not_passed")
    if gold_support.get("passed") is not True:
        failures.append("stage10131_not_passed")

    workbook_rows = _review_rows_by_bundle(list(workbook.get("rows") or []))
    blocked_rows = {str(row.get("bundle_id") or ""): row for row in (blocked.get("rows") or [])}
    admitted_rows = {str(row.get("bundle_id") or ""): row for row in (admitted.get("rows") or [])}
    queue_by_bundle = {str(row.get("bundle_id") or ""): row for row in queue_rows}

    bundle_ids = list(((frontier.get("recommended_first_wave") or {}).get("bundle_ids")) or [])
    ledger_rows: list[dict[str, Any]] = []
    for bundle_id in bundle_ids:
        if bundle_id not in queue_by_bundle:
            failures.append(f"missing_queue_bundle::{bundle_id}")
            continue
        if bundle_id not in workbook_rows:
            failures.append(f"missing_workbook_bundle::{bundle_id}")
            continue
        tasks = set(workbook_rows[bundle_id].keys())
        if tasks != {
            "expert_maintainer_rubric_review",
            "cell_specific_anti_cheat_review",
            "perspective_gold_adjudication",
        }:
            failures.append(f"workbook_task_set_mismatch::{bundle_id}")
            continue
        ledger_rows.append(_score_bundle_row(bundle_id, queue_by_bundle[bundle_id], workbook_rows, blocked_rows, admitted_rows, root))

    language_counts = Counter(str(row.get("language_family") or "") for row in ledger_rows)
    metrics = {
        "first_wave_bundle_count": len(ledger_rows),
        "language_bundle_counts": dict(sorted(language_counts.items())),
        "rubric_reviews_complete": sum(1 for row in ledger_rows if row["task_status"]["rubric_review_complete"]),
        "anti_cheat_reviews_complete": sum(1 for row in ledger_rows if row["task_status"]["anti_cheat_review_complete"]),
        "gold_adjudications_complete": sum(1 for row in ledger_rows if row["task_status"]["gold_adjudication_complete"]),
        "bundles_admitted_now": sum(1 for row in ledger_rows if row["adjudication_state"]["admitted_now"]),
        "bundles_scoreable_now": sum(1 for row in ledger_rows if row["adjudication_state"]["scoreable_now"]),
        "bundles_blocked_now": sum(1 for row in ledger_rows if row["adjudication_state"]["blocked_now"]),
        "bundles_with_all_support_attached": sum(
            1
            for row in ledger_rows
            if all(row["support_attached"].values())
        ),
        "high_shortcut_risk_bundles": sum(1 for row in ledger_rows if row["eval_hacking_watchlist"]["high_shortcut_risk"]),
        "bundles_without_selected_tests": sum(1 for row in ledger_rows if row["eval_hacking_watchlist"]["no_selected_tests"]),
        "bundles_with_few_candidate_paths": sum(1 for row in ledger_rows if row["eval_hacking_watchlist"]["few_candidate_paths"]),
        "gold_answers_completed_total": sum(row["task_status"]["gold_answers_filled"] for row in ledger_rows),
        "gold_answers_expected_total": sum(row["task_status"]["gold_answers_expected"] for row in ledger_rows),
    }
    if metrics["first_wave_bundle_count"] != 8:
        failures.append("first_wave_bundle_count_not_8")
    if metrics["language_bundle_counts"] != {
        "c_cpp": 2,
        "python": 2,
        "rust": 2,
        "web_js_ts_html": 2,
    }:
        failures.append("language_bundle_counts_not_balanced_2_each")
    if metrics["bundles_with_all_support_attached"] != 8:
        failures.append("bundles_with_all_support_attached_not_8")

    payload = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "decision": (
            "Collapse the first-wave multilingual maintainer review state into one strict readiness ledger so the repo can distinguish bundles that are merely scaffolded from bundles that are actually scoreable, while keeping eval-hacking pressure visible."
        ),
        "claim_boundary": {
            "maintainer_grade_same_surface_comparison_ready_now": metrics["bundles_scoreable_now"] == 8 and not failures,
            "machine_support_complete_but_human_signoff_open": metrics["bundles_with_all_support_attached"] == 8 and metrics["bundles_scoreable_now"] == 0,
            "scoreable_without_human_signoff": False,
        },
        "frontier_reason": ((frontier.get("recommended_first_wave") or {}).get("reason")),
        "rows": ledger_rows,
        "metrics": metrics,
        "failures": failures,
        "next_best_step": (
            "Use this ledger to clear the highest-risk blocked bundles first, complete rubric, anti-cheat, and gold signoff on all eight bundles, "
            "then rerun Stage10129 and Stage10130 before any 100M-versus-Gemma maintainer comparison."
        ),
    }
    return payload


def main() -> None:
    built = build_ledger()
    write_json(LEDGER, built)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "artifacts": {
            "ledger": display(LEDGER),
            "doc": display(DOC),
        },
        "decision": built["decision"],
        "next_best_step": built["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10132 True Source-Backed First-Wave Adjudication Readiness Ledger",
                "",
                f"Passed: `{summary['passed']}`",
                f"First-wave bundles: `{built['metrics']['first_wave_bundle_count']}`",
                f"Bundles scoreable now: `{built['metrics']['bundles_scoreable_now']}`",
                f"Bundles with all support attached: `{built['metrics']['bundles_with_all_support_attached']}`",
                "",
                summary["decision"],
                "",
                f"Next: {built['next_best_step']}",
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
