#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10432
NAME = "stage10432_reviewed_v27_strict_leak_cleanup_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
QUEUE_JSON = OUT_DIR / "reviewed_v27_strict_leak_cleanup_queue.json"
ROWS_JSONL = OUT_DIR / "reviewed_v27_strict_leak_cleanup_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

STRICT_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_strict_eval.jsonl"
MARGIN_JSONL = ROOT / "runs/local/artifacts/stage10431_reviewed_v27_saved_runtime_margin_audit/reviewed_v27_saved_runtime_margin_rows.jsonl"
EVAL_HACK_JSON = ROOT / "runs/local/artifacts/stage10429_reviewed_v27_eval_hacking_audit/reviewed_v27_eval_hacking_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


def extract_leak_snippet(prompt: str, target: str) -> str:
    body = prompt.split("\nOptions:\n", 1)[0]
    for line in body.splitlines():
        if target and target in line:
            return line[:400]
    return ""


def classify_mechanism(target_value: str) -> str:
    if "/" in target_value:
        return "exact_candidate_path_visible_in_evidence"
    return "semantic_target_name_visible_in_evidence"


def main() -> None:
    strict_rows = {row["row_id"]: row for row in load_jsonl(STRICT_ROWS_JSONL)}
    margin_rows = load_jsonl(MARGIN_JSONL)
    eval_hack = load_json(EVAL_HACK_JSON)

    leak_rows: list[dict[str, Any]] = []
    for margin_row in margin_rows:
        if not margin_row.get("prompt_target_leak"):
            continue
        row = strict_rows[margin_row["row_id"]]
        target_value = str(margin_row["target_semantic_value"])
        prompt = str(row.get("prompt_text") or row.get("input_text") or "")
        leak_rows.append(
            {
                "row_id": row["row_id"],
                "language_family": row.get("language_family"),
                "task_type": row.get("task_type"),
                "repo_family": row.get("repo_family"),
                "target_label": margin_row.get("target_label"),
                "target_semantic_value": target_value,
                "predicted_label": margin_row.get("predicted_label"),
                "predicted_semantic_value": margin_row.get("predicted_semantic_value"),
                "margin_top1_minus_top2": margin_row.get("margin_top1_minus_top2"),
                "selected_test_anchor": bool(row.get("selected_test_anchor")),
                "verifier_anchor": bool(row.get("verifier_anchor")),
                "mechanism": classify_mechanism(target_value),
                "leak_snippet": extract_leak_snippet(prompt, target_value),
                "recommended_repair": (
                    "replace the exact path/value-bearing evidence line with a causal paraphrase or alternate supporting fact"
                ),
                "must_revalidate_after_repair": [
                    "same root remains answerable from visible evidence",
                    "target semantic value no longer appears verbatim before options",
                    "strict row remains admitted by anti-cheat review",
                ],
            }
        )
    leak_rows.sort(key=lambda row: (row["language_family"], row["task_type"], row["row_id"]))

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Strict-row anti-cheat cleanup queue for the reviewed v2.7 standalone benchmark path.",
            "These rows are currently scoreable, but they should not be treated as fully hardened until the prompt-visible target leakage is repaired.",
            "Repairs must preserve answerability and must not change split assignments or introduce same-root train leakage.",
        ],
        "source_artifacts": {
            "strict_rows": display(STRICT_ROWS_JSONL),
            "margin_audit": display(MARGIN_JSONL),
            "eval_hacking_audit": display(EVAL_HACK_JSON),
        },
        "summary": {
            "strict_rows": len(margin_rows),
            "strict_leak_rows": len(leak_rows),
            "all_rows_prompt_target_leak_rate": (eval_hack.get("prompt_leakage") or {}).get("prompt_contains_target_value_before_options_rate"),
            "strict_leak_languages": sorted({row["language_family"] for row in leak_rows}),
        },
        "repair_priority_order": [
            row["row_id"] for row in sorted(leak_rows, key=lambda row: (float(row["margin_top1_minus_top2"]), row["row_id"]))
        ],
        "repair_requirements": [
            "Do not alter root splits.",
            "Do not move stress rows into the promotable path.",
            "Re-run anti-cheat and same-runtime margin audit after leak cleanup.",
            "Prefer causal paraphrase or evidence substitution over masking with placeholders.",
        ],
        "rows": leak_rows,
        "outputs": {
            "queue_json": display(QUEUE_JSON),
            "queue_rows": display(ROWS_JSONL),
        },
    }

    write_json(QUEUE_JSON, payload)
    write_jsonl(ROWS_JSONL, leak_rows)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
