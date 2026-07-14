#!/usr/bin/env python3
"""Compare routed 100M transition projections against Gemma on the same rows."""

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
STAGE = 11916
NAME = "stage11916_transition_projection_same_manifest_gemma_comparison"
OUT = ROOT / "runs/local/artifacts" / NAME
SUMMARY = OUT / "transition_projection_same_manifest_gemma_comparison.json"
ROWS_OUT = OUT / "transition_projection_same_manifest_gemma_rows.jsonl"
PROGRESS = OUT / "progress.json"

ROWS = ROOT / "runs/local/artifacts/stage11897_transition_record_projection_rows/transition_projection_rows.jsonl"
ROUTED_AUDIT = ROOT / "runs/local/artifacts/stage11914_routed_transition_semantic_head_audit/routed_transition_semantic_head_audit.json"
MODEL_ID = "gemma3:12b"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def prompt_surface_hash(rows: list[dict[str, Any]]) -> str:
    payload = [
        {
            "row_id": row.get("row_id"),
            "language_family": row.get("language_family"),
            "task_type": row.get("task_type"),
            "prompt_text": row.get("prompt_text"),
            "target_text": row.get("target_text"),
            "opaque_options": row.get("opaque_options") or [],
        }
        for row in sorted(rows, key=lambda item: str(item.get("row_id") or ""))
    ]
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def option_labels(row: dict[str, Any]) -> list[str]:
    return [str(opt.get("label") or "").strip() for opt in row.get("opaque_options") or [] if str(opt.get("label") or "").strip()]


def build_gemma_prompt(row: dict[str, Any]) -> str:
    labels = ", ".join(option_labels(row))
    prompt = str(row.get("prompt_text") or "")
    return (
        f"{prompt}\n\n"
        "You must answer with exactly one option label from the candidate list. "
        f"Allowed labels: {labels}. Do not explain."
    )


def ollama_generate(*, prompt: str, model: str = MODEL_ID, seed: int = 0, temperature: float = 0.0) -> str:
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"seed": seed, "temperature": temperature, "num_predict": 8},
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


def normalize_label(text: str, row: dict[str, Any]) -> str:
    raw = str(text or "").strip()
    labels = option_labels(row)
    if not raw or not labels:
        return ""
    first_line = raw.splitlines()[0].strip()
    if first_line in labels:
        return first_line
    patterns = [
        r"^\s*([A-Z])\s*$",
        r"\*\*([A-Z])\*\*",
        r"\banswer\s*(?:is|:)?\s*([A-Z])\b",
        r"\boption\s+([A-Z])\b",
        r"\b([A-Z])\b(?=\s*[:.)])",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, raw, flags=re.IGNORECASE):
            candidate = match.group(1).upper()
            if candidate in labels:
                return candidate
    lowered = raw.lower()
    for opt in row.get("opaque_options") or []:
        label = str(opt.get("label") or "").strip()
        value = str(opt.get("value") or "").strip()
        if label in labels and value and value.lower() in lowered:
            return label
    for token in re.findall(r"[A-Z]", first_line.upper()):
        if token in labels:
            return token
    return first_line


def metric(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get(field), bool)]
    correct = sum(1 for row in scored if row.get(field) is True)
    return {
        "rows": len(rows),
        "scored_rows": len(scored),
        "correct": correct,
        "accuracy": (correct / len(scored)) if scored else None,
    }


def group_metric(rows: list[dict[str, Any]], group_field: str, result_field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(group_field))].append(row)
    return {key: metric(bucket, result_field) for key, bucket in sorted(buckets.items())}


def verdicts(hundred: dict[str, Any], gemma: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    summary = {"100m": 0, "gemma": 0, "ties": 0, "unscored": 0}
    for key in sorted(set(hundred) | set(gemma)):
        h = (hundred.get(key) or {}).get("accuracy")
        g = (gemma.get(key) or {}).get("accuracy")
        if h is None or g is None:
            verdict = "unscored"
            summary["unscored"] += 1
        elif h > g:
            verdict = "100m_better"
            summary["100m"] += 1
        elif g > h:
            verdict = "gemma_better"
            summary["gemma"] += 1
        else:
            verdict = "tie"
            summary["ties"] += 1
        out[key] = {
            "hundred_m_accuracy": h,
            "gemma12b_accuracy": g,
            "delta": None if h is None or g is None else h - g,
            "verdict": verdict,
            "rows": (hundred.get(key) or gemma.get(key) or {}).get("rows"),
        }
    out["_summary"] = summary
    return out


def routed_100m_cards() -> dict[str, dict[str, Any]]:
    audit = read_json(ROUTED_AUDIT)
    card_path = ROOT / audit["outputs"]["audit_dir"] / "stage11912_semantic_head_only" / "bounded_choice_eval_audit_transition_projection__semantic_candidate_head.json"
    if not card_path.exists():
        # _write_bounded_choice_eval_audit sanitizes split names with underscores in some versions.
        candidates = sorted((ROOT / audit["outputs"]["audit_dir"] / "stage11912_semantic_head_only").glob("bounded_choice_eval_audit*transition*semantic*.json"))
        if not candidates:
            raise FileNotFoundError(f"missing routed transition row-card audit under {audit['outputs']['audit_dir']}")
        card_path = candidates[0]
    card = read_json(card_path)
    return {str(row.get("row_id")): row for row in card.get("row_cards") or []}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reuse-existing-gemma", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(ROWS)
    rows.sort(key=lambda row: str(row.get("row_id") or ""))
    if args.limit is not None:
        rows = rows[: args.limit]
    hundred_cards = routed_100m_cards()
    existing = {str(row.get("row_id") or ""): row for row in read_jsonl(ROWS_OUT)} if args.reuse_existing_gemma else {}

    comparison: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        row_id = str(row.get("row_id") or "")
        target = str(row.get("bounded_choice_target_label") or row.get("target_text") or "")
        hundred = hundred_cards.get(row_id) or {}
        raw = "[dry-run]"
        if args.reuse_existing_gemma and row_id in existing:
            raw = str(existing[row_id].get("gemma12b_raw_output") or "")
        elif not args.dry_run:
            raw = ollama_generate(prompt=build_gemma_prompt(row))
        pred = None if args.dry_run else normalize_label(raw, row)
        correct = None if args.dry_run else pred == target
        comparison.append(
            {
                "row_id": row_id,
                "language_family": row.get("language_family"),
                "task_type": row.get("task_type"),
                "root_id": row.get("root_id"),
                "target_text": target,
                "opaque_options": row.get("opaque_options") or [],
                "prompt_text": row.get("prompt_text"),
                "hundred_m_scorer": "routed:transition_projection=encoder_option_retrieval_semantic_candidate_head",
                "hundred_m_predicted_label": hundred.get("constrained_choice_top1_label"),
                "hundred_m_correct": hundred.get("constrained_choice_match"),
                "hundred_m_target_rank_full_vocab": hundred.get("target_rank_full_vocab"),
                "gemma12b_model": MODEL_ID,
                "gemma12b_prompt": build_gemma_prompt(row),
                "gemma12b_raw_output": raw,
                "gemma12b_predicted_label": pred,
                "gemma12b_correct": correct,
            }
        )
        write_json(PROGRESS, {"phase": "gemma" if not args.dry_run else "dry_run", "completed": idx, "total": len(rows), "updated_at_utc": now()})
        if idx % 25 == 0:
            write_jsonl(ROWS_OUT, comparison)
    write_jsonl(ROWS_OUT, comparison)

    by_language_100m = group_metric(comparison, "language_family", "hundred_m_correct")
    by_language_gemma = group_metric(comparison, "language_family", "gemma12b_correct")
    by_task_100m = group_metric(comparison, "task_type", "hundred_m_correct")
    by_task_gemma = group_metric(comparison, "task_type", "gemma12b_correct")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "dry_run": args.dry_run,
        "model_id": MODEL_ID,
        "rows": len(comparison),
        "prompt_surface_hash": prompt_surface_hash(rows),
        "hundred_m": {
            "runtime": rel(ROOT / "runs/local/artifacts/stage11912_transition_projection_semantic_head_only_probe/runtime_model/runtime_model_bundle.json"),
            "route": "transition_projection -> encoder_option_retrieval_semantic_candidate_head",
            "overall": metric(comparison, "hundred_m_correct"),
            "by_language": by_language_100m,
            "by_task": by_task_100m,
        },
        "gemma12b": {
            "executed": not args.dry_run,
            "overall": metric(comparison, "gemma12b_correct"),
            "by_language": by_language_gemma,
            "by_task": by_task_gemma,
        },
        "verdict_by_language": verdicts(by_language_100m, by_language_gemma),
        "verdict_by_task": verdicts(by_task_100m, by_task_gemma),
        "source_artifacts": {
            "rows": rel(ROWS),
            "routed_audit": rel(ROUTED_AUDIT),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "rows": rel(ROWS_OUT),
            "progress": rel(PROGRESS),
        },
        "claim_boundary": [
            "Same-manifest compact transition-projection comparison only.",
            "100M uses the routed transition semantic candidate scorer from Stage11914.",
            "This does not establish full-product patch repair or freeform generation.",
        ],
    }
    write_json(SUMMARY, summary)
    write_json(PROGRESS, {"phase": "complete", "completed": len(rows), "total": len(rows), "updated_at_utc": now()})
    print(json.dumps({"summary": rel(SUMMARY), "hundred_m": summary["hundred_m"]["overall"], "gemma12b": summary["gemma12b"]["overall"], "verdict_by_language": summary["verdict_by_language"]["_summary"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
