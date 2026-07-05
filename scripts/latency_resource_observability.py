from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping

DEFAULT_LIMITS = {
    "latency_ms": 30_000,
    "memory_peak_mb": 4_096,
    "token_count": 16_000,
    "tool_cost": 50,
    "tool_call_count": 50,
}


def _float(row: Mapping[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _usage(row: Mapping[str, Any]) -> Mapping[str, Any]:
    usage = row.get("usage", row.get("resources", {}))
    return usage if isinstance(usage, Mapping) else {}


def observe_resource_row(row: Mapping[str, Any], *, limits: Mapping[str, float] | None = None) -> dict[str, Any]:
    lim = dict(DEFAULT_LIMITS)
    if limits:
        lim.update({str(k): float(v) for k, v in limits.items()})
    usage = _usage(row)
    latency_ms = _float(usage, "latency_ms", "wall_time_ms", default=_float(row, "latency_ms", "wall_time_ms"))
    memory_peak_mb = _float(usage, "memory_peak_mb", "memory_mb", default=_float(row, "memory_peak_mb", "memory_mb"))
    token_count = _float(usage, "token_count", "tokens", default=_float(row, "token_count", "tokens"))
    tool_cost = _float(usage, "tool_cost", "tool_calls", default=_float(row, "tool_cost", "tool_calls"))
    tool_call_count = _float(usage, "tool_call_count", "tool_calls", default=_float(row, "tool_call_count", "tool_calls"))
    metrics = {
        "latency_ms": latency_ms,
        "memory_peak_mb": memory_peak_mb,
        "token_count": token_count,
        "tool_cost": tool_cost,
        "tool_call_count": tool_call_count,
    }
    ratios = {key: (metrics[key] / lim[key] if lim[key] else 0.0) for key in metrics}
    violations = sorted(key for key, ratio in ratios.items() if ratio > 1.0)
    warnings = sorted(key for key, ratio in ratios.items() if 0.8 <= ratio <= 1.0)
    if violations:
        route = "BLOCK_RESOURCE_BUDGET_VIOLATION"
    elif warnings:
        route = "HOLD_RESOURCE_BUDGET_WARNING"
    else:
        route = "PASS_RESOURCE_OBSERVABILITY"
    return {
        "row_id": str(row.get("row_id", row.get("trace_id", row.get("id", "unknown_row")))),
        "resource_route": route,
        "metrics": metrics,
        "ratios": {key: round(value, 6) for key, value in ratios.items()},
        "budget_violation": bool(violations),
        "violations": violations,
        "warnings": warnings,
        "authority": {
            "runtime_authorized": False,
            "training_authorized": False,
            "promotion_ready": False,
        },
    }


def observability_card(rows: Iterable[Mapping[str, Any]], *, limits: Mapping[str, float] | None = None) -> dict[str, Any]:
    records = [observe_resource_row(row, limits=limits) for row in rows]
    routes = Counter(record["resource_route"] for record in records)
    metric_keys = ["latency_ms", "memory_peak_mb", "token_count", "tool_cost", "tool_call_count"]
    aggregate = {}
    for key in metric_keys:
        values = [record["metrics"][key] for record in records]
        aggregate[f"mean_{key}"] = round(mean(values), 6) if values else 0.0
        aggregate[f"max_{key}"] = max(values) if values else 0.0
    return {
        "rows": len(records),
        "records": records,
        "metrics": {
            "rows": len(records),
            "pass_rows": routes.get("PASS_RESOURCE_OBSERVABILITY", 0),
            "warning_rows": routes.get("HOLD_RESOURCE_BUDGET_WARNING", 0),
            "blocked_rows": routes.get("BLOCK_RESOURCE_BUDGET_VIOLATION", 0),
            "budget_violation_rows": sum(1 for record in records if record["budget_violation"]),
            "route_counts": dict(routes),
            "authority_rows": 0,
            **aggregate,
        },
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Passive latency/resource budget observability card.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    card = observability_card(read_jsonl(args.manifest))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
