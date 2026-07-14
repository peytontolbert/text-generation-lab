#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11402
NAME = "stage11402_rust_replacement_same_manifest_gemma_comparison"
OUT = ART / NAME
SUMMARY = OUT / "rust_replacement_same_manifest_gemma_comparison.json"
ROWS_OUT = OUT / "rust_replacement_gemma_rows.jsonl"

ROWS = ART / "stage11331_rust_web_gap_recovery_manifest/admitted_rust_strict_replacement_rows.jsonl"
HUNDRED = ART / "stage11333_rust_web_gap_current_runtime_score/rust_web_gap_current_runtime_score.json"
MODEL_ID = "gemma3:12b"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def metric(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get(field), bool)]
    correct = sum(1 for row in scored if row.get(field))
    return {"rows": len(rows), "scored_rows": len(scored), "correct": correct, "exact_accuracy": correct / len(scored) if scored else None}


def ollama_generate(prompt: str) -> str:
    payload = json.dumps(
        {
            "model": MODEL_ID,
            "prompt": prompt,
            "stream": False,
            "options": {"seed": 0, "temperature": 0.0},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response") or "").strip()


def normalize_label(text: str, options: list[dict[str, Any]]) -> str:
    raw = str(text).strip()
    if not raw:
        return ""
    labels = [str(item.get("label") or "").strip() for item in options if str(item.get("label") or "").strip()]
    value_by_label = {str(item.get("label") or "").strip(): str(item.get("value") or "").strip() for item in options}
    first = raw.splitlines()[0].strip()
    if first in labels:
        return first
    for pattern in (r"\*\*([A-Z])\*\*", r"\b([A-Z])\b(?=\s*[:.])", r"\banswer\s+is\s+([A-Z])\b", r"\boption\s+([A-Z])\b"):
        for match in re.finditer(pattern, raw, flags=re.IGNORECASE):
            candidate = match.group(1).upper()
            if candidate in labels:
                return candidate
    lowered = raw.lower()
    for label, value in value_by_label.items():
        if value and value.lower() in lowered:
            return label
    return first


def prompt_for_gemma(row: dict[str, Any]) -> str:
    base = str(row.get("prompt_text") or row.get("input_text") or "")
    return base + "\n\nReturn exactly one option label from the listed choices. Do not explain. Use only the visible evidence."


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(ROWS)
    hundred = read_json(HUNDRED)
    existing = {row.get("row_id"): row for row in read_jsonl(ROWS_OUT)}
    result_rows: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row["row_id"])
        if row_id in existing and existing[row_id].get("gemma12b_raw_output"):
            raw = str(existing[row_id]["gemma12b_raw_output"])
        else:
            raw = ollama_generate(prompt_for_gemma(row))
        pred = normalize_label(raw, list(row.get("opaque_options") or []))
        result_rows.append(
            {
                "row_id": row_id,
                "repo_family": row.get("repo_family"),
                "task_type": row.get("task_type"),
                "language_family": row.get("language_family"),
                "target_text": row.get("target_text"),
                "semantic_target_value": (row.get("standalone_projection_source") or {}).get("gold_value"),
                "gemma12b_raw_output": raw,
                "gemma12b_predicted_label": pred,
                "gemma12b_correct": pred == str(row.get("target_text") or ""),
            }
        )
        write_jsonl(ROWS_OUT, result_rows)

    hundred_metric = (hundred.get("product_metrics") or {}).get("rust_admitted_replacements", {})
    gemma_metric = metric(result_rows, "gemma12b_correct")
    delta = None
    if hundred_metric.get("exact_accuracy") is not None and gemma_metric.get("exact_accuracy") is not None:
        delta = hundred_metric["exact_accuracy"] - gemma_metric["exact_accuracy"]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "rust_replacement_same_manifest_gemma_comparison_complete",
        "claim_scope": "three reserved Rust replacement evidence-citation rows; diagnostic strict-candidate slice, not broad Rust claim",
        "model_id": MODEL_ID,
        "hundred_m_stage11200_product_scorer": hundred_metric,
        "gemma12b": gemma_metric,
        "delta_hundred_m_minus_gemma": delta,
        "gemma_rows": result_rows,
        "source_artifacts": {"rows": rel(ROWS), "hundred_m_score": rel(HUNDRED)},
        "outputs": {"summary": rel(SUMMARY), "gemma_rows": rel(ROWS_OUT)},
        "recommended_next_action": "Use this diagnostic to decide whether Rust replacements are a real 100M weakness; do not train on these reserved rows.",
    }
    write_json(SUMMARY, summary)
    write_jsonl(ROWS_OUT, result_rows)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"hundred_m": hundred_metric, "gemma12b": gemma_metric, "delta": delta}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
