from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

REQUIRED_SPAN_FIELDS = {"span_id", "span_type", "name"}
BLOCKING_TRACE_FLAGS = {"locked_eval_source", "hidden_eval_source", "raw_source_body_included", "target_answer_included"}


def stable_trace_id(row: Mapping[str, Any]) -> str:
    raw = str(row.get("trace_id") or row.get("eval_id") or row.get("row_id") or json.dumps(row, sort_keys=True))
    return "trace_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _bool(value: Any) -> bool:
    return value is True or str(value).lower() in {"1", "true", "yes"}


def _spans(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    spans = row.get("spans", row.get("span_tree", []))
    return list(spans) if isinstance(spans, list) else []


def _metrics(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    metrics = row.get("metric_events", row.get("metrics", []))
    if isinstance(metrics, list):
        return [dict(item) for item in metrics if isinstance(item, Mapping)]
    if isinstance(metrics, Mapping):
        return [{"metric": str(k), "value": v} for k, v in metrics.items()]
    return []


def validate_trace(row: Mapping[str, Any]) -> dict[str, Any]:
    trace_id = stable_trace_id(row)
    spans = _spans(row)
    metrics = _metrics(row)
    reasons = []
    blocking_flags = sorted(flag for flag in BLOCKING_TRACE_FLAGS if _bool(row.get(flag)))
    if blocking_flags:
        reasons.extend(blocking_flags)
    if not spans:
        reasons.append("missing_spans")
    for span in spans:
        missing = sorted(field for field in REQUIRED_SPAN_FIELDS if field not in span)
        if missing:
            reasons.append("span_missing_" + "_".join(missing))
            break
    has_failure = _bool(row.get("failed")) or bool(row.get("failure_type")) or bool(row.get("error"))
    failure_packet = {
        "trace_id": trace_id,
        "failure_type": str(row.get("failure_type") or row.get("error") or "none"),
        "failed": has_failure,
        "dataset_patch_eligible": False,
        "reasons": [],
    }
    if blocking_flags:
        route = "BLOCK_TRACE_CONTAMINATION"
        failure_packet["reasons"] = blocking_flags
    elif reasons:
        route = "HOLD_TRACE_SCHEMA_REVIEW"
        failure_packet["reasons"] = reasons
    elif has_failure:
        route = "PASS_FAILURE_TRACE_PACKET"
        failure_packet["dataset_patch_eligible"] = True
    else:
        route = "PASS_EVAL_TRACE"
    dataset_patch_link = {
        "trace_id": trace_id,
        "eligible": bool(failure_packet["dataset_patch_eligible"]),
        "patch_op": "compile_failure_to_dataset_patch" if failure_packet["dataset_patch_eligible"] else "none",
    }
    return {
        "trace_id": trace_id,
        "trace_route": route,
        "span_tree": spans,
        "metric_events": metrics,
        "failure_packet": failure_packet,
        "dataset_patch_link": dataset_patch_link,
        "reasons": reasons,
        "authority": {
            "training_authorized": False,
            "runtime_authorized": False,
            "promotion_ready": False,
        },
    }


def trace_observability_card(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    records = [validate_trace(row) for row in rows]
    routes = Counter(record["trace_route"] for record in records)
    return {
        "rows": len(rows),
        "records": records,
        "metrics": {
            "rows": len(rows),
            "pass_trace_rows": routes.get("PASS_EVAL_TRACE", 0),
            "failure_packet_rows": routes.get("PASS_FAILURE_TRACE_PACKET", 0),
            "schema_review_rows": routes.get("HOLD_TRACE_SCHEMA_REVIEW", 0),
            "blocked_rows": routes.get("BLOCK_TRACE_CONTAMINATION", 0),
            "dataset_patch_eligible_rows": sum(1 for record in records if record["dataset_patch_link"]["eligible"]),
            "route_counts": dict(routes),
            "authority_rows": 0,
        },
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Shared no-authority traced eval observability schema.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    card = trace_observability_card(read_jsonl(args.manifest))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
