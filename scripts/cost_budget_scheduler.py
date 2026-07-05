from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_LIMITS = {
    "token_budget": 16000,
    "tool_call_budget": 16,
    "test_budget": 4,
    "diff_line_budget": 120,
    "wall_time_budget_s": 300,
}


def ratio(used: float, budget: float) -> float:
    if budget <= 0:
        return 1.0
    return max(0.0, used / budget)


def budget_class(max_ratio: float) -> str:
    if max_ratio >= 1.0:
        return "exhausted"
    if max_ratio >= 0.85:
        return "critical"
    if max_ratio >= 0.65:
        return "tight"
    return "ok"


def schedule(row: dict[str, Any], limits: dict[str, Any] | None = None) -> dict[str, Any]:
    limits = {**DEFAULT_LIMITS, **(limits or {})}
    used = row.get("used") if isinstance(row.get("used"), dict) else row
    ratios = {
        "token_ratio": ratio(float(used.get("tokens", used.get("token_used", 0))), float(limits["token_budget"])),
        "tool_call_ratio": ratio(float(used.get("tool_calls", 0)), float(limits["tool_call_budget"])),
        "test_ratio": ratio(float(used.get("tests", used.get("test_runs", 0))), float(limits["test_budget"])),
        "diff_line_ratio": ratio(float(used.get("diff_lines", used.get("changed_lines", 0))), float(limits["diff_line_budget"])),
        "wall_time_ratio": ratio(float(used.get("wall_time_s", 0)), float(limits["wall_time_budget_s"])),
    }
    max_ratio = max(ratios.values()) if ratios else 0.0
    bclass = budget_class(max_ratio)
    has_evidence = bool(row.get("has_evidence", used.get("has_evidence", False)))
    uncertainty = float(row.get("uncertainty", used.get("uncertainty", 0.0)))
    tests_passed = bool(row.get("tests_passed", used.get("tests_passed", False)))
    if bclass == "exhausted":
        route = "STOP_BUDGET_EXHAUSTED"
    elif bclass == "critical" and not tests_passed:
        route = "HOLD_BUDGET_REVIEW"
    elif not has_evidence and bclass in {"ok", "tight"}:
        route = "RETRIEVE_MORE_WITHIN_BUDGET"
    elif uncertainty >= 0.75 and bclass == "ok":
        route = "RETRIEVE_OR_INSPECT_MORE"
    elif tests_passed and bclass in {"ok", "tight", "critical"}:
        route = "STOP_VERIFIED_WITHIN_BUDGET"
    else:
        route = "CONTINUE_WITHIN_BUDGET"
    return {
        "row_id": str(row.get("row_id") or row.get("candidate_id") or row.get("id") or "unknown_row"),
        "budget_route": route,
        "budget_class": bclass,
        "budget_ratios": {key: round(value, 4) for key, value in ratios.items()},
        "max_budget_ratio": round(max_ratio, 4),
        "budget_ok": bclass in {"ok", "tight"},
        "tool_call_budget_ok": ratios["tool_call_ratio"] < 1.0,
        "test_budget_ok": ratios["test_ratio"] < 1.0,
        "decoder_budget_ok": ratios["token_ratio"] < 1.0,
        "stop_or_retrieve_route": route,
    }


def schedule_rows(rows: list[dict[str, Any]], limits: dict[str, Any] | None = None) -> dict[str, Any]:
    records = [schedule(row, limits=limits) for row in rows]
    route_counts: dict[str, int] = {}
    class_counts: dict[str, int] = {}
    for record in records:
        route_counts[record["budget_route"]] = route_counts.get(record["budget_route"], 0) + 1
        class_counts[record["budget_class"]] = class_counts.get(record["budget_class"], 0) + 1
    return {
        "rows": len(rows),
        "records": records,
        "metrics": {
            "rows": len(rows),
            "route_counts": route_counts,
            "budget_class_counts": class_counts,
            "budget_ok_rows": sum(int(record["budget_ok"]) for record in records),
            "stop_rows": sum(int(record["budget_route"].startswith("STOP")) for record in records),
            "retrieve_rows": sum(int("RETRIEVE" in record["budget_route"]) for record in records),
        },
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Route rows by token/tool/test/diff/time budgets without executing tools.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    card = schedule_rows(read_jsonl(args.manifest))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
