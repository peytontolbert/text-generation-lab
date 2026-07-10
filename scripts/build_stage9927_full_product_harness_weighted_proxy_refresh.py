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
STAGE = 9927
NAME = "stage9927_full_product_harness_weighted_proxy_refresh"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKETS = OUT_DIR / "full_product_harness_weighted_proxy_packets.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FULL_PRODUCT_HARNESS_WEIGHTED_PROXY_REFRESH_STAGE9927.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_PACKETS = ROOT / "runs/local/artifacts/stage9756_full_product_harness_review_packets/full_product_harness_review_packets.jsonl"
SOURCE_STANDALONE = ROOT / "runs/local/artifacts/stage9925_supported_standalone_weighted_frontier_refresh/supported_standalone_weighted_frontier_packets.jsonl"
WINNER_PROXIES = {f"standalone_100m_weights::{lang}::edit_localization" for lang in ["python", "rust", "c_cpp", "web_js_ts_html"]}


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
    standalone = {str(row.get("cell_key") or ""): row for row in load_jsonl(SOURCE_STANDALONE)}
    failures: list[str] = []
    refreshed = []
    promoted = 0
    for packet in packets:
        row = copy.deepcopy(packet)
        proxy = str(row.get("proxy_standalone_cell_key") or "")
        if proxy in WINNER_PROXIES:
            stand = standalone.get(proxy)
            if not isinstance(stand, dict):
                failures.append(f"missing_proxy_support:{proxy}")
            else:
                row["priority_bucket"] = "aligned_with_weighted_hardened_frontier_cell"
                row["proxy_standalone_priority_score"] = stand.get("priority_score")
                row["runner_status"] = "missing_harness_runner_surface_but_proxy_frontier_machine_complete"
                merge = row.get("merge_ready_bundle_template") if isinstance(row.get("merge_ready_bundle_template"), dict) else {}
                notes = list(merge.get("notes") or [])
                notes.append("proxy_standalone_weighted_frontier_machine_complete_but_harness_runner_still_missing")
                merge["notes"] = notes
                row["merge_ready_bundle_template"] = merge
                promoted += 1
        refreshed.append(row)
    metrics = {
        "review_packets": len(refreshed),
        "weighted_proxy_cells": promoted,
    }
    if metrics["review_packets"] != 36:
        failures.append("review_packets_not_36")
    if metrics["weighted_proxy_cells"] != 4:
        failures.append("weighted_proxy_cells_not_4")
    return {"passed": not failures, "failures": failures, "review_packets": refreshed, "metrics": metrics, "authority": dict(AUTHORITY_CLOSED)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packets()
    write_jsonl(PACKETS, built["review_packets"])
    next_step = "Use these refreshed harness packets to keep the four edit-localization harness cells aligned with the weighted-hardened standalone frontier while the missing harness runner remains the only machine-side blocker."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"review_packets": str(PACKETS.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Refreshed the harness packet set so the four edit-localization harness cells now explicitly proxy to the weighted-hardened standalone frontier and distinguish missing harness execution from missing standalone evidence.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9927 Full Product Harness Weighted Proxy Refresh",
        "",
        f"Passed: `{summary['passed']}`",
        f"Weighted proxy cells: `{built['metrics']['weighted_proxy_cells']}`",
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
