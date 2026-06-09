#!/usr/bin/env python3
"""Build a compact intelligence/compute map from local research artifacts."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


EXACT_KEYS = (
    "strict_full_corpus_operation_gated_exact_top1",
    "pure_neural_exact_top1",
    "neural_exact_top1",
    "operation_gated_exact_top1",
    "exact_top1",
    "top1_accuracy",
    "top1",
)
ANSWER_KEYS = (
    "strict_full_corpus_operation_gated_answer_top1",
    "pure_neural_answer_top1",
    "neural_answer_top1_current_evaluator",
    "answer_top1_accuracy",
    "answer_top1",
    "operation_gated_answer_top1",
)
MRR_KEYS = (
    "strict_full_corpus_operation_gated_mrr",
    "pure_neural_mrr",
    "mean_reciprocal_rank",
    "mrr",
)
BIT_MPARAM_KEYS = (
    "hard_filter_verified_bits_per_million_params",
    "verified_bits_per_million_params",
    "answer_verified_bits_per_million_params",
    "neural_verified_bits_per_million_params",
)
BIT_TOKEN_KEYS = (
    "hard_filter_verified_bits_per_training_token",
    "verified_bits_per_training_token",
    "answer_verified_bits_per_training_token",
    "neural_verified_bits_per_training_token",
)
VERIFIED_BITS_KEYS = (
    "answer_verified_bits",
    "exact_verified_bits",
    "verified_bits",
    "hard_filter_verified_bits",
)
TRAIN_TOKEN_KEYS = (
    "estimated_training_retrieval_tokens",
    "estimated_retrieval_training_tokens",
    "train_retrieval_tokens",
)


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _flatten(value: Any, *, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            out.update(_flatten(child, prefix=child_prefix))
    elif isinstance(value, list):
        return out
    else:
        out[prefix] = value
    return out


def _first_number(flat: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for wanted in keys:
        for key, value in flat.items():
            if key == wanted or key.endswith("." + wanted):
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return float(value)
    return None


def _first_int(flat: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    value = _first_number(flat, keys)
    return int(value) if value is not None else None


def _first_text(flat: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for wanted in keys:
        for key, value in flat.items():
            if key == wanted or key.endswith("." + wanted):
                if isinstance(value, str) and value:
                    return value
    return None


def _scale_band(params: int | None) -> str:
    if params is None:
        return "unknown"
    if params < 10_000:
        return "<10k"
    if params < 20_000:
        return "10k-20k"
    if params < 30_000:
        return "20k-30k"
    if params < 50_000:
        return "30k-50k"
    if params < 100_000:
        return "50k-100k"
    if params < 1_000_000:
        return "100k-1m"
    if params < 10_000_000:
        return "1m-10m"
    return "10m+"


def _record_kind(record: dict[str, Any], flat: dict[str, Any]) -> str:
    label = " ".join(
        str(record.get(key, ""))
        for key in ("run_id", "label", "status", "decision", "note", "verdict")
    ).lower()
    if "hard_filter" in label or bool(record.get("structured_key_hard_filter")):
        return "verified_runtime"
    if "rejected" in label or "negative" in label:
        return "negative_result"
    if _first_number(flat, EXACT_KEYS) == 1.0 or _first_number(flat, ANSWER_KEYS) == 1.0:
        return "frontier_candidate"
    return "measurement"


def _normalize(record: dict[str, Any], source: str) -> dict[str, Any] | None:
    flat = _flatten(record)
    params = _first_int(flat, ("params", "parameter_count", "total_parameters"))
    exact = _first_number(flat, EXACT_KEYS)
    answer = _first_number(flat, ANSWER_KEYS)
    bits_mparam = _first_number(flat, BIT_MPARAM_KEYS)
    bits_token = _first_number(flat, BIT_TOKEN_KEYS)
    verified_bits = _first_number(flat, VERIFIED_BITS_KEYS)
    train_tokens = _first_number(flat, TRAIN_TOKEN_KEYS)
    if params is None and exact is None and answer is None and bits_mparam is None:
        return None
    label = (
        record.get("label")
        or record.get("run_id")
        or record.get("stage")
        or _first_text(flat, ("label", "run_id", "stage"))
        or source
    )
    steps = _first_int(flat, ("steps", "completed_steps", "max_steps"))
    verified_bits_per_param = bits_mparam / 1_000_000.0 if bits_mparam is not None else None
    param_steps = float(params * steps) if params is not None and steps is not None else None
    param_train_tokens = float(params * train_tokens) if params is not None and train_tokens is not None else None
    return {
        "label": str(label),
        "run_id": str(record.get("run_id") or _first_text(flat, ("run_id",)) or ""),
        "source": source,
        "kind": _record_kind(record, flat),
        "params": params,
        "scale_band": _scale_band(params),
        "steps": steps,
        "exact_top1": exact,
        "answer_top1": answer,
        "mrr": _first_number(flat, MRR_KEYS),
        "verified_bits": verified_bits,
        "verified_bits_per_param": verified_bits_per_param,
        "verified_bits_per_million_params": bits_mparam,
        "verified_bits_per_training_token": bits_token,
        "estimated_training_retrieval_tokens": train_tokens,
        "training_param_steps_proxy": param_steps,
        "training_param_token_proxy": param_train_tokens,
        "hard_filter_corrections": _first_int(
            flat,
            (
                "hard_filter_corrections",
                "top1_corrected_by_hard_filter",
                "hard_filter_top1_corrected_by_hard_filter",
            ),
        ),
        "hard_filter_damage": _first_int(
            flat,
            ("hard_filter_damage", "top1_damaged_by_hard_filter", "hard_filter_top1_damaged_by_hard_filter"),
        ),
        "bundle_dir": _first_text(flat, ("bundle_dir",)),
        "checkpoint": _first_text(flat, ("checkpoint", "best_checkpoint", "best_answer_checkpoint")),
        "decision": str(record.get("decision") or record.get("status") or ""),
        "note": str(record.get("note") or record.get("verdict") or ""),
    }


def _collect_records(ledger: Path, artifacts_dir: Path) -> list[dict[str, Any]]:
    raw: list[tuple[dict[str, Any], str]] = []
    for row in _load_jsonl(ledger):
        raw.append((row, str(ledger)))
    for path in sorted(artifacts_dir.glob("knowledge_compression*_summary.json")):
        data = _load_json(path)
        if not isinstance(data, dict):
            continue
        raw.append((data, str(path)))
        runs = data.get("runs")
        if isinstance(runs, list):
            for run in runs:
                if isinstance(run, dict):
                    raw.append((run, str(path) + "#runs"))
        latest = data.get("latest_result")
        if isinstance(latest, dict):
            raw.append((latest, str(path) + "#latest_result"))
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int | None]] = set()
    for row, source in raw:
        normalized = _normalize(row, source)
        if normalized is None:
            continue
        key = (normalized["label"], normalized.get("bundle_dir") or source, normalized.get("params"))
        if key in seen:
            continue
        seen.add(key)
        records.append(normalized)
    return records


def _max_by(records: list[dict[str, Any]], metric: str) -> dict[str, Any] | None:
    eligible = [row for row in records if isinstance(row.get(metric), (int, float))]
    if not eligible:
        return None
    return max(eligible, key=lambda row: float(row[metric]))


def _best_by_band(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    bands: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        bands[str(row["scale_band"])].append(row)
    out: dict[str, dict[str, Any]] = {}
    for band, rows in sorted(bands.items()):
        out[band] = {
            "count": len(rows),
            "best_exact": _max_by(rows, "exact_top1"),
            "best_answer": _max_by(rows, "answer_top1"),
            "best_bits_per_million_params": _max_by(rows, "verified_bits_per_million_params"),
            "best_bits_per_training_token": _max_by(rows, "verified_bits_per_training_token"),
        }
    return out


def _compact(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    keys = (
        "label",
        "params",
        "steps",
        "exact_top1",
        "answer_top1",
        "mrr",
        "verified_bits",
        "verified_bits_per_param",
        "verified_bits_per_million_params",
        "verified_bits_per_training_token",
        "estimated_training_retrieval_tokens",
        "training_param_steps_proxy",
        "training_param_token_proxy",
        "hard_filter_corrections",
        "bundle_dir",
        "checkpoint",
    )
    return {key: row.get(key) for key in keys if row.get(key) not in (None, "")}


def _pareto_frontier(records: list[dict[str, Any]], x_key: str, y_key: str) -> list[dict[str, Any]]:
    eligible = [
        row
        for row in records
        if isinstance(row.get(x_key), (int, float))
        and isinstance(row.get(y_key), (int, float))
        and float(row[x_key]) > 0.0
    ]
    eligible.sort(key=lambda row: (float(row[x_key]), -float(row[y_key]), str(row.get("label", ""))))
    best_y = float("-inf")
    frontier: list[dict[str, Any]] = []
    for row in eligible:
        y = float(row[y_key])
        if y > best_y:
            compact = _compact(row)
            if compact is not None:
                frontier.append(compact)
            best_y = y
    return frontier


def _top_efficiency(records: list[dict[str, Any]], metric: str, *, limit: int = 12) -> list[dict[str, Any]]:
    eligible = [row for row in records if isinstance(row.get(metric), (int, float))]
    eligible.sort(key=lambda row: float(row[metric]), reverse=True)
    return [compact for row in eligible[:limit] if (compact := _compact(row)) is not None]


def _write_markdown(mapping: dict[str, Any], path: Path) -> None:
    lines = [
        "# Tiny Intelligence Mapping",
        "",
        f"Generated: {mapping['generated_at']}",
        "",
        "This map treats intelligence narrowly: verified semantic access under fixed",
        "parameter, token, and runtime contracts. It is not yet a general intelligence",
        "benchmark, but it is a usable parameter-space map for compressed knowledge",
        "retrieval, binding, rule use, set operations, and verifier-assisted access.",
        "",
        "## Global Frontier",
        "",
    ]
    for name, row in mapping["frontier"].items():
        if row is None:
            continue
        lines.append(f"- {name}: `{row.get('label')}`")
        for key in (
            "params",
            "steps",
            "exact_top1",
            "answer_top1",
            "verified_bits_per_million_params",
            "verified_bits_per_training_token",
            "hard_filter_corrections",
        ):
            if key in row:
                lines.append(f"  - {key}: `{row[key]}`")
    lines.extend(["", "## Best By Parameter Band", ""])
    lines.extend(
        [
            "Rows can come from different curriculum scopes, so a frontier value is a",
            "measurement waypoint rather than a universal winner. Use the JSON records",
            "when comparing only runs from the same curriculum family.",
            "",
        ]
    )
    lines.append("| band | best exact | best answer | best bits/Mparam | best bits/token |")
    lines.append("|---|---|---|---|---|")
    for band, values in mapping["bands"].items():
        if band == "unknown":
            continue
        def cell(metric: str, value_key: str) -> str:
            row = values.get(metric)
            if not row:
                return ""
            value = row.get(value_key)
            label = row.get("label", "")
            return f"`{value}`<br>{label}" if value is not None else label
        lines.append(
            "| "
            + " | ".join(
                [
                    band,
                    cell("best_exact", "exact_top1"),
                    cell("best_answer", "answer_top1"),
                    cell("best_bits_per_million_params", "verified_bits_per_million_params"),
                    cell("best_bits_per_training_token", "verified_bits_per_training_token"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Compute Proxies",
            "",
            "The JSON map includes compute proxies for records with enough data:",
            "",
            "- `training_param_steps_proxy = params * steps`",
            "- `training_param_token_proxy = params * estimated_training_retrieval_tokens`",
            "- `verified_bits_per_param = verified_bits_per_million_params / 1_000_000`",
            "",
            "These are not hardware FLOPs. They are stable local proxies for comparing",
            "runs that share this training stack and curriculum family.",
            "",
            "## Pareto Frontiers",
            "",
            "Smallest parameter counts that improve answer top1:",
            "",
        ]
    )
    for row in mapping["pareto_frontiers"]["answer_top1_vs_params"][:12]:
        lines.append(
            f"- `{row.get('params')}` params: answer `{row.get('answer_top1')}` - {row.get('label')}"
        )
    lines.extend(["", "Smallest parameter counts that improve exact top1:", ""])
    for row in mapping["pareto_frontiers"]["exact_top1_vs_params"][:12]:
        lines.append(
            f"- `{row.get('params')}` params: exact `{row.get('exact_top1')}` - {row.get('label')}"
        )
    lines.extend(
        [
            "",
            "## Current Read",
            "",
            "- The current best pure-neural strict checkpoint remains Stage548.",
            "- Deterministic structured-key hard filtering is the best verified runtime contract.",
            "- Learned key-hash side channels are negative so far, including when active during the full Stage548-style continuation.",
            "- The map is strongest for semantic access and weakest for free-form decoding, planning, and broad transfer.",
            "- Runtime-only verifier rows without parameter counts are kept in the JSON records but omitted from the band table.",
            "",
            "## Source",
            "",
            f"- JSON map: `{mapping['json_output']}`",
            f"- Ledger: `{mapping['ledger']}`",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default="runs/ledgers/pocketpal_seq2seq_runs.jsonl")
    parser.add_argument("--artifacts-dir", default="runs/local/artifacts")
    parser.add_argument("--output-json", default="runs/local/artifacts/tiny_intelligence_mapping.json")
    parser.add_argument("--output-md", default="docs/tiny_intelligence_mapping.md")
    args = parser.parse_args()

    ledger = Path(args.ledger)
    artifacts_dir = Path(args.artifacts_dir)
    records = _collect_records(ledger, artifacts_dir)
    frontier = {
        "best_exact_top1": _compact(_max_by(records, "exact_top1")),
        "best_answer_top1": _compact(_max_by(records, "answer_top1")),
        "best_verified_bits_per_million_params": _compact(_max_by(records, "verified_bits_per_million_params")),
        "best_verified_bits_per_training_token": _compact(_max_by(records, "verified_bits_per_training_token")),
    }
    pareto_frontiers = {
        "answer_top1_vs_params": _pareto_frontier(records, "params", "answer_top1"),
        "exact_top1_vs_params": _pareto_frontier(records, "params", "exact_top1"),
        "verified_bits_per_param_vs_training_param_steps": _pareto_frontier(
            records,
            "training_param_steps_proxy",
            "verified_bits_per_param",
        ),
    }
    bands = {
        band: {key: _compact(value) if isinstance(value, dict) else value for key, value in data.items()}
        for band, data in _best_by_band(records).items()
    }
    mapping = {
        "artifact_kind": "tiny_intelligence_parameter_space_map",
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "scope": "verified semantic access, not general intelligence",
        "ledger": str(ledger),
        "artifacts_dir": str(artifacts_dir),
        "json_output": str(Path(args.output_json)),
        "record_count": len(records),
        "frontier": frontier,
        "pareto_frontiers": pareto_frontiers,
        "top_efficiency": {
            "verified_bits_per_million_params": _top_efficiency(records, "verified_bits_per_million_params"),
            "verified_bits_per_training_token": _top_efficiency(records, "verified_bits_per_training_token"),
        },
        "bands": bands,
        "records": records,
    }
    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown(mapping, Path(args.output_md))
    print(json.dumps({"records": len(records), "output_json": str(output_json), "output_md": args.output_md}, indent=2))


if __name__ == "__main__":
    main()
