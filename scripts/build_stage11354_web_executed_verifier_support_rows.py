#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11354
NAME = "stage11354_web_executed_verifier_support_rows"
OUT = ART / NAME
SUMMARY = OUT / "web_executed_verifier_support_rows.json"
OUT_ROWS = OUT / "web_executed_verifier_train_support_rows.jsonl"
SOURCE_ROWS = ART / "stage11347_web_static_verifier_maintainer_rows/web_static_verifier_train_support_rows.jsonl"
SOURCE_BUNDLES = ART / "stage11347_web_static_verifier_maintainer_rows/web_static_verifier_root_bundles.jsonl"
EXEC = ART / "stage11353_web_verifier_execution_evidence/web_verifier_execution_evidence.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    exec_card = read_json(EXEC)
    by_root = exec_card.get("by_root", {})
    passed_roots = {slug for slug, card in by_root.items() if card.get("execution_status") == "verifier_executed_passed"}
    rows = []
    blocked_rows = []
    for row in read_jsonl(SOURCE_ROWS):
        root_id = str(row.get("root_id") or "")
        slug = root_id.split("stage11347::", 1)[-1]
        if slug not in passed_roots:
            blocked_rows.append({"row_id": row.get("row_id"), "root_id": root_id, "reason": "root_not_verifier_executed_passed"})
            continue
        item = dict(row)
        item["row_id"] = item["row_id"].replace("stage11347::", "stage11354::")
        item["root_id"] = item["root_id"].replace("stage11347::", "stage11354::")
        item["root_lineage_key"] = str(item.get("root_lineage_key", "")) + "::executed_verifier_stage11353"
        item["review_status"] = "executed_verifier_train_support_admitted"
        item["strict_eval_eligible"] = False
        item["train_support_only"] = True
        item.setdefault("anti_cheat", {})["static_verifier_not_executed"] = False
        item["anti_cheat"]["executed_verifier_output_attached"] = True
        exec_evidence = by_root[slug]
        result_text = exec_evidence.get("test_result") or "verifier executed; see log"
        log_text = ((exec_evidence.get("attempt") or {}).get("log") or "")
        visible_exec = f"Visible verifier execution evidence:\nExecuted targeted verifier: {result_text}. Log artifact: {log_text}."
        for text_field in ("input_text", "prompt_text"):
            current = str(item.get(text_field) or "")
            if "Visible verifier execution evidence:" not in current:
                item[text_field] = current.replace("Options:\n", visible_exec + "\nOptions:\n")
        item["verifier_execution_evidence"] = exec_evidence
        projection = item.get("standalone_projection_source") or {}
        projection["verifier_execution_evidence"] = by_root[slug]
        projection["projection_mode"] = "web_executed_verifier_maintainer_perspective"
        item["standalone_projection_source"] = projection
        rows.append(item)
    bundles = []
    for bundle in read_jsonl(SOURCE_BUNDLES):
        if bundle.get("root_slug") in passed_roots:
            b = dict(bundle)
            b["root_id"] = b["root_id"].replace("stage11347::", "stage11354::")
            b["root_lineage_key"] = str(b.get("root_lineage_key", "")) + "::executed_verifier_stage11353"
            b["review"]["verifier_execution_status"] = "executed_passed"
            b["verifier_execution_evidence"] = by_root[b["root_slug"]]
            bundles.append(b)
    write_jsonl(OUT_ROWS, rows)
    write_jsonl(OUT / "web_executed_verifier_root_bundles.jsonl", bundles)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": bool(rows),
        "decision": "web_executed_verifier_train_support_rows_ready" if rows else "web_executed_verifier_rows_blocked",
        "counts": {
            "executed_roots": len(passed_roots),
            "bundles": len(bundles),
            "rows": len(rows),
            "blocked_source_rows": len(blocked_rows),
            "rows_by_root": dict(sorted(Counter(r["root_id"] for r in rows).items())),
            "rows_by_task": dict(sorted(Counter(r["task_type"] for r in rows).items())),
        },
        "admissibility": {
            "train_support_only": True,
            "strict_eval_eligible": False,
            "verifier_backed": True,
            "why_not_strict_eval": "Rows are derived from already-used Stage11347 support roots; use for training/support, not heldout promotion.",
        },
        "excluded": blocked_rows[:20],
        "source_artifacts": {"stage11347_rows": rel(SOURCE_ROWS), "stage11347_bundles": rel(SOURCE_BUNDLES), "stage11353_execution": rel(EXEC)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(OUT_ROWS), "bundles": rel(OUT / "web_executed_verifier_root_bundles.jsonl")},
        "recommended_next_action": "Use these executed-verifier Web rows in the next support package; build separate heldout Web roots from different Stage11346 candidates before promotion.",
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
