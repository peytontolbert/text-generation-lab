#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "runs/local/artifacts/tiny_intelligence_mapping.json"
ARTIFACTS_DIR = ROOT / "runs/local/artifacts"
JSON_OUT = ROOT / "runs/local/artifacts/operation_bits_per_param_report.json"
DOC_OUT = ROOT / "docs/operation_bits_per_parameter.md"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _as_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _answer_by_operation(bundle: Path) -> dict[str, dict[str, float]]:
    answer_json = _load_json(bundle / "answer_equivalence_eval.json") or {}
    out: dict[str, dict[str, float]] = {}
    for op, stats in (answer_json.get("by_problem_ops") or {}).items():
        if not isinstance(stats, dict):
            continue
        out[str(op)] = {
            "answer_top1": float(stats.get("answer", stats.get("answer_top1", 0.0)) or 0.0),
            "exact_top1": float(stats.get("exact", stats.get("exact_top1", 0.0)) or 0.0),
            "evaluated_pairs": float(stats.get("n", stats.get("evaluated_pairs", 0.0)) or 0.0),
        }
    return out


def _eval_operation_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    params = int(record.get("params") or 0)
    if params <= 0:
        return []
    bundle = _as_path(record.get("bundle_dir"))
    if bundle is None or not bundle.exists():
        return []
    retrieval = _load_json(bundle / "retrieval_eval_full.json")
    if not retrieval:
        return []
    by_op = retrieval.get("by_operation") or {}
    if not isinstance(by_op, dict):
        return []
    answer_by_op = _answer_by_operation(bundle)
    bits_per_choice = (
        ((retrieval.get("verified_density") or {}).get("token_stats") or {}).get("bits_per_eval_card_choice")
        or math.log2(max(2, int(retrieval.get("evaluated_pairs") or 0)))
    )
    rows: list[dict[str, Any]] = []
    for op, stats in by_op.items():
        if not isinstance(stats, dict):
            continue
        n = float(stats.get("evaluated_pairs") or 0.0)
        if n <= 0:
            continue
        exact = float(stats.get("top1_accuracy") or 0.0)
        answer = float(stats.get("answer_top1_accuracy") or exact)
        if op in answer_by_op:
            answer = float(answer_by_op[op].get("answer_top1", answer))
            exact = float(answer_by_op[op].get("exact_top1", exact))
            n = float(answer_by_op[op].get("evaluated_pairs", n) or n)
        exact_bits = n * exact * float(bits_per_choice)
        answer_bits = n * answer * float(bits_per_choice)
        perfect_bits = n * float(bits_per_choice)
        rows.append(
            {
                "label": record.get("label"),
                "bundle_dir": record.get("bundle_dir"),
                "operation": str(op),
                "params": params,
                "scale_band": record.get("scale_band"),
                "steps": record.get("steps"),
                "evaluated_pairs": int(n),
                "exact_top1": exact,
                "answer_top1": answer,
                "exact_bits_per_param": exact_bits / params,
                "answer_bits_per_param": answer_bits / params,
                "perfect_bits_per_param": perfect_bits / params,
                "missing_exact_bits_per_param": (perfect_bits - exact_bits) / params,
                "missing_answer_bits_per_param": (perfect_bits - answer_bits) / params,
            }
        )
    return rows


def _bundle_record(bundle: Path) -> dict[str, Any] | None:
    manifest = _load_json(bundle / "agentkernel_lite_encdec_manifest.json")
    retrieval = _load_json(bundle / "retrieval_eval_full.json")
    if not manifest or not retrieval:
        return None
    training = manifest.get("training_summary") or {}
    params = int(manifest.get("parameter_count") or training.get("parameter_count") or 0)
    if params <= 0:
        return None
    return {
        "label": bundle.name,
        "bundle_dir": str(bundle.relative_to(ROOT)),
        "params": params,
        "steps": int(training.get("completed_steps") or training.get("max_steps") or 0),
        "scale_band": _scale_band(params),
    }


def _scale_band(params: int) -> str:
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


def _top(rows: list[dict[str, Any]], key: str, n: int = 8) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda item: float(item.get(key) or 0.0), reverse=True)[:n]


def _composability_by_band(operation_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows_by_band: dict[str, list[dict[str, Any]]] = {}
    for row in operation_rows:
        rows_by_band.setdefault(str(row.get("scale_band") or "unknown"), []).append(row)

    out: dict[str, Any] = {}
    for band, rows in sorted(rows_by_band.items()):
        best_by_operation: dict[str, dict[str, Any]] = {}
        run_sums: dict[str, dict[str, Any]] = {}
        for row in rows:
            op = str(row["operation"])
            if op not in best_by_operation or float(row["answer_bits_per_param"]) > float(best_by_operation[op]["answer_bits_per_param"]):
                best_by_operation[op] = row
            label = str(row["label"])
            entry = run_sums.setdefault(
                label,
                {
                    "label": label,
                    "bundle_dir": row.get("bundle_dir"),
                    "params": row.get("params"),
                    "scale_band": band,
                    "answer_bits_per_param_sum": 0.0,
                    "exact_bits_per_param_sum": 0.0,
                    "operation_count": 0,
                    "min_answer_top1": 1.0,
                },
            )
            entry["answer_bits_per_param_sum"] += float(row["answer_bits_per_param"])
            entry["exact_bits_per_param_sum"] += float(row["exact_bits_per_param"])
            entry["operation_count"] += 1
            entry["min_answer_top1"] = min(float(entry["min_answer_top1"]), float(row["answer_top1"]))

        oracle_sum = sum(float(row["answer_bits_per_param"]) for row in best_by_operation.values())
        best_run = max(run_sums.values(), key=lambda item: float(item["answer_bits_per_param_sum"]))
        reliable_runs = [item for item in run_sums.values() if float(item["min_answer_top1"]) >= 0.999]
        best_reliable_run = (
            max(reliable_runs, key=lambda item: float(item["answer_bits_per_param_sum"]))
            if reliable_runs
            else None
        )
        out[band] = {
            "operation_count": len(best_by_operation),
            "operation_oracle_answer_bits_per_param": oracle_sum,
            "best_single_run_answer_bits_per_param": best_run,
            "best_reliable_single_run_answer_bits_per_param": best_reliable_run,
            "noncomposable_oracle_gap_vs_best_run": oracle_sum - float(best_run["answer_bits_per_param_sum"]),
            "noncomposable_oracle_gap_fraction": (
                (oracle_sum - float(best_run["answer_bits_per_param_sum"])) / oracle_sum
                if oracle_sum
                else 0.0
            ),
            "oracle_operation_sources": {
                op: {
                    "label": row["label"],
                    "answer_bits_per_param": row["answer_bits_per_param"],
                    "answer_top1": row["answer_top1"],
                }
                for op, row in sorted(best_by_operation.items())
            },
        }
    return out


def build() -> dict[str, Any]:
    source = _load_json(MAP_PATH) or {}
    records = source.get("records") or []
    operation_rows: list[dict[str, Any]] = []
    seen_bundles: set[str] = set()
    for record in records:
        if isinstance(record, dict):
            if record.get("bundle_dir"):
                seen_bundles.add(str(record["bundle_dir"]))
            operation_rows.extend(_eval_operation_rows(record))
    for eval_json in sorted(ARTIFACTS_DIR.glob("*/retrieval_eval_full.json")):
        bundle = eval_json.parent
        rel = str(bundle.relative_to(ROOT))
        if rel in seen_bundles:
            continue
        record = _bundle_record(bundle)
        if record is None:
            continue
        seen_bundles.add(rel)
        operation_rows.extend(_eval_operation_rows(record))

    by_operation: dict[str, list[dict[str, Any]]] = {}
    for row in operation_rows:
        by_operation.setdefault(str(row["operation"]), []).append(row)

    operation_frontiers: dict[str, dict[str, Any]] = {}
    for op, rows in sorted(by_operation.items()):
        exact_reliable = [r for r in rows if float(r["exact_top1"]) >= 0.999]
        answer_reliable = [r for r in rows if float(r["answer_top1"]) >= 0.999]
        operation_frontiers[op] = {
            "row_count": len(rows),
            "best_raw_answer_bits_per_param": _top(rows, "answer_bits_per_param", 5),
            "best_reliable_answer_bits_per_param": _top(answer_reliable, "answer_bits_per_param", 5),
            "best_reliable_exact_bits_per_param": _top(exact_reliable, "exact_bits_per_param", 5),
            "median_answer_bits_per_param": median(float(r["answer_bits_per_param"]) for r in rows),
        }

    focus_needles = ("stage525", "stage508", "stage548", "stage579")
    focus_rows = [
        r
        for r in operation_rows
        if any(needle in str(r.get("label", "")) or needle in str(r.get("bundle_dir", "")) for needle in focus_needles)
    ]
    missing_by_focus: dict[str, list[dict[str, Any]]] = {}
    for row in focus_rows:
        missing_by_focus.setdefault(str(row["label"]), []).append(row)
    missing_by_focus = {
        label: _top(rows, "missing_answer_bits_per_param", 8)
        for label, rows in sorted(missing_by_focus.items())
    }

    composability = _composability_by_band(operation_rows)
    band_16k = composability.get("10k-20k") or {}
    band_20k = composability.get("20k-30k") or {}
    findings = [
        "Run-level bits/param rewards small models with many near-correct operations, so reliability thresholds must be tracked separately.",
        "Operation-level frontiers show what each tiny run can solve, but the best operations are not necessarily solved simultaneously in one checkpoint.",
        "This report uses batch-local retrieval evals where available; strict full-corpus operation-gated eval remains the promotion-grade reliability check.",
        "The 16k frontier keeps high raw operation bits/param on most operations but loses its missing bits in composite membership/count operations.",
        "The 26k frontier gives up raw density but clears the reliability threshold across the full operation mix.",
        "Stage579 confirms that lowering target text entropy without preserving discriminative anchors destroys operation-level bits/param.",
    ]
    if band_16k:
        findings.append(
            "The 16k operation-oracle gap is tiny "
            f"({float(band_16k.get('noncomposable_oracle_gap_fraction') or 0.0):.3%}), "
            "so the remaining issue is not mainly that different checkpoints solve different operations; "
            "the best 16k checkpoint is a few residual bits short of joint reliability."
        )
    if band_20k:
        reliable = band_20k.get("best_reliable_single_run_answer_bits_per_param") or {}
        best = band_20k.get("best_single_run_answer_bits_per_param") or {}
        if reliable and best:
            findings.append(
                "In the 20k-30k band, the raw-density leader is not the reliability leader: "
                f"{best.get('label')} has higher summed operation bits/param, while "
                f"{reliable.get('label')} is the reliable checkpoint."
            )

    report = {
        "artifact_kind": "operation_bits_per_parameter_report",
        "source_map": str(MAP_PATH.relative_to(ROOT)),
        "operation_row_count": len(operation_rows),
        "operation_count": len(by_operation),
        "composability_by_band": composability,
        "operation_frontiers": operation_frontiers,
        "top_operation_answer_bits_per_param": _top(operation_rows, "answer_bits_per_param", 20),
        "focus_missing_answer_bits_per_param": missing_by_focus,
        "findings": findings,
    }
    return report


def write_doc(report: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Operation Bits Per Parameter")
    lines.append("")
    lines.append("This decomposes verified semantic bits/parameter by operation.")
    lines.append("It uses each operation's evaluated pair count, exact/answer top1, and the eval-card choice entropy from the run artifact.")
    lines.append("")
    lines.append("## Main Findings")
    lines.append("")
    for finding in report["findings"]:
        lines.append(f"- {finding}")
    lines.append("")
    lines.append("## Highest Operation-Level Answer Bits/Param")
    lines.append("")
    for row in report["top_operation_answer_bits_per_param"][:12]:
        lines.append(
            f"- `{row['answer_bits_per_param']:.6g}` bits/param, answer `{row['answer_top1']}`, "
            f"`{row['operation']}`: {row['label']}"
        )
    lines.append("")
    lines.append("## Composability Gap")
    lines.append("")
    lines.append("The operation oracle picks the best checkpoint separately for each operation inside a scale band.")
    lines.append("The single-run score is what one checkpoint actually contains.")
    lines.append("")
    lines.append("| band | operation oracle answer bits/param | best single run | gap | gap fraction | best reliable run |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for band, summary in sorted(report["composability_by_band"].items()):
        best = summary["best_single_run_answer_bits_per_param"]
        reliable = summary["best_reliable_single_run_answer_bits_per_param"]
        reliable_label = reliable["label"] if reliable else ""
        lines.append(
            f"| {band} | {summary['operation_oracle_answer_bits_per_param']:.6g} | "
            f"{best['answer_bits_per_param_sum']:.6g} | "
            f"{summary['noncomposable_oracle_gap_vs_best_run']:.6g} | "
            f"{summary['noncomposable_oracle_gap_fraction']:.3f} | `{reliable_label}` |"
        )
    lines.append("")
    lines.append("## Reliable Operation Frontiers")
    lines.append("")
    lines.append("| operation | best reliable answer bits/param | run | params | answer |")
    lines.append("|---|---:|---|---:|---:|")
    for op, summary in sorted(report["operation_frontiers"].items()):
        leaders = summary["best_reliable_answer_bits_per_param"]
        if leaders:
            best = leaders[0]
            lines.append(
                f"| `{op}` | {best['answer_bits_per_param']:.6g} | `{best['label']}` | "
                f"{best['params']} | {best['answer_top1']} |"
            )
        else:
            lines.append(f"| `{op}` |  |  |  |  |")
    lines.append("")
    lines.append("## Missing Bits In Focus Runs")
    lines.append("")
    for label, rows in report["focus_missing_answer_bits_per_param"].items():
        lines.append(f"### {label}")
        if not rows:
            lines.append("")
            continue
        for row in rows[:6]:
            lines.append(
                f"- `{row['missing_answer_bits_per_param']:.6g}` missing answer bits/param, "
                f"answer `{row['answer_top1']}`: `{row['operation']}`"
            )
        lines.append("")
    lines.append("## Source")
    lines.append("")
    lines.append(f"- JSON: `{JSON_OUT.relative_to(ROOT)}`")
    lines.append(f"- Source map: `{report['source_map']}`")
    DOC_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    report = build()
    JSON_OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(report)
    print(json.dumps({"json": str(JSON_OUT), "doc": str(DOC_OUT), "operation_rows": report["operation_row_count"]}, indent=2))


if __name__ == "__main__":
    main()
