#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10423
NAME = "stage10423_reviewed_multilingual_v27_same_manifest_gemma_comparison"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "reviewed_multilingual_v27_same_manifest_gemma_comparison.json"
ROWS_PATH = OUT_DIR / "reviewed_multilingual_v27_same_manifest_gemma_rows.jsonl"
MANIFEST = ROOT / "runs/local/artifacts/stage10421_reviewed_multilingual_v27_target100m_execution_request/reviewed_multilingual_v27_target100m_manifest.jsonl"
HUNDRED_M_EXECUTION = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/execution_result.json"
MODEL_ID = "gemma3:12b"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def prompt_surface_hash(rows: list[dict[str, Any]]) -> str:
    payload = []
    for row in sorted(rows, key=lambda item: str(item.get("row_id") or "")):
        payload.append(
            {
                "row_id": row.get("row_id"),
                "language_family": row.get("language_family"),
                "task_type": row.get("task_type"),
                "prompt_text": row.get("prompt_text"),
                "target_text": row.get("target_text"),
                "opaque_options": (((row.get("standalone_projection_source") or {}).get("opaque_options")) or []),
            }
        )
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def ollama_generate(*, prompt: str, model: str = MODEL_ID, seed: int = 0, temperature: float = 0.0) -> str:
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"seed": seed, "temperature": temperature},
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
    label_to_value = {
        str(item.get("label") or "").strip(): str(item.get("value") or "").strip()
        for item in options
        if str(item.get("label") or "").strip()
    }
    first_line = raw.splitlines()[0].strip()
    if first_line in labels:
        return first_line
    patterns = [
        r"\*\*([A-Z])\*\*",
        r"\b([A-Z])\b(?=\s*[:.])",
        r"\banswer\s+is\s+([A-Z])\b",
        r"\boption\s+([A-Z])\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, raw, flags=re.IGNORECASE):
            candidate = match.group(1).upper()
            if candidate in labels:
                return candidate
    lowered = raw.lower()
    for label, value in label_to_value.items():
        if value and value.lower() in lowered:
            return label
    for line in raw.splitlines():
        cleaned = line.strip()
        for label in labels:
            if cleaned == label:
                return label
            if cleaned.startswith(f"{label}.") or cleaned.startswith(f"{label}:") or cleaned.startswith(f"{label} "):
                return label
    return first_line


def metric_block(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get(field), bool)]
    correct = sum(1 for row in scored if row.get(field) is True)
    return {
        "rows": len(rows),
        "scored_rows": len(scored),
        "correct": correct,
        "exact_accuracy": (correct / len(scored)) if scored else None,
    }


def group_metrics(rows: list[dict[str, Any]], group_field: str, result_field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(group_field))].append(row)
    return {key: metric_block(bucket, result_field) for key, bucket in sorted(buckets.items())}


def verdicts(hundred: dict[str, Any], gemma: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(set(hundred) | set(gemma))
    out: dict[str, Any] = {}
    wins_100m = 0
    wins_gemma = 0
    ties = 0
    for key in keys:
        h = (hundred.get(key) or {}).get("exact_accuracy")
        g = (gemma.get(key) or {}).get("exact_accuracy")
        if h is None or g is None:
            verdict = "unscored"
        elif h > g:
            verdict = "100m_better"
            wins_100m += 1
        elif g > h:
            verdict = "gemma_better"
            wins_gemma += 1
        else:
            verdict = "tie"
            ties += 1
        out[key] = {
            "hundred_m_exact_accuracy": h,
            "gemma12b_exact_accuracy": g,
            "delta_hundred_m_minus_gemma": None if h is None or g is None else h - g,
            "verdict": verdict,
            "rows": (hundred.get(key) or gemma.get(key) or {}).get("rows"),
        }
    out["_summary"] = {"hundred_m": wins_100m, "gemma12b": wins_gemma, "ties": ties}
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_rows = [row for row in load_jsonl(MANIFEST) if str(row.get("split") or "") == "strict_eval"]
    manifest_rows.sort(key=lambda row: str(row.get("row_id") or ""))
    if args.limit is not None:
        manifest_rows = manifest_rows[: args.limit]

    execution = load_json(HUNDRED_M_EXECUTION)
    hundred_cards = {
        str(card["row_id"]): card
        for card in (((execution.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("row_cards") or [])
    }
    runtime_bundle = execution.get("runtime_model_bundle") or {}

    existing_rows = {}
    if args.reuse_existing and ROWS_PATH.exists():
        existing_rows = {str(row.get("row_id") or ""): row for row in load_jsonl(ROWS_PATH)}

    comparison_rows: list[dict[str, Any]] = []
    for row in manifest_rows:
        row_id = str(row.get("row_id") or "")
        prompt = str(row.get("prompt_text") or row.get("prompt") or "")
        options = [item for item in (((row.get("standalone_projection_source") or {}).get("opaque_options")) or []) if isinstance(item, dict)]
        raw = "[dry-run]"
        pred = None
        correct = None
        if args.reuse_existing and row_id in existing_rows:
            raw = str(existing_rows[row_id].get("gemma12b_raw_output") or "")
        elif not args.dry_run:
            raw = ollama_generate(prompt=prompt)
        if not args.dry_run:
            pred = normalize_label(raw, options)
            correct = pred == str(row.get("target_text") or "")
        hundred = hundred_cards[row_id]
        comparison_rows.append(
            {
                "row_id": row_id,
                "language_family": row.get("language_family"),
                "task_type": row.get("task_type"),
                "repo_family": row.get("repo_family"),
                "repo_id": row.get("repo_id"),
                "source_bundle_id": row.get("source_bundle_id"),
                "selected_test_anchor": bool(row.get("selected_test_anchor")),
                "verifier_anchor": bool(row.get("verifier_anchor")),
                "abstention_heavy": bool(row.get("abstention_heavy")),
                "source_heldout_admissible": bool(row.get("source_heldout_admissible")),
                "target_text": row.get("target_text"),
                "opaque_options": options,
                "prompt_text": prompt,
                "hundred_m_predicted_label": hundred.get("constrained_choice_top1_label"),
                "hundred_m_correct": hundred.get("constrained_choice_match"),
                "hundred_m_target_rank_full_vocab": hundred.get("target_rank_full_vocab"),
                "gemma12b_raw_output": raw,
                "gemma12b_predicted_label": pred,
                "gemma12b_correct": correct,
            }
        )

    write_jsonl(ROWS_PATH, comparison_rows)

    hundred_metrics = metric_block(comparison_rows, "hundred_m_correct")
    gemma_metrics = metric_block(comparison_rows, "gemma12b_correct")
    by_language_100m = group_metrics(comparison_rows, "language_family", "hundred_m_correct")
    by_language_gemma = group_metrics(comparison_rows, "language_family", "gemma12b_correct")
    by_task_100m = group_metrics(comparison_rows, "task_type", "hundred_m_correct")
    by_task_gemma = group_metrics(comparison_rows, "task_type", "gemma12b_correct")
    by_verifier_100m = group_metrics(comparison_rows, "verifier_anchor", "hundred_m_correct")
    by_verifier_gemma = group_metrics(comparison_rows, "verifier_anchor", "gemma12b_correct")
    by_selected_test_100m = group_metrics(comparison_rows, "selected_test_anchor", "hundred_m_correct")
    by_selected_test_gemma = group_metrics(comparison_rows, "selected_test_anchor", "gemma12b_correct")
    by_abstention_100m = group_metrics(comparison_rows, "abstention_heavy", "hundred_m_correct")
    by_abstention_gemma = group_metrics(comparison_rows, "abstention_heavy", "gemma12b_correct")

    misses = [
        {
            "row_id": row["row_id"],
            "language_family": row["language_family"],
            "task_type": row["task_type"],
            "target_text": row["target_text"],
            "hundred_m_predicted_label": row["hundred_m_predicted_label"],
            "gemma12b_predicted_label": row["gemma12b_predicted_label"],
            "gemma12b_raw_output": row["gemma12b_raw_output"],
        }
        for row in comparison_rows
        if row.get("gemma12b_correct") is False
    ]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "dry_run": args.dry_run,
        "model_id": MODEL_ID,
        "manifest": display(MANIFEST),
        "manifest_strict_rows": len(manifest_rows),
        "prompt_surface_hash": prompt_surface_hash(manifest_rows),
        "hundred_m_execution_result": display(HUNDRED_M_EXECUTION),
        "hundred_m_runtime_model_weights_sha256": runtime_bundle.get("weights_sha256"),
        "gemma_rows_path": display(ROWS_PATH),
        "hundred_m": hundred_metrics,
        "gemma12b": gemma_metrics,
        "delta_exact_accuracy": None
        if args.dry_run or hundred_metrics["exact_accuracy"] is None or gemma_metrics["exact_accuracy"] is None
        else hundred_metrics["exact_accuracy"] - gemma_metrics["exact_accuracy"],
        "by_language": {
            "hundred_m": by_language_100m,
            "gemma12b": by_language_gemma,
            "verdicts": verdicts(by_language_100m, by_language_gemma),
        },
        "by_task_type": {
            "hundred_m": by_task_100m,
            "gemma12b": by_task_gemma,
            "verdicts": verdicts(by_task_100m, by_task_gemma),
        },
        "by_verifier_anchor": {
            "hundred_m": by_verifier_100m,
            "gemma12b": by_verifier_gemma,
            "verdicts": verdicts(by_verifier_100m, by_verifier_gemma),
        },
        "by_selected_test_anchor": {
            "hundred_m": by_selected_test_100m,
            "gemma12b": by_selected_test_gemma,
            "verdicts": verdicts(by_selected_test_100m, by_selected_test_gemma),
        },
        "by_abstention_heavy": {
            "hundred_m": by_abstention_100m,
            "gemma12b": by_abstention_gemma,
            "verdicts": verdicts(by_abstention_100m, by_abstention_gemma),
        },
        "gemma_miss_rows": misses,
        "claim_scope": [
            "Same-manifest reviewed multilingual v2.7 strict_eval comparison only.",
            "100M uses the saved bounded-choice stage10422 runtime on the exact same strict rows.",
            "Gemma is evaluated by same-prompt opaque-label generation with deterministic decoding through Ollama.",
            "Stress-only rows remain excluded from this promotable strict comparison.",
        ],
    }
    write_json(SUMMARY_PATH, payload)
    print(display(SUMMARY_PATH))


if __name__ == "__main__":
    main()
