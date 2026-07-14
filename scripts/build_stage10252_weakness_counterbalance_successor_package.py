#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10252
NAME = "stage10252_weakness_counterbalance_successor_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
EVAL_JSONL = OUT_DIR / "agentkernel_lite_encdec_eval.jsonl"
PACKAGE_JSON = OUT_DIR / "weakness_counterbalance_successor_package.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_PACKAGE = ROOT / "runs/local/artifacts/stage10247_weakness_counterbalance_package/weakness_counterbalance_package.json"
REPLENISHMENT = ROOT / "runs/local/artifacts/stage10251_disjoint_reviewed_replenishment_inventory/disjoint_reviewed_replenishment_inventory.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def language_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        lang = str(row.get("language_family") or "")
        counts[lang] = counts.get(lang, 0) + 1
    return dict(sorted(counts.items()))


def build_package() -> dict[str, Any]:
    base = load_json(BASE_PACKAGE)
    base_train = load_jsonl(ROOT / str(base.get("train_dataset_path") or ""))
    holdout = load_jsonl(ROOT / str(base.get("eval_dataset_path") or ""))

    repl = load_json(REPLENISHMENT)
    repl_rows = load_jsonl(ROOT / str(repl.get("generated_train_rows_path") or ""))

    seen_ids = {str(row.get("row_id") or "") for row in base_train}
    merged_train = list(base_train)
    added_rows = 0
    for row in repl_rows:
        row_id = str(row.get("row_id") or "")
        if row_id in seen_ids:
            continue
        seen_ids.add(row_id)
        merged_train.append(row)
        added_rows += 1

    write_jsonl(TRAIN_JSONL, merged_train)
    write_jsonl(EVAL_JSONL, holdout)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(merged_train) and bool(holdout),
        "base_package": display(BASE_PACKAGE),
        "replenishment_inventory": display(REPLENISHMENT),
        "train_dataset_path": display(TRAIN_JSONL),
        "eval_dataset_path": display(EVAL_JSONL),
        "claim_scope": "auxiliary weakness-repair successor only; exact stage10242 misses remain strict-eval holdout only, with added disjoint c_cpp abstention-only honesty rows",
        "required_honesty_gates": [
            "exact stage10242 miss rows remain strict-eval holdout only",
            "new support rows must be train-only and disjoint from the current miss frontier",
            "web weakness families remain uncovered until fresh source-backed roots are generated",
            "package remains auxiliary and does not upgrade the primary maintainer claim by itself",
        ],
        "metrics": {
            "base_train_rows": len(base_train),
            "added_replenishment_rows": added_rows,
            "train_rows": len(merged_train),
            "holdout_rows": len(holdout),
            "train_language_counts": language_counts(merged_train),
            "holdout_language_counts": language_counts(holdout),
        },
        "remaining_uncovered_rules": [
            "web_evidence",
            "web_symptom",
            "web_patch",
            "web_minfix",
        ],
        "next_probe_intent": "Warm-start from stage10224 and test whether c_cpp abstention honesty improves without contaminating the web miss frontier.",
    }
    write_json(PACKAGE_JSON, payload)
    write_json(SUMMARY, {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": payload["passed"],
        "package": display(PACKAGE_JSON),
        "metrics": payload["metrics"],
    })
    return payload


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    payload = build_package()
    print(json.dumps({
        "stage": STAGE,
        "passed": payload["passed"],
        "package": display(PACKAGE_JSON),
        "metrics": payload["metrics"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
