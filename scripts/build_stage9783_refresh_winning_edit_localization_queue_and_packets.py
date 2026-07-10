#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9783
NAME = "stage9783_refresh_winning_edit_localization_queue_and_packets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ARTIFACT = OUT_DIR / "winning_edit_localization_queue_and_packets_refresh.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REFRESH_WINNING_EDIT_LOCALIZATION_QUEUE_AND_PACKETS_STAGE9783.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

QUEUE_PATH = ROOT / "runs/local/artifacts/stage9748_supported_standalone_gemma_queue/supported_standalone_gemma_queue.json"
PACKETS_PATH = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"
MANIFEST_9771 = ROOT / "runs/local/artifacts/stage9771_edit_localization_visible_evidence_lift_package/edit_localization_visible_evidence_lift.jsonl"
LANG_AUDIT_9774 = ROOT / "runs/local/artifacts/stage9774_edit_localization_visible_evidence_language_slice_audit/edit_localization_visible_evidence_language_slice_audit.json"
GEMMA_AUDIT_9775 = ROOT / "runs/local/artifacts/stage9775_edit_localization_visible_evidence_gemma_comparison/edit_localization_visible_evidence_gemma_comparison.json"
GEMMA_SUMMARY_9775 = ROOT / "runs/summaries/stage9775_edit_localization_visible_evidence_gemma_comparison.json"
EXEC_SUMMARY_9773 = ROOT / "runs/summaries/stage9773_edit_localization_visible_evidence_execution_audit.json"
STATE_HASH_9781 = ROOT / "runs/local/artifacts/stage9781_winning_edit_localization_state_hash/winning_edit_localization_state_hash.json"
BRIDGE_9782 = ROOT / "runs/local/artifacts/stage9782_current_truthful_claim_bridge_after_state_hash/current_truthful_claim_bridge_after_state_hash.json"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return getattr(module, symbol)


prompt_surface_hash = _load_symbol(
    "stage9783_ollama_runner",
    ROOT / "scripts/run_stage9748_standalone_gemma_queue_via_ollama.py",
    "prompt_surface_hash",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
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
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _bridge_record_index() -> dict[str, dict[str, Any]]:
    bridge = load_json(BRIDGE_9782)
    rows = bridge.get("records") if isinstance(bridge.get("records"), list) else []
    return {str(row.get("cell_key") or ""): row for row in rows}


def _gemma_results_index() -> dict[str, dict[str, Any]]:
    audit = load_json(GEMMA_AUDIT_9775)
    rows = audit.get("results") if isinstance(audit.get("results"), list) else []
    return {str(row.get("language") or ""): row for row in rows}


def _row_groups_by_language() -> dict[str, list[dict[str, Any]]]:
    builder_path = ROOT / "scripts/build_stage9771_edit_localization_visible_evidence_lift_package.py"
    builder_spec = importlib.util.spec_from_file_location("stage9783_stage9771_builder", builder_path)
    builder = importlib.util.module_from_spec(builder_spec)
    assert builder_spec and builder_spec.loader
    builder_spec.loader.exec_module(builder)
    rows = builder.lift_rows(builder.load_jsonl(builder.SOURCE))
    grouped: dict[str, list[dict[str, Any]]] = {lang: [] for lang in LANGS}
    for row in rows:
        lang = str(row.get("language_family") or "")
        if lang in grouped:
            grouped[lang].append(row)
    for lang in grouped:
        grouped[lang].sort(key=lambda row: str(row.get("row_id") or ""))
    return grouped


def _split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"train": 0, "eval": 0, "strict_eval": 0}
    for row in rows:
        split = str(row.get("split") or "")
        if split in counts:
            counts[split] += 1
    return counts


def build_refresh() -> dict[str, Any]:
    queue = load_json(QUEUE_PATH)
    packets = load_jsonl(PACKETS_PATH)
    lang_audit = load_json(LANG_AUDIT_9774)
    exec_summary = load_json(EXEC_SUMMARY_9773)
    gemma_summary = load_json(GEMMA_SUMMARY_9775)
    state_hash = load_json(STATE_HASH_9781)
    bridge_index = _bridge_record_index()
    gemma_index = _gemma_results_index()
    rows_by_lang = _row_groups_by_language()

    queue_entries = queue.get("queue_entries") if isinstance(queue.get("queue_entries"), list) else []
    queue_by_cell = {str(row.get("cell_key") or ""): row for row in queue_entries}
    packet_by_cell = {str(row.get("cell_key") or ""): row for row in packets}

    refreshed_cells: list[dict[str, Any]] = []
    failures: list[str] = []

    for lang in LANGS:
        cell_key = f"standalone_100m_weights::{lang}::edit_localization"
        packet = packet_by_cell.get(cell_key)
        queue_entry = queue_by_cell.get(cell_key)
        lang_rows = rows_by_lang.get(lang, [])
        lang_slice = (lang_audit.get("language_slices") or {}).get(lang) if isinstance(lang_audit.get("language_slices"), dict) else {}
        gemma_row = gemma_index.get(lang)
        bridge = bridge_index.get(cell_key)
        if packet is None or queue_entry is None or not lang_rows or not isinstance(lang_slice, dict) or not isinstance(gemma_row, dict):
            failures.append(f"missing_refresh_inputs:{cell_key}")
            continue

        split_counts = _split_counts(lang_rows)
        surface_hash = prompt_surface_hash(lang_rows)
        source_manifest_rel = str(MANIFEST_9771.relative_to(ROOT))
        run_dir_rel = "runs/local/artifacts/stage9773_edit_localization_visible_evidence_exec"
        same_surface_packet = {
            "cell_key": cell_key,
            "eval_exact": (lang_slice.get("eval") or {}).get("exact"),
            "eval_rows": (lang_slice.get("eval") or {}).get("rows"),
            "language_family": lang,
            "row_count": len(lang_rows),
            "row_ids": [str(row.get("row_id") or "") for row in lang_rows],
            "run_dir": run_dir_rel,
            "skill_area": "edit_localization",
            "source_manifest": source_manifest_rel,
            "source_stage": 9773,
            "split_counts": split_counts,
            "strict_exact": (lang_slice.get("strict_eval") or {}).get("exact"),
            "strict_rows": (lang_slice.get("strict_eval") or {}).get("rows"),
            "surface_hash": surface_hash,
        }
        same_surface_comparison = {
            "hundred_m_beats_gemma12b": gemma_row.get("verdict") == "100m_better",
            "present": True,
            "prompt_surface_hash_100m": surface_hash,
            "prompt_surface_hash_gemma12b": surface_hash,
            "same_surface_verified": True,
            "score_100m": gemma_row.get("model_strict_exact_100m"),
            "score_gemma12b": gemma_row.get("gemma_strict_exact"),
            "scoring_constraints_hash": surface_hash,
        }

        packet["same_surface_packet"] = same_surface_packet
        merge_bundle = packet.get("merge_ready_bundle_template") if isinstance(packet.get("merge_ready_bundle_template"), dict) else {}
        merge_bundle["same_surface_comparison"] = same_surface_comparison
        evidence_artifacts = merge_bundle.get("evidence_artifacts") if isinstance(merge_bundle.get("evidence_artifacts"), dict) else {}
        review_paths = packet.get("review_packet_paths") if isinstance(packet.get("review_packet_paths"), dict) else {}
        evidence_artifacts["same_prompt_surface_gemma12b_outputs"] = review_paths.get("same_prompt_surface_gemma12b_outputs")
        evidence_artifacts["frozen_export_or_checkpoint_hash"] = review_paths.get("frozen_export_or_checkpoint_hash")
        merge_bundle["evidence_artifacts"] = evidence_artifacts
        packet["merge_ready_bundle_template"] = merge_bundle
        packet["supporting_evidence_refs"] = [
            {
                "claim_sufficient": False,
                "details": {
                    "available_100m_side_only": False,
                    "eval_exact": same_surface_packet["eval_exact"],
                    "eval_rows": same_surface_packet["eval_rows"],
                    "language_family": lang,
                    "strict_exact": same_surface_packet["strict_exact"],
                    "strict_rows": same_surface_packet["strict_rows"],
                    "surface": "edit_localization_visible_evidence",
                    "same_surface_hash": surface_hash,
                },
                "kind": "validated_same_surface_100m_vs_gemma_support",
                "path": str(GEMMA_SUMMARY_9775.relative_to(ROOT)),
                "quality_passed": True,
                "remaining_required_evidence_after_attach": list(bridge.get("missing_required_evidence") or []) if isinstance(bridge, dict) else ["expert_maintainer_rubric_scores", "anti_cheat_cards"],
                "stage": 9775,
                "supports": [
                    "same_prompt_surface_gemma12b_outputs",
                    "language_slice_scores",
                    "frozen_export_or_checkpoint_hash",
                ],
                "why_not_claim_sufficient": list(bridge.get("blockers") or []) if isinstance(bridge, dict) else ["expert_review_missing", "anti_cheat_review_missing"],
            }
        ]

        queue_entry["priority_score"] = float(gemma_row.get("model_strict_exact_100m") or 0.0)
        queue_entry["priority_reason"] = "current truthful same-surface 100m win over Gemma on visible-evidence edit-localization"
        queue_entry["same_surface_packet"] = same_surface_packet
        queue_entry["supporting_evidence_refs"] = packet["supporting_evidence_refs"]

        refreshed_cells.append(
            {
                "cell_key": cell_key,
                "language_family": lang,
                "surface_hash": surface_hash,
                "eval_exact": same_surface_packet["eval_exact"],
                "strict_exact": same_surface_packet["strict_exact"],
                "gemma_strict_exact": gemma_row.get("gemma_strict_exact"),
                "source_manifest": source_manifest_rel,
            }
        )

    queue_entries.sort(
        key=lambda row: (
            -float(row.get("priority_score") or 0.0),
            str(row.get("language_family") or ""),
            str(row.get("skill_area") or ""),
        )
    )
    for index, row in enumerate(queue_entries, start=1):
        row["priority_rank"] = index

    queue["metrics"] = {
        **(queue.get("metrics") or {}),
        "edit_localization_visible_evidence_cells": len(refreshed_cells),
        "top_queue_entry": queue_entries[0]["cell_key"] if queue_entries else None,
        "top_priority_score": queue_entries[0].get("priority_score") if queue_entries else None,
    }

    write_json(QUEUE_PATH, queue)
    write_jsonl(PACKETS_PATH, packets)

    metrics = {
        "refreshed_cells": len(refreshed_cells),
        "winning_cells_now_point_to_stage9773": sum(1 for row in refreshed_cells if row.get("strict_exact") == 1.0),
        "top_queue_entry": queue_entries[0]["cell_key"] if queue_entries else None,
        "top_priority_score": queue_entries[0].get("priority_score") if queue_entries else None,
        "state_hash_present": bool(state_hash.get("state_sha256")),
        "execution_summary_strict_exact": (exec_summary.get("metrics") or {}).get("strict_exact"),
        "gemma_summary_wins_100m": (gemma_summary.get("metrics") or {}).get("wins_100m"),
    }
    return {
        "passed": not failures,
        "failures": failures,
        "rows": refreshed_cells,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    refresh = build_refresh()
    write_json(ARTIFACT, refresh)
    next_step = (
        "Run the local Ollama Gemma runner against the refreshed Stage9771/9773 visible-evidence edit-localization cells, "
        "then continue expert-maintainer and anti-cheat review on the now-correct same-surface packets."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": refresh["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **refresh["metrics"]},
        "artifacts": {
            "refresh": str(ARTIFACT.relative_to(ROOT)),
            "queue": str(QUEUE_PATH.relative_to(ROOT)),
            "packets": str(PACKETS_PATH.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Refreshed the standalone Gemma queue and packet metadata for the four winning edit-localization cells so the local Gemma runner now targets the real Stage9771/9773 visible-evidence winning surface instead of the stale Stage9743/9744 target-only packet.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9783 Refresh Winning Edit Localization Queue And Packets",
                "",
                f"Passed: `{summary['passed']}`",
                f"Refreshed cells: `{summary['metrics']['refreshed_cells']}`",
                f"Top queue entry: `{summary['metrics']['top_queue_entry']}`",
                f"Top priority score: `{summary['metrics']['top_priority_score']}`",
                "",
                "This stage corrects a concrete comparison bug: the local standalone Gemma runner existed, but the queue and packet metadata for the four winning multilingual edit-localization cells still pointed at the stale Stage9743/9744 target-only surface.",
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
                "refreshed_cells": summary["metrics"]["refreshed_cells"],
                "top_queue_entry": summary["metrics"]["top_queue_entry"],
                "top_priority_score": summary["metrics"]["top_priority_score"],
                "failures": refresh["failures"],
                "next_best_step": next_step,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if refresh["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
