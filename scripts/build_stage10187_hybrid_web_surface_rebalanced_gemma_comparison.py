#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10187
NAME = "stage10187_hybrid_web_surface_rebalanced_gemma_comparison"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
MANIFEST = ROOT / "runs/local/artifacts/stage10184_hybrid_web_surface_rebalanced_target100m_execution_request/hybrid_web_surface_rebalanced_target100m_manifest.jsonl"
HUNDRED_M_AUDIT = ROOT / "runs/local/artifacts/stage10185_hybrid_web_surface_rebalanced_target100m_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
GEMMA_ROWS = OUT_DIR / "hybrid_web_surface_rebalanced_gemma12b_rows.jsonl"
COMPARISON = OUT_DIR / "hybrid_web_surface_rebalanced_gemma_comparison.json"
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
    option_labels = [str(item.get("label") or "").strip() for item in options if str(item.get("label") or "").strip()]
    option_pairs = [
        (str(item.get("label") or "").strip(), str(item.get("value") or "").strip())
        for item in options
        if str(item.get("label") or "").strip()
    ]
    first_line = raw.splitlines()[0].strip()
    if first_line in option_labels:
        return first_line
    patterns = [
        r"\*\*([A-Z])\*\*",
        r"\b([A-Z])\b(?=\s*[:.])",
        r"\banswer\s+is\s+([A-Z])\b",
        r"\btherefore[, ]+the answer is\s+([A-Z])\b",
        r"\boption\s+([A-Z])\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, raw, flags=re.IGNORECASE):
            candidate = match.group(1).upper()
            if candidate in option_labels:
                return candidate
    lowered = raw.lower()
    for label, value in option_pairs:
        if value and value.lower() in lowered:
            return label
    for line in raw.splitlines():
        line = line.strip()
        for label in option_labels:
            if line == label:
                return label
            if line.startswith(f"{label}.") or line.startswith(f"{label}:") or line.startswith(f"{label} "):
                return label
    return first_line


def metric_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get("correct"), bool)]
    correct = sum(1 for row in scored if row.get("correct") is True)
    return {
        "rows": len(rows),
        "scored_rows": len(scored),
        "correct": correct,
        "exact_accuracy": (correct / len(scored)) if scored else None,
    }


def per_language(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get("language_family") or "unknown")].append(row)
    return {lang: metric_block(bucket) for lang, bucket in sorted(buckets.items())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--reuse-existing", action="store_true")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)

    manifest_rows = [row for row in load_jsonl(MANIFEST) if str(row.get("split") or "") == "strict_eval"]
    if args.limit is not None:
        manifest_rows = manifest_rows[: args.limit]
    manifest_by_id = {str(row.get("row_id") or ""): row for row in manifest_rows}
    hundred_m_audit_exists = HUNDRED_M_AUDIT.exists()
    hundred_m_audit = load_json(HUNDRED_M_AUDIT) if hundred_m_audit_exists else {}
    hundred_m_rows = {str(row["row_id"]): row for row in hundred_m_audit.get("row_cards") or []}

    gemma_rows: list[dict[str, Any]] = []
    if args.reuse_existing and GEMMA_ROWS.exists():
        existing = {str(row.get("row_id") or ""): row for row in load_jsonl(GEMMA_ROWS)}
        for row_id, row in manifest_by_id.items():
            prior = existing.get(row_id, {})
            raw = str(prior.get("raw_output") or "")
            options = [
                item
                for item in (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
                if isinstance(item, dict)
            ]
            predicted = None if args.dry_run else normalize_label(raw, options)
            expected = str(row.get("target_text") or "")
            gemma_rows.append(
                {
                    "row_id": row_id,
                    "language_family": row.get("language_family"),
                    "perspective": row.get("perspective"),
                    "expected_label": expected,
                    "predicted_label": predicted,
                    "raw_output": raw,
                    "correct": None if args.dry_run else (predicted == expected),
                }
            )
    else:
        for row in manifest_rows:
            row_id = str(row.get("row_id") or "")
            raw = "[dry-run]" if args.dry_run else ollama_generate(prompt=str(row.get("prompt_text") or row.get("prompt") or ""))
            options = [
                item
                for item in (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
                if isinstance(item, dict)
            ]
            predicted = None if args.dry_run else normalize_label(raw, options)
            expected = str(row.get("target_text") or "")
            gemma_rows.append(
                {
                    "row_id": row_id,
                    "language_family": row.get("language_family"),
                    "perspective": row.get("perspective"),
                    "expected_label": expected,
                    "predicted_label": predicted,
                    "raw_output": raw,
                    "correct": None if args.dry_run else (predicted == expected),
                }
            )
        write_jsonl(GEMMA_ROWS, gemma_rows)

    comparison_rows: list[dict[str, Any]] = []
    for gemma_row in gemma_rows:
        row_id = str(gemma_row.get("row_id") or "")
        row = manifest_by_id[row_id]
        hundred_m = hundred_m_rows.get(row_id, {})
        comparison_rows.append(
            {
                "row_id": row_id,
                "language_family": row.get("language_family"),
                "perspective": row.get("perspective"),
                "expected_label": str(row.get("target_text") or ""),
                "hundred_m_predicted_label": hundred_m.get("constrained_choice_top1_label"),
                "hundred_m_correct": hundred_m.get("constrained_choice_match"),
                "gemma12b_predicted_label": gemma_row.get("predicted_label"),
                "gemma12b_correct": gemma_row.get("correct"),
            }
        )

    write_jsonl(GEMMA_ROWS, gemma_rows)

    hundred_m_comp_rows = [
        {
            "row_id": row["row_id"],
            "language_family": next((m.get("language_family") for m in manifest_rows if str(m.get("row_id")) == str(row["row_id"])), None),
            "perspective": next((m.get("perspective") for m in manifest_rows if str(m.get("row_id")) == str(row["row_id"])), None),
            "correct": row.get("constrained_choice_match"),
        }
        for row in hundred_m_audit.get("row_cards") or []
        if any(str(m.get("row_id")) == str(row.get("row_id")) for m in manifest_rows)
    ]

    hundred_m_metrics = metric_block(hundred_m_comp_rows)
    gemma_metrics = metric_block(gemma_rows)
    hundred_lang = per_language(hundred_m_comp_rows)
    gemma_lang = per_language(gemma_rows)

    language_verdicts = {}
    hundred_wins = 0
    gemma_wins = 0
    ties = 0
    for lang in sorted(set(hundred_lang) | set(gemma_lang)):
        a = hundred_lang.get(lang, {}).get("exact_accuracy")
        b = gemma_lang.get(lang, {}).get("exact_accuracy")
        if a is None or b is None:
            verdict = "unscored"
        elif a > b:
            verdict = "100m_better"
            hundred_wins += 1
        elif b > a:
            verdict = "gemma_better"
            gemma_wins += 1
        else:
            verdict = "tie"
            ties += 1
        language_verdicts[lang] = {
            "hundred_m_exact_accuracy": a,
            "gemma12b_exact_accuracy": b,
            "verdict": verdict,
            "rows": hundred_lang.get(lang, {}).get("rows") or gemma_lang.get(lang, {}).get("rows"),
        }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "dry_run": args.dry_run,
        "pending_hundred_m_audit": not hundred_m_audit_exists,
        "model_id": MODEL_ID,
        "manifest": display(MANIFEST),
        "hundred_m_audit": display(HUNDRED_M_AUDIT),
        "gemma_rows_path": display(GEMMA_ROWS),
        "rows": len(manifest_rows),
        "hundred_m": hundred_m_metrics,
        "gemma12b": gemma_metrics,
        "hundred_m_by_language": hundred_lang,
        "gemma12b_by_language": gemma_lang,
        "language_verdicts": language_verdicts,
        "wins": {"hundred_m": hundred_wins, "gemma12b": gemma_wins, "ties": ties},
        "delta_exact_accuracy": None if args.dry_run else ((hundred_m_metrics["exact_accuracy"] or 0.0) - (gemma_metrics["exact_accuracy"] or 0.0)),
        "comparison_rows": comparison_rows,
        "claim_scope": "same-manifest compact bounded maintainer projection using the rebalanced stage10185 100M outputs against live gemma3:12b same-prompt outputs; diagnostic standalone surface only, not full maintainer leaderboard",
    }
    COMPARISON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(
        json.dumps(
            {
                "stage": STAGE,
                "stage_name": NAME,
                "passed": True,
                "comparison": display(COMPARISON),
                "gemma_rows": display(GEMMA_ROWS),
                "rows": len(manifest_rows),
                "dry_run": args.dry_run,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": True,
                "comparison": display(COMPARISON),
                "rows": len(manifest_rows),
                "dry_run": args.dry_run,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
