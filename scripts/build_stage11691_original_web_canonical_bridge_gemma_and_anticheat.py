#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11691_original_web_canonical_bridge_gemma_and_anticheat"
OUT = ART / NAME
SUMMARY = OUT / "original_web_canonical_bridge_gemma_and_anticheat.json"
GEMMA_ROWS = OUT / "original_web_canonical_bridge_gemma_rows.jsonl"

ROWS = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridged_rows.jsonl"
BRIDGE_AUDIT = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridge_audit.json"
MODEL_ID = os.environ.get("STAGE11691_GEMMA_MODEL", "gemma3:12b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "127.0.0.1:11435").replace("http://", "").replace("https://", "").rstrip("/")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_lineage_key") or row.get("root_id") or row.get("row_id"))


def labels(row: dict[str, Any]) -> list[str]:
    return [str(opt.get("label") or "").strip() for opt in row.get("opaque_options", []) if str(opt.get("label") or "").strip()]


def target_label(row: dict[str, Any]) -> str:
    return str(row.get("bounded_choice_target_label") or row.get("target_text") or (row.get("target") or {}).get("bounded_choice_target_label") or "").strip()


def ollama_generate(prompt: str) -> str:
    payload = json.dumps(
        {
            "model": MODEL_ID,
            "prompt": prompt,
            "stream": False,
            "options": {"seed": 0, "temperature": 0.0, "num_ctx": 8192},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"http://{OLLAMA_HOST}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=360) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response") or "").strip()


def normalize_label(text: str, row: dict[str, Any]) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    options = [opt for opt in row.get("opaque_options", []) if isinstance(opt, dict)]
    option_labels = labels(row)
    first = raw.splitlines()[0].strip()
    first_clean = re.sub(r"[^A-Za-z0-9_ -].*$", "", first).strip()
    for candidate in (first, first_clean, first[:1].upper()):
        if candidate in option_labels:
            return candidate
    patterns = (
        r"\*\*([A-Z])\*\*",
        r"\b([A-Z])\b(?=\s*[:.)])",
        r"\banswer\s+(?:is|:)\s*([A-Z])\b",
        r"\boption\s+([A-Z])\b",
        r"\bcandidate\s+([A-Z])\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, raw, flags=re.IGNORECASE):
            candidate = match.group(1).upper()
            if candidate in option_labels:
                return candidate
    lowered = raw.lower()
    for opt in options:
        label = str(opt.get("label") or "").strip()
        value = str(opt.get("value") or "").strip().lower()
        text_value = str(opt.get("text") or "").strip().lower()
        if label and value and value in lowered:
            return label
        if label and text_value and text_value in lowered:
            return label
    return first


def prompt_for_gemma(row: dict[str, Any]) -> str:
    base = str(row.get("prompt_text") or row.get("input_text") or "")
    return (
        base
        + "\n\nYou are scoring a compact software-maintenance decision row."
        + "\nReturn exactly one option label from the listed CANDIDATES."
        + "\nDo not explain. Use only the visible evidence and candidate fields."
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
    pred = normalize_label(raw, row)
    target = target_label(row)
    return {
        "row_id": row.get("row_id"),
        "root_id": row.get("root_id"),
        "root_lineage_key": row.get("root_lineage_key"),
        "repo_id": row.get("repo_id"),
        "repo_family": row.get("repo_family"),
        "task_type": row.get("task_type"),
        "language_family": row.get("language_family"),
        "target_text": target,
        "semantic_target_value": row.get("semantic_target_value"),
        "gemma12b_raw_output": raw,
        "gemma12b_predicted_label": pred,
        "gemma12b_correct": pred == target,
    }


def anticheat(rows: list[dict[str, Any]]) -> dict[str, Any]:
    root_counts = Counter(root_key(row) for row in rows)
    label_counts = Counter(target_label(row) for row in rows)
    task_counts = Counter(str(row.get("task_type") or "unknown") for row in rows)
    prompt_label_leaks = []
    semantic_value_leaks = []
    singleton_rows = []
    missing_shuffle = []
    for row in rows:
        opts = [opt for opt in row.get("opaque_options", []) if isinstance(opt, dict)]
        target = target_label(row)
        prompt = str(row.get("prompt_text") or row.get("input_text") or "")
        before = prompt.split("CANDIDATES", 1)[0]
        if len(opts) <= 1:
            singleton_rows.append(row.get("row_id"))
        if re.search(rf"\b(option|candidate)\s+{re.escape(target)}\b", before, flags=re.IGNORECASE):
            prompt_label_leaks.append(row.get("row_id"))
        anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        if anti.get("deterministic_option_shuffle") is not True:
            missing_shuffle.append(row.get("row_id"))
        target_opt = next((opt for opt in opts if str(opt.get("label")) == target), None)
        if target_opt is not None:
            obj = target_opt.get("canonical_candidate_object") if isinstance(target_opt.get("canonical_candidate_object"), dict) else {}
            target_value = str(obj.get("value") or target_opt.get("text") or "").strip()
            if target_value and target_value in before:
                semantic_value_leaks.append(row.get("row_id"))
    return {
        "rows": len(rows),
        "roots": len(root_counts),
        "task_counts": dict(task_counts.most_common()),
        "label_counts": dict(label_counts.most_common()),
        "max_rows_per_root": max(root_counts.values()) if root_counts else 0,
        "singleton_rows": len(singleton_rows),
        "singleton_examples": singleton_rows[:20],
        "prompt_label_leak_rows": len(prompt_label_leaks),
        "prompt_label_leak_examples": prompt_label_leaks[:20],
        "target_value_visible_before_candidates_rows": len(semantic_value_leaks),
        "target_value_visible_before_candidates_examples": semantic_value_leaks[:20],
        "missing_deterministic_shuffle_rows": len(missing_shuffle),
        "missing_deterministic_shuffle_examples": missing_shuffle[:20],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(ROWS)
    bridge = load_json(BRIDGE_AUDIT)
    existing = {str(row.get("row_id")): row for row in load_jsonl(GEMMA_ROWS)}
    result_rows: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        if row_id in existing and existing[row_id].get("gemma12b_raw_output"):
            raw = str(existing[row_id]["gemma12b_raw_output"])
        else:
            raw = ollama_generate(prompt_for_gemma(row))
        result_rows.append(row_result(row, raw))
        write_jsonl(GEMMA_ROWS, result_rows)

    hundred = ((bridge.get("scores") or {}).get("stage11690_bridged_original_web") or {})
    gemma_metric = metric(result_rows, "gemma12b_correct")
    comparison = {
        "hundred_m_correct": hundred.get("correct"),
        "hundred_m_rows": hundred.get("rows"),
        "hundred_m_accuracy": hundred.get("accuracy"),
        "gemma12b_correct": gemma_metric.get("correct"),
        "gemma12b_rows": gemma_metric.get("rows"),
        "gemma12b_accuracy": gemma_metric.get("accuracy"),
        "delta_hundred_m_minus_gemma": None
        if hundred.get("accuracy") is None or gemma_metric.get("accuracy") is None
        else hundred["accuracy"] - gemma_metric["accuracy"],
    }
    audit = anticheat(rows)
    gates = {
        "same_manifest_row_count": comparison["hundred_m_rows"] == comparison["gemma12b_rows"] == len(rows) == 66,
        "gemma_full_coverage": gemma_metric.get("scored_rows") == len(rows),
        "hundred_m_beats_gemma": (comparison["hundred_m_correct"] or 0) > (comparison["gemma12b_correct"] or 0),
        "no_singleton_rows": audit["singleton_rows"] == 0,
        "no_prompt_label_leaks": audit["prompt_label_leak_rows"] == 0,
        "deterministic_shuffle_declared": audit["missing_deterministic_shuffle_rows"] == 0,
        "bridge_gates_passed": all((bridge.get("gates") or {}).values()),
    }
    decision = (
        "canonical_bridged_web_100m_beats_gemma_same_manifest"
        if all(gates.values())
        else "canonical_bridged_web_comparison_incomplete_or_no_100m_win"
    )
    summary = {
        "stage": 11691,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "model_id": MODEL_ID,
        "ollama_host": OLLAMA_HOST,
        "comparison": comparison,
        "gemma12b": gemma_metric,
        "by_task_gemma12b": group_metric(result_rows, "task_type", "gemma12b_correct"),
        "by_repo_gemma12b": group_metric(result_rows, "repo_id", "gemma12b_correct"),
        "gemma_misses": [row for row in result_rows if row.get("gemma12b_correct") is not True],
        "anticheat": audit,
        "gates": gates,
        "claim_boundary": [
            "This compares Gemma and 100M on the canonical-bridged original Web heldout prompt surface, not the raw Stage11548 prompt surface.",
            "The roots are the same 11 original Web heldout roots; the interface is canonical role-typed candidate scoring.",
            "This is compact bounded-choice maintainer scoring, not freeform repair or executable patch synthesis.",
            "The configured Ollama host must be the GPU2-pinned service at 127.0.0.1:11435.",
        ],
        "source_artifacts": {"rows": rel(ROWS), "bridge_audit": rel(BRIDGE_AUDIT)},
        "outputs": {"summary": rel(SUMMARY), "gemma_rows": rel(GEMMA_ROWS)},
    }
    write_json(SUMMARY, summary)
    write_jsonl(GEMMA_ROWS, result_rows)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "comparison": comparison, "gates": gates, "anticheat": audit}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
