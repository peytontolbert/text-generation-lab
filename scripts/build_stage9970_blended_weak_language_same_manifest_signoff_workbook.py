#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9970
NAME = "stage9970_blended_weak_language_same_manifest_signoff_workbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
WORKBOOK = OUT_DIR / "blended_weak_language_same_manifest_signoff_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BLENDED_WEAK_LANGUAGE_SAME_MANIFEST_SIGNOFF_WORKBOOK_STAGE9970.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REVIEW_MANIFEST = ROOT / "runs/local/artifacts/stage9969_blended_weak_language_same_manifest_review_packets/blended_weak_language_same_manifest_review_manifest.json"
REQUEST = ROOT / "runs/local/artifacts/stage9966_blended_weak_language_target100m_execution_request/surface_requests/edit_localization.json"
HANDOFF = ROOT / "runs/local/artifacts/stage9968_blended_weak_language_same_manifest_handoff_bundle/blended_weak_language_same_manifest_handoff_bundle.json"
AUDIT = ROOT / "runs/local/artifacts/stage9969_blended_weak_language_same_manifest_review_packets/blended_weak_language_same_manifest_review_audit.json"

LANG_PRIORITY = ["python", "c_cpp", "web_js_ts_html", "rust"]
TASK_ORDER = {
    "attach_same_manifest_outputs": 0,
    "expert_maintainer_rubric_review": 1,
    "cell_specific_anti_cheat_review": 2,
}


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
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_workbook() -> dict[str, Any]:
    review_manifest = load_json(REVIEW_MANIFEST)
    request = load_json(REQUEST)
    handoff = load_json(HANDOFF)
    audit = load_json(AUDIT)
    failures: list[str] = []

    review_rows = [row for row in (review_manifest.get("rows") or []) if isinstance(row, dict)]
    language_cards = {
        str(row.get("language_family") or ""): row
        for row in (audit.get("language_cards") or [])
        if isinstance(row, dict)
    }
    handoff_bundle = handoff.get("handoff_bundle") if isinstance(handoff.get("handoff_bundle"), dict) else {}
    hundred_m = handoff_bundle.get("hundred_m_execution") if isinstance(handoff_bundle.get("hundred_m_execution"), dict) else {}
    gemma = handoff_bundle.get("gemma_execution") if isinstance(handoff_bundle.get("gemma_execution"), dict) else {}

    if len(review_rows) != 4:
        failures.append("review_rows_not_4")

    rows: list[dict[str, Any]] = []
    for row in review_rows:
        language = str(row.get("language_family") or "")
        packet_paths = row.get("packet_paths") if isinstance(row.get("packet_paths"), dict) else {}
        card = language_cards.get(language, {})
        if language not in LANG_PRIORITY:
            failures.append(f"unexpected_language:{language}")
            continue

        same_manifest_task = {
            "cell_key": row.get("cell_key"),
            "language_family": language,
            "task": "attach_same_manifest_outputs",
            "queue_position": 0,
            "required_human_action": (
                "Attach the real Stage9965 100M outputs and Stage9971 Gemma outputs for this language to the live review packet before any signoff."
            ),
            "review_status": "pending_real_outputs",
            "compare_rows": row.get("compare_rows"),
            "expected_python_rows": (request.get("language_counts") or {}).get("python"),
            "expected_c_cpp_rows": (request.get("language_counts") or {}).get("c_cpp"),
            "expected_web_rows": (request.get("language_counts") or {}).get("web_js_ts_html"),
            "future_stage9965_output_dir": hundred_m.get("future_output_dir"),
            "future_stage9971_output_stub": gemma.get("future_output_stub"),
            "packet_dir": packet_paths.get("packet_dir"),
            "target_review_files": [
                packet_paths.get("expert_maintainer_rubric_review"),
                packet_paths.get("anti_cheat_review_card"),
            ],
            "supporting_evidence_paths": {
                "same_manifest_request": display(REQUEST),
                "same_manifest_handoff_bundle": display(HANDOFF),
                "same_manifest_review_audit": display(AUDIT),
            },
        }
        rubric_task = {
            "cell_key": row.get("cell_key"),
            "language_family": language,
            "task": "expert_maintainer_rubric_review",
            "queue_position": 0,
            "review_status": "pending_real_outputs_and_human_review",
            "required_human_action": (
                "After attaching real outputs, score only the 8 in-scope localization/evidence-grounding rubric lines and leave out-of-scope maintainer lines unclaimed."
            ),
            "compare_rows": row.get("compare_rows"),
            "in_scope_subskills": sorted({
                "avoids_hallucinated_symbols",
                "avoids_internal_tokens",
                "binds_symbols_correctly",
                "localizes_edit_scope",
                "produces_contentful_final_answer",
                "repairs_or_abstains_safely",
                "retrieves_source_evidence_when_needed",
                "understands_user_intent",
            }),
            "review_file": packet_paths.get("expert_maintainer_rubric_review"),
            "recommendation_draft": packet_paths.get("expert_maintainer_recommendation_draft"),
            "packet_dir": packet_paths.get("packet_dir"),
            "machine_scope_summary": {
                "surface_support_rows": card.get("rows"),
                "compare_rows": card.get("compare_rows"),
                "weak_language_priority_order": LANG_PRIORITY.index(language) + 1,
            },
        }
        anti_task = {
            "cell_key": row.get("cell_key"),
            "language_family": language,
            "task": "cell_specific_anti_cheat_review",
            "queue_position": 0,
            "review_status": "pending_real_outputs_and_human_review",
            "required_human_action": (
                "After attaching real outputs, confirm that the same-manifest outputs still respect the opaque-choice and no-shortcut contract already shown by the machine-side packet."
            ),
            "compare_rows": row.get("compare_rows"),
            "review_file": packet_paths.get("anti_cheat_review_card"),
            "recommendation_draft": packet_paths.get("anti_cheat_recommendation_draft"),
            "packet_dir": packet_paths.get("packet_dir"),
            "machine_contract_summary": {
                "unique_permutation_maps": card.get("unique_permutation_maps"),
                "all_gate_status_true": card.get("all_gate_status_true"),
                "no_raw_source_included": card.get("no_raw_source_included"),
                "no_raw_symbol_names_in_model_input": card.get("no_raw_symbol_names_in_model_input"),
            },
        }
        rows.extend([same_manifest_task, rubric_task, anti_task])

    rows.sort(key=lambda item: (LANG_PRIORITY.index(str(item.get("language_family") or "")), TASK_ORDER[str(item.get("task") or "")]))
    for index, row in enumerate(rows, start=1):
        row["queue_position"] = index

    metrics = {
        "signoff_tasks": len(rows),
        "attach_output_tasks": sum(1 for row in rows if row["task"] == "attach_same_manifest_outputs"),
        "rubric_tasks": sum(1 for row in rows if row["task"] == "expert_maintainer_rubric_review"),
        "anti_cheat_tasks": sum(1 for row in rows if row["task"] == "cell_specific_anti_cheat_review"),
        "unique_cells": len({str(row.get("cell_key") or "") for row in rows}),
        "top_queue_entry": rows[0]["cell_key"] + "::" + rows[0]["task"] if rows else None,
        "languages_in_priority_order": LANG_PRIORITY,
    }
    if metrics["signoff_tasks"] != 12:
        failures.append("signoff_tasks_not_12")
    if metrics["attach_output_tasks"] != 4:
        failures.append("attach_output_tasks_not_4")
    if metrics["rubric_tasks"] != 4:
        failures.append("rubric_tasks_not_4")
    if metrics["anti_cheat_tasks"] != 4:
        failures.append("anti_cheat_tasks_not_4")
    if metrics["unique_cells"] != 4:
        failures.append("unique_cells_not_4")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "rows": rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_workbook()
    WORKBOOK.write_text(
        json.dumps(
            {
                "stage": STAGE,
                "name": NAME,
                "passed": built["passed"],
                "metrics": built["metrics"],
                "rows": built["rows"],
                "authority": dict(AUTHORITY_CLOSED),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    next_step = (
        "Work the Stage9970 workbook in order: attach real same-manifest outputs first for python, c_cpp, web_js_ts_html, and rust, then complete rubric and anti-cheat signoff on those exact outputs before making any refreshed 100M-vs-Gemma claim."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "workbook": display(WORKBOOK),
            "doc": display(DOC),
        },
        "decision": "Materialized a live signoff workbook for the weak-language same-manifest path so the first real Stage9965 and Stage9971 outputs can be attached, reviewed, and judged on the exact packets already prepared in Stage9969.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9970 Blended Weak-Language Same-Manifest Signoff Workbook",
            "",
            f"Passed: `{summary['passed']}`",
            f"Signoff tasks: `{built['metrics']['signoff_tasks']}`",
            f"Attach-output tasks: `{built['metrics']['attach_output_tasks']}`",
            f"Unique cells: `{built['metrics']['unique_cells']}`",
            "",
            summary["decision"],
            "",
            f"Next: {next_step}",
            "",
        ]),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
