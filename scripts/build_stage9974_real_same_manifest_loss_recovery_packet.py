#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9974
NAME = "stage9974_real_same_manifest_loss_recovery_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "real_same_manifest_loss_recovery_packet.json"
ROWS = OUT_DIR / "real_same_manifest_loss_recovery_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_SAME_MANIFEST_LOSS_RECOVERY_PACKET_STAGE9974.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

COMPARE = ROOT / "runs/local/artifacts/stage9973_blended_weak_language_same_manifest_comparison_audit/blended_weak_language_same_manifest_comparison_rows.jsonl"
MANIFEST = ROOT / "runs/local/artifacts/stage9964_blended_weak_language_execution_review/review_manifests/edit_localization.jsonl"

TARGET_LANGS = {"python", "c_cpp"}
TARGET_SPLITS = {"eval", "strict_eval"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def root_row_id(row_id: str) -> str:
    parts = row_id.split("::")
    if len(parts) >= 2:
        return "::".join(parts[:-1]) if parts[-1] in {"mixed_replay", "positive_original", "positive_original::eval_replay"} else row_id
    return row_id


def comparison_buckets() -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    rows = load_jsonl(COMPARE)
    selected: list[dict[str, Any]] = []
    counters: dict[str, dict[str, int]] = defaultdict(lambda: {"100m_wrong_gemma_right": 0, "both_wrong": 0})
    for row in rows:
        language = str(row.get("language_family") or "")
        split = str(row.get("split") or "")
        if language not in TARGET_LANGS or split not in TARGET_SPLITS:
            continue
        hm = bool(row.get("hundred_m_correct"))
        gm = bool(row.get("gemma_correct"))
        if hm and not gm:
            continue
        enriched = dict(row)
        if (not hm) and gm:
            enriched["recovery_reason"] = "gemma_advantage_recovery"
            counters[f"{language}:{split}"]["100m_wrong_gemma_right"] += 1
        else:
            enriched["recovery_reason"] = "hundred_m_general_miss_recovery"
            counters[f"{language}:{split}"]["both_wrong"] += 1
        selected.append(enriched)
    return selected, counters


def build_packet() -> dict[str, Any]:
    compare_rows, counters = comparison_buckets()
    manifest_rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    by_row_id = {str(row.get("row_id") or ""): row for row in manifest_rows}

    roots_to_keep = {str(row.get("row_id") or "") for row in compare_rows}
    selected_manifest_rows: list[dict[str, Any]] = []
    for row_id in sorted(roots_to_keep):
        if row_id not in by_row_id:
            failures.append(f"missing_manifest_row:{row_id}")
            continue
        row = dict(by_row_id[row_id])
        compare = next(item for item in compare_rows if str(item.get("row_id") or "") == row_id)
        row["recovery_reason"] = compare["recovery_reason"]
        row["recovery_language_family"] = compare["language_family"]
        row["recovery_split"] = compare["split"]
        row["recovery_expected_label"] = compare["expected_label"]
        row["recovery_hundred_m_pred"] = compare["hundred_m_pred"]
        row["recovery_gemma_pred"] = compare["gemma_pred"]
        selected_manifest_rows.append(row)

    language_counts = Counter(str(row.get("recovery_language_family") or "") for row in selected_manifest_rows)
    split_counts = Counter(str(row.get("recovery_split") or "") for row in selected_manifest_rows)
    reason_counts = Counter(str(row.get("recovery_reason") or "") for row in selected_manifest_rows)

    metrics = {
        "rows": len(selected_manifest_rows),
        "language_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "target_languages": sorted(TARGET_LANGS),
        "worst_bucket_counts": {key: value for key, value in sorted(counters.items())},
    }
    if metrics["rows"] <= 0:
        failures.append("no_selected_rows")
    if "python" not in language_counts:
        failures.append("python_not_present")
    if "c_cpp" not in language_counts:
        failures.append("c_cpp_not_present")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "selected_rows": selected_manifest_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    PACKET.write_text(json.dumps({
        "stage": STAGE,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "failures": built["failures"],
        "authority": dict(AUTHORITY_CLOSED),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(ROWS, built["selected_rows"])
    next_step = "Blend this real post-Gemma loss packet into the next edit-localization cycle, with priority on python and the c_cpp strict rows that still lose after the weak-language recovery mix."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "packet": display(PACKET),
            "rows": display(ROWS),
            "doc": display(DOC),
        },
        "decision": "Materialized a real post-comparison recovery packet from the actual stage9973 weak-language losses, targeting python broadly and the c_cpp strict regression instead of relying on pre-execution guesses.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9974 Real Same-Manifest Loss Recovery Packet",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows: `{built['metrics']['rows']}`",
        f"Languages: `{built['metrics']['language_counts']}`",
        f"Reasons: `{built['metrics']['reason_counts']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "metrics": built["metrics"],
        "failures": built["failures"],
    }, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
