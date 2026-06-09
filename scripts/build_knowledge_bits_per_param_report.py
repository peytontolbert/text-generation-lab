#!/usr/bin/env python3
"""Generate a focused knowledge-bits-per-parameter report."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _has_number(row: dict[str, Any], key: str) -> bool:
    return isinstance(row.get(key), (int, float)) and not isinstance(row.get(key), bool)


def _compact(row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "label",
        "run_id",
        "params",
        "scale_band",
        "steps",
        "exact_top1",
        "answer_top1",
        "mrr",
        "verified_bits_per_param",
        "verified_bits_per_million_params",
        "verified_bits_per_training_token",
        "training_param_steps_proxy",
        "training_param_token_proxy",
        "bundle_dir",
        "checkpoint",
        "note",
    )
    return {key: row.get(key) for key in keys if row.get(key) not in (None, "")}


def _top(rows: list[dict[str, Any]], *, key: str, limit: int = 20) -> list[dict[str, Any]]:
    eligible = [row for row in rows if _has_number(row, key)]
    eligible.sort(key=lambda row: float(row[key]), reverse=True)
    return [_compact(row) for row in eligible[:limit]]


def _threshold(rows: list[dict[str, Any]], *, exact: float, answer: float) -> list[dict[str, Any]]:
    eligible = [
        row
        for row in rows
        if _has_number(row, "verified_bits_per_param")
        and float(row.get("exact_top1") or 0.0) >= exact
        and float(row.get("answer_top1") or 0.0) >= answer
    ]
    eligible.sort(key=lambda row: float(row["verified_bits_per_param"]), reverse=True)
    return [_compact(row) for row in eligible[:20]]


def _band_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bands: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        bands[str(row.get("scale_band") or "unknown")].append(row)
    out: dict[str, Any] = {}
    for band, band_rows in sorted(bands.items()):
        values = [float(row["verified_bits_per_param"]) for row in band_rows if _has_number(row, "verified_bits_per_param")]
        if not values:
            continue
        best = max(band_rows, key=lambda row: float(row.get("verified_bits_per_param") or -1.0))
        out[band] = {
            "records": len(values),
            "median_verified_bits_per_param": median(values),
            "best": _compact(best),
        }
    return out


def _design_bucket(label: str) -> str:
    text = label.lower()
    if "compact_false" in text or "false_claim" in text:
        return "compact_false_claim"
    if "direct_fact_key" in text or "direct_fact" in text:
        return "direct_fact_keying"
    if "compact_reverse" in text or "reverse" in text:
        return "compact_reverse_or_reverse_replay"
    if "rule_replay" in text or "rule_field" in text or "rule_key" in text:
        return "rule_replay_or_rule_keying"
    if "retrieval32" in text:
        return "retrieval_head_dim_32"
    if "keyhash" in text or "key_hash" in text:
        return "learned_key_hash_negative"
    if "anchor" in text:
        return "auxiliary_anchor_negative"
    return "other"


def _design_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if _has_number(row, "verified_bits_per_param"):
            buckets[_design_bucket(str(row.get("label") or row.get("run_id") or ""))].append(row)
    out: dict[str, Any] = {}
    for bucket, items in sorted(buckets.items()):
        best = max(items, key=lambda row: float(row.get("verified_bits_per_param") or -1.0))
        out[bucket] = {
            "records": len(items),
            "best": _compact(best),
        }
    return out


def _write_md(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Knowledge Bits Per Parameter",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "This report ranks runs by verified semantic bits per raw parameter.",
        "Higher is better only within comparable curriculum families; reliability",
        "threshold sections separate dense-but-imperfect runs from high-confidence",
        "frontier candidates.",
        "",
        "## Main Findings",
        "",
        "- The highest raw bits/param point is in the 16k band, but it is not answer-perfect.",
        "- The best exact+answer-perfect high-reliability point is currently the 26k Stage508 run.",
        "- Compact false-claim/card designs and direct keying move the reliability frontier downward.",
        "- Learned key hashes and auxiliary anchors are negative for Stage548 because they collapse membership proof geometry.",
        "",
        "## Overall Leaders",
        "",
    ]
    for row in report["top_verified_bits_per_param"][:10]:
        lines.append(
            f"- `{row['verified_bits_per_param']:.6g}` bits/param, `{row.get('params')}` params: {row.get('label')}"
        )
    lines.extend(["", "## High-Reliability Leaders", ""])
    for name, rows in report["threshold_leaders"].items():
        lines.append(f"### {name}")
        for row in rows[:8]:
            lines.append(
                f"- `{row['verified_bits_per_param']:.6g}` bits/param, exact `{row.get('exact_top1')}`, answer `{row.get('answer_top1')}`, `{row.get('params')}` params: {row.get('label')}"
            )
        lines.append("")
    lines.extend(["## Best By Band", ""])
    lines.append("| band | median bits/param | best bits/param | best run |")
    lines.append("|---|---:|---:|---|")
    for band, data in report["band_summary"].items():
        best = data["best"]
        lines.append(
            f"| {band} | {data['median_verified_bits_per_param']:.6g} | {best['verified_bits_per_param']:.6g} | {best.get('label')} |"
        )
    lines.extend(["", "## Target Design Buckets", ""])
    for bucket, data in report["target_design_summary"].items():
        best = data["best"]
        lines.append(
            f"- {bucket}: best `{best['verified_bits_per_param']:.6g}` bits/param from `{best.get('label')}`"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map-json", default="runs/local/artifacts/tiny_intelligence_mapping.json")
    parser.add_argument("--output-json", default="runs/local/artifacts/knowledge_bits_per_param_report.json")
    parser.add_argument("--output-md", default="docs/knowledge_bits_per_parameter.md")
    args = parser.parse_args()

    mapping = _load(Path(args.map_json))
    rows = [
        row
        for row in mapping.get("records", [])
        if _has_number(row, "verified_bits_per_param") and _has_number(row, "params")
    ]
    report = {
        "artifact_kind": "knowledge_bits_per_parameter_report",
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_map": str(Path(args.map_json)),
        "record_count": len(rows),
        "top_verified_bits_per_param": _top(rows, key="verified_bits_per_param", limit=30),
        "top_verified_bits_per_training_token": _top(rows, key="verified_bits_per_training_token", limit=20),
        "threshold_leaders": {
            "answer>=0.999": _threshold(rows, exact=0.0, answer=0.999),
            "exact>=0.999": _threshold(rows, exact=0.999, answer=0.0),
            "exact>=0.999_and_answer>=0.999": _threshold(rows, exact=0.999, answer=0.999),
        },
        "band_summary": _band_summary(rows),
        "target_design_summary": _design_summary(rows),
    }
    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_md(report, Path(args.output_md))
    print(json.dumps({"records": len(rows), "output_json": str(output_json), "output_md": args.output_md}, indent=2))


if __name__ == "__main__":
    main()
