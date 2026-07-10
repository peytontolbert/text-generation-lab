#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9740
NAME = "stage9740_verifier_repair_label_aligned_language_slice_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "verifier_repair_label_aligned_language_slice_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "VERIFIER_REPAIR_LABEL_ALIGNED_LANGUAGE_SLICE_AUDIT_STAGE9740.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9739_multilingual_verifier_repair_label_aligned_execution_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9738_multilingual_verifier_repair_label_aligned_package/multilingual_verifier_repair_label_aligned.jsonl"
LOGITS = ROOT / "runs/local/artifacts/stage9739_multilingual_verifier_repair_label_aligned_exec/row_field_logits.jsonl"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
SPLITS = ["eval", "strict_eval"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    manifest = {row["row_id"]: row["language_family"] for row in load_jsonl(MANIFEST)}
    logits = load_jsonl(LOGITS)
    grouped = defaultdict(lambda: defaultdict(lambda: {"rows": 0, "correct": 0}))
    failures: list[str] = []
    for row in logits:
        row_id = row.get("row_id")
        if row_id not in manifest:
            failures.append("unmapped_row_id")
            continue
        lang = manifest[row_id]
        split = row.get("split")
        grouped[lang][split]["rows"] += 1
        grouped[lang][split]["correct"] += int(row.get("correct") is True)
    language_slices = {}
    for lang in LANGS:
        language_slices[lang] = {}
        for split in SPLITS:
            rows = grouped[lang][split]["rows"]
            correct = grouped[lang][split]["correct"]
            if rows != 9:
                failures.append(f"unexpected_rows:{lang}:{split}")
            language_slices[lang][split] = {
                "rows": rows,
                "correct": correct,
                "exact": (correct / rows) if rows else None,
            }
    if source.get("passed") is not True:
        failures.append("stage9739_not_passed")
    return {
        "passed": not failures,
        "failures": failures,
        "language_slices": language_slices,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Compare the three label-aligned structured surfaces together and prioritize the strongest multilingual path for later Gemma packaging."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED)},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Recorded the per-language effect of the label-aligned verifier-repair intervention.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9740 Verifier Repair Label-Aligned Language Slice Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Language slices: `{audit['language_slices']}`",
        "",
        "This stage confirms whether the label-aligned verifier-repair improvement is multilingual rather than concentrated in a single language family.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": audit["failures"], "next_best_step": next_step}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
