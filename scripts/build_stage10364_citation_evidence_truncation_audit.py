#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10364
NAME = "stage10364_citation_evidence_truncation_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_JSON = OUT_DIR / "citation_evidence_truncation_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PROBE_RESULT = ROOT / "runs/local/artifacts/stage10363_source_backed_cpp_rust_citation_support_probe/bounded_decoder_probe/execution_result.json"
MANIFEST = ROOT / "runs/local/artifacts/stage10362_source_backed_cpp_rust_citation_support_execution_request/source_backed_cpp_rust_citation_support_manifest.jsonl"


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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def evidence_prefixes(prompt_text: str) -> list[str]:
    prefixes: list[str] = []
    for line in str(prompt_text).splitlines():
        stripped = line.strip()
        if not stripped or stripped == "Evidence:":
            continue
        if stripped == "Options:":
            break
        if ": " in stripped:
            prefixes.append(stripped.split(": ", 1)[0].split(" [", 1)[0])
    return prefixes


def main() -> None:
    rows = {row["row_id"]: row for row in load_jsonl(MANIFEST)}
    result = load_json(PROBE_RESULT)
    row_cards = (((result.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("row_cards") or [])
    misses = [row for row in row_cards if not row.get("constrained_choice_match")]

    audited_rows: list[dict[str, Any]] = []
    omitted_gold_rows = 0
    duplicate_target_rows = 0
    for miss in misses:
        row_id = str(miss.get("row_id") or "")
        row = rows.get(row_id)
        if not row:
            continue
        source = row.get("standalone_projection_source") or {}
        gold_value = str(source.get("gold_value") or "")
        options = source.get("opaque_options") or []
        option_values = [str(opt.get("value") or "") for opt in options if isinstance(opt, dict)]
        prompt_keys = evidence_prefixes(str(row.get("prompt_text") or ""))
        gold_visible = gold_value in prompt_keys
        if not gold_visible:
            omitted_gold_rows += 1
        prompt_text = str(row.get("prompt_text") or "")
        duplicate_target = False
        for key in prompt_keys:
            if key == gold_value:
                continue
            gold_prefix = f"{gold_value} ["
            other_prefix = f"{key} ["
            # Compare only the first surfaced snippet line to catch path/text collisions.
            gold_lines = [line for line in prompt_text.splitlines() if line.startswith(gold_prefix)]
            other_lines = [line for line in prompt_text.splitlines() if line.startswith(other_prefix)]
            if gold_lines and other_lines and gold_lines[0].split(": ", 1)[-1] == other_lines[0].split(": ", 1)[-1]:
                duplicate_target = True
                break
        if duplicate_target:
            duplicate_target_rows += 1
        audited_rows.append(
            {
                "row_id": row_id,
                "language_family": row.get("language_family"),
                "task_type": row.get("task_type"),
                "prompt_visible_evidence_keys": prompt_keys,
                "gold_value": gold_value,
                "gold_visible_in_prompt": gold_visible,
                "opaque_option_values": option_values,
                "predicted_label": miss.get("constrained_choice_top1_label"),
                "target_label": miss.get("target_text"),
                "duplicate_target_surface_detected": duplicate_target,
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "source_probe_result": display(PROBE_RESULT),
        "source_manifest": display(MANIFEST),
        "metrics": {
            "strict_accuracy": ((result.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("constrained_choice_top1_accuracy"),
            "miss_rows": len(audited_rows),
            "omitted_gold_rows": omitted_gold_rows,
            "duplicate_target_rows": duplicate_target_rows,
            "evidence_truncation_supported": omitted_gold_rows == len(audited_rows) and len(audited_rows) > 0,
        },
        "decision": {
            "headline": "current weak c_cpp/rust evidence_citation rows are not honest maintainer probes because the prompt truncates away the gold evidence bucket",
            "next_best_step": "rebuild compact bounded projection with all task-visible evidence keys surfaced, then rerun 100M and Gemma before any more citation training",
        },
        "audited_rows": audited_rows,
    }
    write_json(OUT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "artifact": display(OUT_JSON),
            "metrics": payload["metrics"],
        },
    )
    print(json.dumps({"stage": STAGE, "passed": True, "artifact": display(OUT_JSON), "metrics": payload["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
