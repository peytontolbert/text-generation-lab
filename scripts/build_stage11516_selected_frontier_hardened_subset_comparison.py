#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
NAME = "stage11516_selected_frontier_hardened_subset_comparison"
OUT_DIR = ART / NAME
OUT_JSON = SUM / f"{NAME}.json"

PAYLOAD = ART / "stage11511_selected_frontier_harness_payload/selected_frontier_harness_payload.json"
RUNTIME_ROOT = ART / "stage11512_selected_frontier_harness_local_runtime"
ANTICHEAT = SUM / "stage11515_selected_frontier_anticheat_claim_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def before_options(prompt: str) -> str:
    marker = "\nOptions:"
    return prompt.split(marker, 1)[0] if marker in prompt else prompt


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "cell"


def row_expected_label(row: dict[str, Any]) -> str:
    return str(row.get("expected_label") or row.get("decoder_text") or row.get("target_label") or row.get("target") or "")


def row_expected_value(row: dict[str, Any]) -> str:
    label = row_expected_label(row)
    for opt in row.get("opaque_options") or []:
        if isinstance(opt, dict) and str(opt.get("label") or "") == label:
            return str(opt.get("value") or "")
    return ""


def gold_value_visible_before_options(row: dict[str, Any]) -> bool:
    value = normalize_text(row_expected_value(row))
    if len(value) < 4:
        return False
    prompt = str(row.get("prompt") or row.get("prompt_text") or row.get("input_text") or "")
    return value in normalize_text(before_options(prompt))


def main() -> None:
    payload = load_json(PAYLOAD)
    anticheat = load_json(ANTICHEAT)
    rows_by_id: dict[str, dict[str, Any]] = {}
    cell_by_row: dict[str, str] = {}
    excluded: dict[str, list[str]] = defaultdict(list)

    for run in payload.get("runs") or []:
        cell_key = str(run.get("cell_key") or "")
        for row in ((run.get("task_pack") or {}).get("manifest_rows") or []):
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("row_id") or "")
            rows_by_id[row_id] = row
            cell_by_row[row_id] = cell_key
            options = [opt for opt in row.get("opaque_options") or [] if isinstance(opt, dict)]
            if len(options) <= 1:
                excluded[row_id].append("singleton_options")
            if gold_value_visible_before_options(row):
                excluded[row_id].append("gold_value_visible_before_options")

    hundred_m_predictions: dict[str, dict[str, Any]] = {}
    gemma_predictions: dict[str, dict[str, Any]] = {}
    for run in payload.get("runs") or []:
        cell_key = str(run.get("cell_key") or "")
        runtime_dir = RUNTIME_ROOT / slug(cell_key)
        for pred in read_jsonl(runtime_dir / "hundred_m/predictions.jsonl"):
            hundred_m_predictions[str(pred.get("row_id") or "")] = pred
        for pred in read_jsonl(runtime_dir / "gemma/rows.jsonl"):
            # The Gemma runtime rows include prediction fields in this harness.
            gemma_predictions[str(pred.get("row_id") or "")] = pred

    # Fallback to embedded stage11510 prediction fields if the Gemma rows file is schema-light.
    for row_id, row in rows_by_id.items():
        embedded = row.get("stage11510_predictions") or {}
        if row_id not in gemma_predictions and embedded:
            gemma_predictions[row_id] = {
                "row_id": row_id,
                "correct": embedded.get("gemma12b_correct"),
                "predicted": embedded.get("gemma12b_predicted_label"),
                "expected": row_expected_label(row),
            }

    kept_rows = [row_id for row_id in rows_by_id if row_id not in excluded]
    failures: list[str] = []
    if anticheat.get("passed") is not True:
        failures.append("stage11515_anticheat_not_passed")
    if not kept_rows:
        failures.append("no_hardened_subset_rows")

    by_language: dict[str, Counter[str]] = defaultdict(Counter)
    by_task: dict[str, Counter[str]] = defaultdict(Counter)
    examples: list[dict[str, Any]] = []
    for row_id in kept_rows:
        row = rows_by_id[row_id]
        lang = str(row.get("language_family") or "unknown")
        task = str(row.get("task_type") or "unknown")
        hpred = hundred_m_predictions.get(row_id) or {}
        gpred = gemma_predictions.get(row_id) or {}
        h_ok = hpred.get("correct") is True
        g_ok = gpred.get("correct") is True
        by_language[lang]["rows"] += 1
        by_language[lang]["hundred_m_correct"] += int(h_ok)
        by_language[lang]["gemma_correct"] += int(g_ok)
        by_task[task]["rows"] += 1
        by_task[task]["hundred_m_correct"] += int(h_ok)
        by_task[task]["gemma_correct"] += int(g_ok)
        examples.append(
            {
                "row_id": row_id,
                "language_family": lang,
                "task_type": task,
                "expected": row_expected_label(row),
                "hundred_m_predicted": hpred.get("predicted"),
                "hundred_m_correct": h_ok,
                "gemma_predicted": gpred.get("predicted"),
                "gemma_correct": g_ok,
            }
        )

    hundred_m_correct = sum(v["hundred_m_correct"] for v in by_language.values())
    gemma_correct = sum(v["gemma_correct"] for v in by_language.values())
    rows = len(kept_rows)

    def finalize(counter_map: dict[str, Counter[str]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, counts in sorted(counter_map.items()):
            n = int(counts["rows"])
            out[key] = {
                "rows": n,
                "hundred_m_correct": int(counts["hundred_m_correct"]),
                "hundred_m_accuracy": counts["hundred_m_correct"] / n if n else 0.0,
                "gemma_correct": int(counts["gemma_correct"]),
                "gemma_accuracy": counts["gemma_correct"] / n if n else 0.0,
            }
        return out

    audit = {
        "stage": 11516,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not failures and rows > 0 and hundred_m_correct > gemma_correct,
        "decision": "selected_frontier_beats_gemma_on_hardened_compact_subset" if rows > 0 and hundred_m_correct > gemma_correct else "selected_frontier_hardened_subset_not_promotable",
        "filter": {
            "excluded_reasons": {
                row_id: reasons for row_id, reasons in sorted(excluded.items())
            },
            "excluded_rows": len(excluded),
            "kept_rows": rows,
        },
        "metrics": {
            "rows": rows,
            "hundred_m_correct": hundred_m_correct,
            "hundred_m_accuracy": hundred_m_correct / rows if rows else 0.0,
            "gemma_correct": gemma_correct,
            "gemma_accuracy": gemma_correct / rows if rows else 0.0,
            "delta_accuracy": (hundred_m_correct - gemma_correct) / rows if rows else 0.0,
            "by_language": finalize(by_language),
            "by_task_type": finalize(by_task),
        },
        "claim_boundary": [
            "This is a hardened subset of the compact same-task harness, excluding singleton-option and direct gold-value-visible evidence rows.",
            "It still is not source-heldout broad maintainer evidence because root breadth remains small and the packet has no executable patch/verifier rows.",
        ],
        "examples": examples,
        "failures": failures,
        "source_artifacts": {
            "payload": rel(PAYLOAD),
            "runtime_root": rel(RUNTIME_ROOT),
            "anticheat": rel(ANTICHEAT),
        },
    }
    write_json(OUT_DIR / f"{NAME}.json", audit)
    write_json(OUT_JSON, audit)
    print(json.dumps(audit, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
