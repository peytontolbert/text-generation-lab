#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TINY_MAP = ROOT / "runs/local/artifacts/tiny_intelligence_mapping.json"
JSON_OUT = ROOT / "runs/local/artifacts/scale_sweep_intelligence_density.json"
DOC_OUT = ROOT / "docs/scale_sweep_intelligence_density.md"


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _best(rows: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    valid = [row for row in rows if _num(row.get(key)) is not None]
    if not valid:
        return None
    return max(valid, key=lambda row: float(row[key]))


def _compact(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    keep = (
        "label",
        "params",
        "scale_band",
        "steps",
        "exact_top1",
        "answer_top1",
        "mrr",
        "verified_bits_per_param",
        "verified_bits_per_training_token",
        "training_param_steps_proxy",
        "bundle_dir",
        "note",
    )
    return {key: row.get(key) for key in keep if key in row}


def _regime(params: int) -> str:
    if params < 10_000:
        return "tokenizer_floor_probe"
    if params < 20_000:
        return "raw_density_frontier"
    if params < 30_000:
        return "reliability_breakpoint"
    if params < 100_000:
        return "reliable_but_density_declines"
    if params < 1_000_000:
        return "overcapacity_for_current_curriculum"
    return "large_overcapacity_reference"


def build() -> dict[str, Any]:
    source = _load(TINY_MAP)
    records = [
        row
        for row in source.get("records", [])
        if isinstance(row, dict) and isinstance(row.get("params"), int)
    ]
    by_band: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_param: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_band[str(row.get("scale_band") or "unknown")].append(row)
        by_param[int(row["params"])].append(row)

    param_points: list[dict[str, Any]] = []
    for params, rows in sorted(by_param.items()):
        best_exact = _best(rows, "exact_top1")
        best_answer = _best(rows, "answer_top1")
        best_bpp = _best(rows, "verified_bits_per_param")
        best_token = _best(rows, "verified_bits_per_training_token")
        param_points.append(
            {
                "params": params,
                "regime": _regime(params),
                "record_count": len(rows),
                "best_exact": _compact(best_exact),
                "best_answer": _compact(best_answer),
                "best_bits_per_param": _compact(best_bpp),
                "best_bits_per_training_token": _compact(best_token),
            }
        )

    band_summary: dict[str, Any] = {}
    for band, rows in sorted(by_band.items()):
        bpps = [float(row["verified_bits_per_param"]) for row in rows if _num(row.get("verified_bits_per_param")) is not None]
        band_summary[band] = {
            "record_count": len(rows),
            "best_exact": _compact(_best(rows, "exact_top1")),
            "best_answer": _compact(_best(rows, "answer_top1")),
            "best_bits_per_param": _compact(_best(rows, "verified_bits_per_param")),
            "median_bits_per_param": median(bpps) if bpps else None,
        }

    reliable = [
        row
        for row in records
        if _num(row.get("exact_top1")) is not None
        and _num(row.get("answer_top1")) is not None
        and float(row["exact_top1"]) >= 0.999
        and float(row["answer_top1"]) >= 0.999
    ]
    answer_999 = [
        row
        for row in records
        if _num(row.get("answer_top1")) is not None and float(row["answer_top1"]) >= 0.999
    ]
    exact_999 = [
        row
        for row in records
        if _num(row.get("exact_top1")) is not None and float(row["exact_top1"]) >= 0.999
    ]

    report = {
        "artifact_kind": "scale_sweep_intelligence_density",
        "source_map": str(TINY_MAP.relative_to(ROOT)),
        "record_count": len(records),
        "param_point_count": len(param_points),
        "band_summary": band_summary,
        "param_points": param_points,
        "breakpoints": {
            "smallest_answer_999": _compact(min(answer_999, key=lambda row: int(row["params"])) if answer_999 else None),
            "smallest_exact_999": _compact(min(exact_999, key=lambda row: int(row["params"])) if exact_999 else None),
            "smallest_exact_and_answer_999": _compact(min(reliable, key=lambda row: int(row["params"])) if reliable else None),
            "raw_density_leader": _compact(_best(records, "verified_bits_per_param")),
            "training_token_efficiency_leader": _compact(_best(records, "verified_bits_per_training_token")),
        },
        "regime_interpretation": [
            {
                "regime": "tokenizer_floor_probe",
                "meaning": "Below 10k actual params, embeddings/tokenizer dominate. Useful for lower-bound geometry, not reliable intelligence.",
            },
            {
                "regime": "raw_density_frontier",
                "meaning": "10k-20k contains the highest raw KBPP points. It shows how much knowledge can fit, but misses residual reliability bits.",
            },
            {
                "regime": "reliability_breakpoint",
                "meaning": "20k-30k is the current first reliable region for this curriculum: enough width to bind composite knowledge jointly.",
            },
            {
                "regime": "reliable_but_density_declines",
                "meaning": "30k-100k preserves reliability with lower density. Useful for checking target-design breakpoints.",
            },
            {
                "regime": "overcapacity_for_current_curriculum",
                "meaning": "Above 100k the curriculum saturates; bigger models score well but teach less about density unless tasks get broader/harder.",
            },
        ],
        "main_findings": [
            "The sweep matters because each scale reveals a different failure mode: tokenizer floor, raw density, reliability breakpoint, and overcapacity.",
            "The current reliable breakpoint is not at 100M; it is already around 23k-26k for the controlled curriculum depending on evaluator strictness, which means the curriculum is too narrow to explain 100M general intelligence by itself.",
            "For general intelligence, the sweep must be repeated on broader knowledge-unit benchmarks so the 100M rung is not overcapacity.",
            "The 1k-to-100M program should be treated as a microscope: tiny rungs reveal target entropy and representation failures before expensive larger runs.",
        ],
    }
    return report


def write_doc(report: dict[str, Any]) -> None:
    lines = [
        "# Scale Sweep Intelligence Density",
        "",
        "This maps the whole model sweep, not just the 100M target.",
        "Each scale band is evidence about a different part of model intelligence density.",
        "",
        "## Breakpoints",
        "",
    ]
    for key, value in report["breakpoints"].items():
        if value:
            lines.append(
                f"- `{key}`: `{value.get('label')}` at `{value.get('params')}` params "
                f"(exact `{value.get('exact_top1')}`, answer `{value.get('answer_top1')}`, "
                f"bits/param `{value.get('verified_bits_per_param')}`)"
            )
    lines.extend(["", "## Regimes", ""])
    for item in report["regime_interpretation"]:
        lines.append(f"- `{item['regime']}`: {item['meaning']}")
    lines.extend(["", "## Best By Parameter Point", ""])
    lines.append("| params | regime | best answer | best bits/param | best exact |")
    lines.append("|---:|---|---|---|---|")
    for point in report["param_points"]:
        best_answer = point["best_answer"] or {}
        best_bpp = point["best_bits_per_param"] or {}
        best_exact = point["best_exact"] or {}
        lines.append(
            f"| {point['params']} | `{point['regime']}` | "
            f"`{best_answer.get('answer_top1')}` {best_answer.get('label', '')} | "
            f"`{best_bpp.get('verified_bits_per_param')}` {best_bpp.get('label', '')} | "
            f"`{best_exact.get('exact_top1')}` {best_exact.get('label', '')} |"
        )
    lines.extend(["", "## Main Findings", ""])
    for item in report["main_findings"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Source",
            "",
            f"- JSON: `{JSON_OUT.relative_to(ROOT)}`",
            f"- Tiny map: `{report['source_map']}`",
        ]
    )
    DOC_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    report = build()
    JSON_OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(report)
    print(json.dumps({"json": str(JSON_OUT), "doc": str(DOC_OUT), "param_points": report["param_point_count"]}, indent=2))


if __name__ == "__main__":
    main()
