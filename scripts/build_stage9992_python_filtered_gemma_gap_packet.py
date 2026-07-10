#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9992
NAME = "stage9992_python_filtered_gemma_gap_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "python_filtered_gemma_gap_packet.json"
ROWS = OUT_DIR / "python_filtered_gemma_gap_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PYTHON_FILTERED_GEMMA_GAP_PACKET_STAGE9992.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9986_filtered_positive_replay_successor_request/edit_localization_manifest.jsonl"
HUNDRED_M = ROOT / "runs/local/artifacts/stage9987_filtered_positive_replay_target100m_probe/edit_localization_probe/row_field_logits.jsonl"
GEMMA = ROOT / "runs/local/artifacts/stage9990_filtered_same_manifest_gemma_execution/same_prompt_surface_gemma12b_outputs_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def build_packet() -> dict[str, Any]:
    manifest = {str(row.get("row_id") or ""): row for row in load_jsonl(MANIFEST)}
    hm = {str(row.get("row_id") or ""): row for row in load_jsonl(HUNDRED_M)}
    gm = {str(row.get("row_id") or ""): row for row in load_jsonl(GEMMA)}
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for row_id in sorted(set(manifest) & set(hm) & set(gm)):
        source = manifest[row_id]
        if str(source.get("language_family") or "") != "python":
            continue
        h = hm[row_id]
        g = gm[row_id]
        if bool(h.get("correct")) or not bool(g.get("correct")):
            continue
        rows.append(
            {
                "row_id": row_id,
                "split": source.get("split"),
                "recovery_reason": source.get("recovery_reason") or "anchor",
                "task_observation": (source.get("input_state") or {}).get("task_observation"),
                "visible_locality_evidence": (source.get("input_state") or {}).get("visible_locality_evidence"),
                "candidate_choices": (source.get("input_state") or {}).get("candidate_choices"),
                "hundred_m_pred": h.get("pred"),
                "gemma_pred": g.get("predicted_label"),
                "target": h.get("target"),
                "human_review_priority": "highest",
            }
        )
    metrics = {"rows": len(rows)}
    if metrics["rows"] != 2:
        failures.append("rows_not_2")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "rows": rows}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    PACKET.write_text(json.dumps({"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(ROWS, built["rows"])
    next_step = "Treat these two Python rows as the only remaining same-manifest blocker to a four-language filtered frontier win, and resolve them by expert review before any further training adjustment."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"packet": display(PACKET), "rows": display(ROWS), "doc": display(DOC)},
        "decision": "Materialized the two remaining Python filtered same-manifest Gemma-advantage rows so the final four-language blocker is explicit and reviewable.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9992 Python Filtered Gemma Gap Packet",
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
