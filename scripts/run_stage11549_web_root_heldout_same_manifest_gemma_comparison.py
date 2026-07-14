#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11549
NAME = "stage11549_web_root_heldout_same_manifest_gemma_comparison"
OUT = ART / NAME
SUMMARY = OUT / "web_root_heldout_same_manifest_gemma_comparison.json"
GEMMA_ROWS_OUT = OUT / "web_root_heldout_gemma_rows.jsonl"

ROWS = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"
HUNDRED_SUMMARY = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_stage11507_score_audit.json"
MODEL_ID = "gemma3:12b"
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "127.0.0.1:11435").replace("http://", "").replace("https://", "").rstrip("/")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def ollama_generate(prompt: str) -> str:
    payload = json.dumps(
        {
            "model": MODEL_ID,
            "prompt": prompt,
            "stream": False,
            "options": {"seed": 0, "temperature": 0.0, "num_ctx": 4096},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"http://{OLLAMA_HOST}/api/generate",
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
    text_by_label = {str(item.get("label") or "").strip(): str(item.get("text") or "").strip() for item in options}
    first = raw.splitlines()[0].strip()
    first_clean = re.sub(r"[^A-Za-z0-9_ -].*$", "", first).strip()
    for candidate in (first, first_clean, first[:1].upper()):
        if candidate in labels:
            return candidate
    for pattern in (r"\*\*([A-Z])\*\*", r"\b([A-Z])\b(?=\s*[:.)])", r"\banswer\s+(?:is|:)\s*([A-Z])\b", r"\boption\s+([A-Z])\b"):
        for match in re.finditer(pattern, raw, flags=re.IGNORECASE):
            candidate = match.group(1).upper()
            if candidate in labels:
                return candidate
    lowered = raw.lower()
    for label, value in value_by_label.items():
        if value and value.lower() in lowered:
            return label
    for label, text_value in text_by_label.items():
        if text_value and text_value.lower() in lowered:
            return label
    return first


def prompt_for_gemma(row: dict[str, Any]) -> str:
    base = str(row.get("prompt_text") or row.get("input_text") or "")
    return (
        base
        + "\n\nYou are scoring a compact software-maintenance decision row."
        + "\nReturn exactly one option label from the listed choices."
        + "\nDo not explain. Use only the visible evidence."
    )


def metric(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get(field), bool)]
    correct = sum(1 for row in scored if row.get(field))
    return {"rows": len(rows), "scored_rows": len(scored), "correct": correct, "accuracy": correct / len(scored) if scored else None}


def group_metric(rows: list[dict[str, Any]], group: str, field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(group) or "unknown")].append(row)
    return {key: metric(bucket, field) for key, bucket in sorted(buckets.items())}


def row_result(row: dict[str, Any], raw: str) -> dict[str, Any]:
    pred = normalize_label(raw, list(row.get("opaque_options") or []))
    return {
        "row_id": row.get("row_id"),
        "root_id": row.get("root_id"),
        "repo_family": row.get("repo_family"),
        "task_type": row.get("task_type"),
        "language_family": row.get("language_family"),
        "target_text": row.get("target_text"),
        "semantic_target_value": row.get("semantic_target_value"),
        "gemma12b_raw_output": raw,
        "gemma12b_predicted_label": pred,
        "gemma12b_correct": pred == str(row.get("target_text") or ""),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(ROWS)
    hundred = read_json(HUNDRED_SUMMARY)
    existing = {str(row.get("row_id")): row for row in read_jsonl(GEMMA_ROWS_OUT)}
    result_rows = []
    for row in rows:
        row_id = str(row.get("row_id"))
        if row_id in existing and existing[row_id].get("gemma12b_raw_output"):
            raw = str(existing[row_id]["gemma12b_raw_output"])
        else:
            raw = ollama_generate(prompt_for_gemma(row))
        result_rows.append(row_result(row, raw))
        write_jsonl(GEMMA_ROWS_OUT, result_rows)

    hundred_metric = (hundred.get("hundred_m") or {})
    gemma_metric = metric(result_rows, "gemma12b_correct")
    comparison = {
        "hundred_m_correct": hundred_metric.get("correct"),
        "hundred_m_rows": hundred_metric.get("rows"),
        "hundred_m_accuracy": hundred_metric.get("accuracy"),
        "gemma12b_correct": gemma_metric.get("correct"),
        "gemma12b_rows": gemma_metric.get("rows"),
        "gemma12b_accuracy": gemma_metric.get("accuracy"),
        "delta_hundred_m_minus_gemma": None
        if hundred_metric.get("accuracy") is None or gemma_metric.get("accuracy") is None
        else hundred_metric["accuracy"] - gemma_metric["accuracy"],
    }
    gates = {
        "same_manifest_row_count": comparison["hundred_m_rows"] == comparison["gemma12b_rows"] == len(rows),
        "hundred_m_full_coverage": hundred_metric.get("coverage") == 1.0,
        "gemma_full_coverage": gemma_metric.get("scored_rows") == len(rows),
        "hundred_m_beats_gemma": (comparison["hundred_m_correct"] or 0) > (comparison["gemma12b_correct"] or 0),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": all(gates.values()),
        "decision": "web_root_heldout_same_manifest_100m_win" if all(gates.values()) else "web_root_heldout_same_manifest_no_100m_win_or_incomplete",
        "model_id": MODEL_ID,
        "ollama_host": OLLAMA_HOST,
        "comparison": comparison,
        "hundred_m": {key: value for key, value in hundred_metric.items() if key != "misses"},
        "gemma12b": gemma_metric,
        "by_task_gemma12b": group_metric(result_rows, "task_type", "gemma12b_correct"),
        "by_repo_family_gemma12b": group_metric(result_rows, "repo_family", "gemma12b_correct"),
        "gemma_misses": [row for row in result_rows if row.get("gemma12b_correct") is not True],
        "gates": gates,
        "claim_boundary": [
            "This is a Web/JS/TS/HTML root-heldout diagnostic, not repo-family-heldout broad Web generalization.",
            "The Ollama host is expected to be the GPU2-pinned service at 127.0.0.1:11435.",
            "This is compact bounded-choice scoring, not freeform repair or executable patch synthesis.",
        ],
        "source_artifacts": {"rows": rel(ROWS), "hundred_m_summary": rel(HUNDRED_SUMMARY)},
        "outputs": {"summary": rel(SUMMARY), "gemma_rows": rel(GEMMA_ROWS_OUT)},
    }
    write_json(SUMMARY, summary)
    write_jsonl(GEMMA_ROWS_OUT, result_rows)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"passed": summary["passed"], "comparison": comparison, "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
