#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11197
NAME = "stage11197_clean_residual_successor_gemma_comparison"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "clean_residual_successor_gemma_comparison.json"
GEMMA_ROWS_JSONL = OUT_DIR / "gemma_rows.jsonl"
COMBINED_ROWS_JSONL = OUT_DIR / "combined_rows.jsonl"

BANK_ROWS = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
HUNDRED_AUDIT = ARTIFACTS / "stage11196_clean_residual_successor_100m_score/bounded_choice_eval_audit_clean_residual_successor_encoder_option_retrieval_verifier_conditioned.json"
HUNDRED_SUMMARY = ARTIFACTS / "stage11196_clean_residual_successor_100m_score/clean_residual_successor_100m_score.json"
MODEL_ID = "gemma3:12b"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_label(text: str, options: list[dict[str, Any]]) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    labels = [str(item.get("label") or "").strip() for item in options if str(item.get("label") or "").strip()]
    first_line = raw.splitlines()[0].strip()
    if first_line in labels:
        return first_line
    for pattern in [r"\*\*([A-Z])\*\*", r"\b([A-Z])\b(?=\s*[:.])", r"\banswer\s+is\s+([A-Z])\b", r"\boption\s+([A-Z])\b", r"^([A-Z])\b"]:
        for match in re.finditer(pattern, raw, flags=re.IGNORECASE):
            candidate = match.group(1).upper()
            if candidate in labels:
                return candidate
    lowered = raw.lower()
    for item in options:
        label = str(item.get("label") or "").strip()
        value = str(item.get("value") or "").strip().lower()
        if label and value and value in lowered:
            return label
    return first_line


def ollama_generate(prompt: str, model: str = MODEL_ID, seed: int = 0, temperature: float = 0.0) -> str:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False, "options": {"seed": seed, "temperature": temperature}}).encode("utf-8")
    request = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response") or "").strip()


def metric(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get(field), bool)]
    correct = sum(1 for row in scored if row.get(field) is True)
    return {"rows": len(rows), "scored_rows": len(scored), "correct": correct, "exact_accuracy": correct / len(scored) if scored else None}


def group(rows: list[dict[str, Any]], group_field: str, result_field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(group_field) or "unknown")].append(row)
    return {key: metric(bucket, result_field) for key, bucket in sorted(buckets.items())}


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("row_id") or "missing")


def cluster_metric(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[root_id(row)].append(row)
    solved = 0
    scored = 0
    for bucket in buckets.values():
        sub = [row for row in bucket if isinstance(row.get(field), bool)]
        if not sub:
            continue
        scored += 1
        solved += int(all(row.get(field) is True for row in sub))
    return {"clusters": len(buckets), "scored_clusters": scored, "solved_clusters": solved, "cluster_exact_accuracy": solved / scored if scored else None}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-existing-gemma", action="store_true")
    args = parser.parse_args()

    bank_rows = load_jsonl(BANK_ROWS)
    hundred_audit = load_json(HUNDRED_AUDIT)
    hundred_summary = load_json(HUNDRED_SUMMARY)
    hundred_cards = {str(row.get("row_id") or ""): row for row in (hundred_audit.get("row_cards") or [])}
    existing = {str(row.get("row_id") or ""): row for row in load_jsonl(GEMMA_ROWS_JSONL)} if args.reuse_existing_gemma else {}

    gemma_rows = []
    combined = []
    for row in bank_rows:
        row_id = str(row.get("row_id") or "")
        options = [item for item in row.get("opaque_options") or [] if isinstance(item, dict)]
        if row_id in existing:
            raw = str(existing[row_id].get("gemma12b_raw_output") or "")
        else:
            raw = ollama_generate(str(row.get("prompt_text") or row.get("input_text") or ""))
        pred = normalize_label(raw, options)
        correct = pred == str(row.get("target_text") or "")
        gemma = {"row_id": row_id, "gemma12b_raw_output": raw, "gemma12b_predicted_label": pred, "gemma12b_correct": correct}
        gemma_rows.append(gemma)
        h = hundred_cards.get(row_id, {})
        source = row.get("standalone_projection_source") or {}
        combined.append({
            "row_id": row_id,
            "root_id": root_id(row),
            "language_family": row.get("language_family"),
            "repo_family": row.get("repo_family"),
            "task_type": row.get("task_type"),
            "gold_value": source.get("gold_value"),
            "target_text": row.get("target_text"),
            "hundred_m_correct": h.get("constrained_choice_match"),
            "hundred_m_predicted_label": h.get("constrained_choice_top1_label"),
            "hundred_m_full_vocab_top1": h.get("full_vocab_top1_text"),
            **gemma,
        })
    write_jsonl(GEMMA_ROWS_JSONL, gemma_rows)
    write_jsonl(COMBINED_ROWS_JSONL, combined)

    wins_100m = wins_gemma = ties = 0
    for row in combined:
        a = row.get("hundred_m_correct") is True
        b = row.get("gemma12b_correct") is True
        if a and not b:
            wins_100m += 1
        elif b and not a:
            wins_gemma += 1
        else:
            ties += 1
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "clean_residual_successor_same_manifest_compared",
        "claim_scope": [
            "Diagnostic same-manifest comparison on the cleaned 10-row residual successor bank.",
            "Rows are replacement/clean residual candidates; report root-clustered metrics because one legacy root contributes two rows.",
            "This does not supersede the clean strict 22/22 canary; it measures unresolved residual evidence/verifier behavior.",
        ],
        "source_artifacts": {
            "bank_rows": rel(BANK_ROWS),
            "hundred_audit": rel(HUNDRED_AUDIT),
            "hundred_summary": rel(HUNDRED_SUMMARY),
        },
        "hundred_m": {
            "model_source": ((hundred_summary.get("runtime_initialization") or {}).get("weights_sha256")),
            "overall": metric(combined, "hundred_m_correct"),
            "clustered": cluster_metric(combined, "hundred_m_correct"),
            "by_language": group(combined, "language_family", "hundred_m_correct"),
            "by_task": group(combined, "task_type", "hundred_m_correct"),
            "by_gold_value": group(combined, "gold_value", "hundred_m_correct"),
        },
        "gemma12b": {
            "model_id": MODEL_ID,
            "overall": metric(combined, "gemma12b_correct"),
            "clustered": cluster_metric(combined, "gemma12b_correct"),
            "by_language": group(combined, "language_family", "gemma12b_correct"),
            "by_task": group(combined, "task_type", "gemma12b_correct"),
            "by_gold_value": group(combined, "gold_value", "gemma12b_correct"),
        },
        "paired_row_verdict": {"wins_100m": wins_100m, "wins_gemma": wins_gemma, "ties": ties},
        "rows": combined,
        "outputs": {"summary_json": rel(SUMMARY_JSON), "gemma_rows_jsonl": rel(GEMMA_ROWS_JSONL), "combined_rows_jsonl": rel(COMBINED_ROWS_JSONL)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
