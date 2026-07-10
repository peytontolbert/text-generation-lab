#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9989
NAME = "stage9989_filtered_same_manifest_gemma_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
QUEUE = OUT_DIR / "filtered_same_manifest_gemma_queue.json"
PACKETS = OUT_DIR / "filtered_same_manifest_gemma_packets.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FILTERED_SAME_MANIFEST_GEMMA_QUEUE_STAGE9989.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9986_filtered_positive_replay_successor_request/edit_localization_manifest.jsonl"
OUTPUT = ROOT / "runs/local/artifacts/stage9990_filtered_same_manifest_gemma_execution/same_prompt_surface_gemma12b_outputs.json"


def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return getattr(module, symbol)


prompt_surface_hash = _load_symbol(
    "stage9989_runner",
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
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_queue() -> dict[str, Any]:
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    language_counts: dict[str, int] = {}
    split_counts: dict[str, int] = {}
    for row in rows:
        language = str(row.get("language_family") or "")
        split = str(row.get("split") or "")
        language_counts[language] = language_counts.get(language, 0) + 1
        split_counts[split] = split_counts.get(split, 0) + 1
    row_ids = [str(row.get("row_id") or "") for row in rows]
    if len(rows) != 117:
        failures.append("rows_not_117")
    if language_counts.get("python") != 22:
        failures.append("python_rows_not_22")
    if language_counts.get("c_cpp") != 29:
        failures.append("c_cpp_rows_not_29")
    packet = {
        "cell_key": "filtered_target100m::edit_localization::same_manifest_filtered_gemma12b",
        "language_family": "multilingual",
        "skill_area": "edit_localization",
        "review_packet_paths": {
            "same_prompt_surface_gemma12b_outputs": display(OUTPUT),
        },
        "same_surface_packet": {
            "row_count": len(rows),
            "row_ids": row_ids,
            "source_manifest": display(MANIFEST),
            "expected_python_rows": language_counts.get("python", 0),
            "expected_c_cpp_rows": language_counts.get("c_cpp", 0),
            "expected_web_rows": language_counts.get("web_js_ts_html", 0),
            "split_counts": split_counts,
            "surface_hash": prompt_surface_hash(rows),
        },
    }
    queue = {
        "queue_entries": [
            {
                "cell_key": packet["cell_key"],
                "language_family": "multilingual",
                "priority_rank": 1,
                "priority_reason": "same-manifest Gemma comparison for the filtered multilingual stage9987 frontier",
                "ready_for_gemma_when_authorized": True,
                "gemma_execution_authorized_now": False,
                "harness_execution_authorized_now": False,
                "remaining_blockers": ["explicit_gemma_execution_authorization"],
                "required_missing_evidence": [],
                "review_packet_paths": packet["review_packet_paths"],
                "same_surface_packet": packet["same_surface_packet"],
            }
        ]
    }
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            "rows": len(rows),
            "language_counts": dict(sorted(language_counts.items())),
            "split_counts": dict(sorted(split_counts.items())),
        },
        "queue": queue,
        "packet": packet,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_queue()
    write_json(QUEUE, built["queue"])
    write_jsonl(PACKETS, [built["packet"]])
    next_step = "Run the local Ollama Gemma comparator on this filtered same-manifest queue, then compare its rows directly against stage9987."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"queue": display(QUEUE), "packets": display(PACKETS), "doc": display(DOC)},
        "decision": "Materialized a same-manifest Gemma queue and packet set for the filtered stage9986 successor manifest so the stage9987 frontier can be compared fairly against Gemma3 12B.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9989 Filtered Same Manifest Gemma Queue",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows: `{built['metrics']['rows']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
