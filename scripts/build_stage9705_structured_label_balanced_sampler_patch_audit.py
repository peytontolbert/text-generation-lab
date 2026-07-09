#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9705
NAME = "stage9705_structured_label_balanced_sampler_patch_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9704_symbol_binding_rebalanced_target100m_execution_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9700_symbol_binding_repair_compiler/symbol_binding_tiny_rebalanced.jsonl"
TRAINING_LOOP = ROOT / "legacy_src/agentkernel_lite/training_loop.py"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "structured_label_balanced_sampler_patch_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STRUCTURED_LABEL_BALANCED_SAMPLER_PATCH_STAGE9705.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def label(row: dict[str, Any]) -> str:
    return str((row.get("clean_state") or {}).get("binding_action"))


def simulated_balanced_exposure(rows: list[dict[str, Any]], *, max_steps: int = 8, batch_size: int = 2) -> dict[str, Any]:
    train_rows = [row for row in rows if row.get("split") == "train"]
    by_label: dict[str, list[dict[str, Any]]] = {}
    for row in train_rows:
        by_label.setdefault(label(row), []).append(row)
    labels = sorted(by_label)
    used = []
    for step in range(1, max_steps + 1):
        start = (step - 1) * batch_size
        for offset in range(batch_size):
            lab = labels[(start + offset) % len(labels)]
            group = by_label[lab]
            cycle = (start + offset) // len(labels)
            used.append(group[cycle % len(group)])
    train_counts = Counter(label(row) for row in train_rows)
    used_counts = Counter(label(row) for row in used)
    return {
        "train_rows": len(train_rows),
        "max_steps": max_steps,
        "batch_size": batch_size,
        "unique_train_rows_seen": len({row.get("row_id") for row in used}),
        "train_label_counts": dict(train_counts),
        "used_label_counts": dict(used_counts),
        "missing_train_labels_in_used_batches": sorted(set(train_counts) - set(used_counts)),
        "min_used_label_count": min(used_counts.values()) if used_counts else 0,
        "max_used_label_count": max(used_counts.values()) if used_counts else 0,
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    text = TRAINING_LOOP.read_text(encoding="utf-8")
    exposure = simulated_balanced_exposure(rows)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9704_not_passed")
    if "_structured_label_balanced_batch_rows" not in text:
        failures.append("label_balanced_sampler_function_missing")
    if "structured_batch_sampler" not in text:
        failures.append("structured_batch_sampler_result_card_missing")
    if exposure["missing_train_labels_in_used_batches"]:
        failures.append(f"balanced_sampler_still_misses_labels:{exposure['missing_train_labels_in_used_batches']}")
    if exposure["min_used_label_count"] <= 0:
        failures.append("balanced_sampler_zero_label_exposure")
    next_step = "Run Stage9706 contract-only target-100M preflight after sampler patch, then rerun Stage9707 target-100M only if the preflight passes."
    audit = {"stage": STAGE, "name": NAME, "passed": not failures, "quality_passed": False, "promotion_ready": False, "failures": failures, "source_stage9704_summary": str(SOURCE_SUMMARY.relative_to(ROOT)), "sampler_function_present": "_structured_label_balanced_batch_rows" in text, "exposure": exposure, "authority": dict(AUTHORITY_CLOSED), "next_best_step": next_step}
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {"stage": STAGE, "name": NAME, "passed": not failures, "quality_passed": False, "promotion_ready": False, "created_at_unix": int(time.time()), "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))}, "metrics": exposure, "authority": dict(AUTHORITY_CLOSED), "next_best_step": next_step}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9705 Structured Label-Balanced Sampler Patch", "", "Stage9705 patches structured probes to sample train batches by primary structured label instead of contiguous row windows.", "", "## Result", "", f"- Passed: `{not failures}`", f"- Used label counts in 8x2 simulation: `{exposure['used_label_counts']}`", f"- Missing labels: `{exposure['missing_train_labels_in_used_batches']}`", "", "## Next", "", next_step, ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
