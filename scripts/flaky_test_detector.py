from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

PASS_STATES = {"pass", "passed", "success", "ok"}
FAIL_STATES = {"fail", "failed", "error", "timeout", "crash"}


def normalize_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in PASS_STATES:
        return "pass"
    if text in FAIL_STATES:
        return "fail"
    return "unknown"


def failure_signature(observation: dict[str, Any]) -> str:
    for key in ["failure_signature", "error_type", "exception", "stderr_digest", "message"]:
        value = observation.get(key)
        if isinstance(value, str) and value:
            return value[:200]
    return "unknown_failure"


def classify_failure_stability(row: dict[str, Any]) -> dict[str, Any]:
    observations = row.get("observations") or row.get("reruns") or row.get("test_runs") or []
    if not isinstance(observations, list):
        observations = []
    statuses = [normalize_status(obs.get("status") if isinstance(obs, dict) else obs) for obs in observations]
    counts = Counter(statuses)
    fail_sigs = Counter(failure_signature(obs) for obs in observations if isinstance(obs, dict) and normalize_status(obs.get("status")) == "fail")
    if not observations:
        route = "HOLD_NO_RERUN_EVIDENCE"
    elif counts["pass"] and counts["fail"]:
        route = "HOLD_FLAKY_FAILURE"
    elif counts["fail"] >= 2 and len(fail_sigs) == 1:
        route = "PASS_STABLE_FAILURE"
    elif counts["fail"] >= 2 and len(fail_sigs) > 1:
        route = "HOLD_UNSTABLE_FAILURE_SIGNATURE"
    elif counts["pass"] and not counts["fail"]:
        route = "PASS_STABLE_PASS"
    else:
        route = "HOLD_INSUFFICIENT_RERUNS"
    return {
        "row_id": str(row.get("row_id") or row.get("candidate_id") or row.get("id") or "unknown_row"),
        "flaky_test_route": route,
        "rerun_count": len(observations),
        "pass_count": counts["pass"],
        "fail_count": counts["fail"],
        "unknown_count": counts["unknown"],
        "failure_signatures": dict(fail_sigs),
        "failure_stability": route in {"PASS_STABLE_FAILURE", "PASS_STABLE_PASS"},
        "rerun_needed": route in {"HOLD_NO_RERUN_EVIDENCE", "HOLD_INSUFFICIENT_RERUNS"},
        "route_to_holdout": route in {"HOLD_FLAKY_FAILURE", "HOLD_UNSTABLE_FAILURE_SIGNATURE"},
    }


def classify_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    records = [classify_failure_stability(row) for row in rows]
    route_counts: dict[str, int] = {}
    for record in records:
        route_counts[record["flaky_test_route"]] = route_counts.get(record["flaky_test_route"], 0) + 1
    return {
        "rows": len(rows),
        "records": records,
        "metrics": {
            "rows": len(rows),
            "stable_rows": sum(int(record["failure_stability"]) for record in records),
            "rerun_needed_rows": sum(int(record["rerun_needed"]) for record in records),
            "holdout_rows": sum(int(record["route_to_holdout"]) for record in records),
            "route_counts": route_counts,
        },
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify provided rerun observations into stable/flaky/holdout failure routes.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    card = classify_rows(read_jsonl(args.manifest))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
