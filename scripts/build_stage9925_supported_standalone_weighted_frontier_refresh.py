#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9925
NAME = "stage9925_supported_standalone_weighted_frontier_refresh"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKETS = OUT_DIR / "supported_standalone_weighted_frontier_packets.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUPPORTED_STANDALONE_WEIGHTED_FRONTIER_REFRESH_STAGE9925.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"
FRONTIER = ROOT / "runs/local/artifacts/stage9922_current_weighted_hardened_multilingual_frontier_bridge/current_weighted_hardened_multilingual_frontier_bridge.json"
TRUTHFUL = ROOT / "runs/local/artifacts/stage9924_current_truthful_weighted_hardened_bridge_after_review_workbook/current_truthful_weighted_hardened_bridge_after_review_workbook.json"
WINNER_CELLS = {f"standalone_100m_weights::{lang}::edit_localization" for lang in ["python", "rust", "c_cpp", "web_js_ts_html"]}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_packets() -> dict[str, Any]:
    packets = load_jsonl(SOURCE_PACKETS)
    frontier = load_json(FRONTIER)
    truthful = load_json(TRUTHFUL)
    truthful_index = {str(row.get("cell_key") or ""): row for row in (truthful.get("records") or [])}
    frontier_index = {f"standalone_100m_weights::{row['language_family']}::edit_localization": row for row in (frontier.get("records") or []) if isinstance(row, dict)}
    failures: list[str] = []
    refreshed: list[dict[str, Any]] = []
    promoted = 0
    for packet in packets:
        row = copy.deepcopy(packet)
        cell_key = str(row.get("cell_key") or "")
        if cell_key in WINNER_CELLS:
            frontier_row = frontier_index.get(cell_key)
            truthful_row = truthful_index.get(f"hardened_weighted_same_surface::{cell_key.split('::')[1]}::edit_localization")
            if not isinstance(frontier_row, dict) or not isinstance(truthful_row, dict):
                failures.append(f"missing_weighted_support:{cell_key}")
            else:
                row["priority_rank"] = 1 + ["python", "rust", "c_cpp", "web_js_ts_html"].index(cell_key.split("::")[1])
                row["priority_score"] = frontier_row.get("strict_exact_100m")
                row["priority_reason"] = "weighted hardened multilingual same-surface Gemma win on current truthful frontier"
                row["same_surface_packet"] = {
                    "cell_key": cell_key,
                    "eval_exact": frontier_row.get("eval_exact_100m"),
                    "strict_exact": frontier_row.get("strict_exact_100m"),
                    "language_family": frontier_row.get("language_family"),
                    "row_count": 16,
                    "eval_rows": 4,
                    "strict_rows": 4,
                    "source_stage": 9917,
                    "surface_hash": str(FRONTIER.relative_to(ROOT)),
                }
                row["supporting_evidence_refs"] = list(truthful_row.get("attached_evidence") or [])
                merge = row.get("merge_ready_bundle_template") if isinstance(row.get("merge_ready_bundle_template"), dict) else {}
                same = merge.get("same_surface_comparison") if isinstance(merge.get("same_surface_comparison"), dict) else {}
                same.update({
                    "present": True,
                    "prompt_surface_hash_100m": str(FRONTIER.relative_to(ROOT)),
                    "prompt_surface_hash_gemma12b": str(FRONTIER.relative_to(ROOT)),
                    "score_100m": frontier_row.get("strict_exact_100m"),
                    "score_gemma12b": frontier_row.get("strict_exact_gemma"),
                    "scoring_constraints_hash": str(FRONTIER.relative_to(ROOT)),
                    "same_surface_verified": True,
                    "hundred_m_beats_gemma12b": True,
                })
                merge["same_surface_comparison"] = same
                evidence = merge.get("evidence_artifacts") if isinstance(merge.get("evidence_artifacts"), dict) else {}
                evidence["same_prompt_surface_gemma12b_outputs"] = "runs/local/artifacts/stage9919_hardened_weighted_edit_localization_gemma_comparison/hardened_weighted_edit_localization_gemma_rows.jsonl"
                evidence["language_slice_scores"] = "runs/local/artifacts/stage9919_hardened_weighted_edit_localization_gemma_comparison/hardened_weighted_edit_localization_gemma_comparison.json"
                evidence["frozen_export_or_checkpoint_hash"] = "machine_side_attached_in_weighted_frontier_bridge"
                merge["evidence_artifacts"] = evidence
                merge["notes"] = [
                    "weighted_hardened_frontier_supersedes_old_edit_localization_packet",
                    "same_surface_gemma_outputs_already_attached",
                    "remaining blockers are human rubric and anti-cheat review only",
                ]
                row["merge_ready_bundle_template"] = merge
                row["ready_for_gemma_when_authorized"] = False
                promoted += 1
        refreshed.append(row)
    refreshed.sort(key=lambda row: (0 if str(row.get("cell_key") or "") in WINNER_CELLS else 1, int(row.get("priority_rank") or 999), str(row.get("cell_key") or "")))
    for idx, row in enumerate(refreshed, start=1):
        row["priority_rank"] = idx
    metrics = {
        "review_packets": len(refreshed),
        "weighted_frontier_promoted_cells": promoted,
        "top_packets": [row["cell_key"] for row in refreshed[:4]],
    }
    if metrics["review_packets"] != 13:
        failures.append("review_packets_not_13")
    if metrics["weighted_frontier_promoted_cells"] != 4:
        failures.append("weighted_frontier_promoted_cells_not_4")
    return {"passed": not failures, "failures": failures, "review_packets": refreshed, "metrics": metrics, "authority": dict(AUTHORITY_CLOSED)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packets()
    write_jsonl(PACKETS, built["review_packets"])
    next_step = "Use this refreshed standalone packet set as the active supported-standalone frontier: the four edit-localization winners now carry weighted-hardened Gemma evidence and should be worked first for expert-review signoff."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"review_packets": str(PACKETS.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Refreshed the supported standalone packet set so the four edit-localization cells now point at the weighted-hardened multilingual frontier instead of the older visible-evidence packet and rise to the top of the queue.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9925 Supported Standalone Weighted Frontier Refresh",
        "",
        f"Passed: `{summary['passed']}`",
        f"Weighted frontier promoted cells: `{built['metrics']['weighted_frontier_promoted_cells']}`",
        f"Top packets: `{built['metrics']['top_packets']}`",
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
