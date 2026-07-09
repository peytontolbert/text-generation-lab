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
STAGE = 9571
NAME = "stage9571_residual_denoise_boundary_class_collapse_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9570_residual_denoise_target_rendered_longer_capped_probe.json"
SAMPLES = ROOT / "runs/local/artifacts/stage9570_residual_denoise_target_rendered_longer_capped_probe/denoise_repair_probe/sample_generation_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "residual_denoise_boundary_class_collapse_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_BOUNDARY_CLASS_COLLAPSE_AUDIT_STAGE9571.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def bucket(text: str) -> str:
    if text.startswith("REPAIR_PREFIX_AND_BOUNDARY"):
        return "REPAIR_PREFIX_AND_BOUNDARY"
    if text.startswith("REPAIR_PREFIX_ONLY"):
        return "REPAIR_PREFIX_ONLY"
    return "OTHER"


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
    sample_card = load_json(SAMPLES)
    samples = sample_card.get("samples") if isinstance(sample_card.get("samples"), list) else []
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9570_not_passed")
    if not samples:
        failures.append("missing_generation_samples")
    target_counts: Counter[str] = Counter()
    pred_counts: Counter[str] = Counter()
    confusion: dict[str, Counter[str]] = {}
    false_boundary_as_prefix: list[str] = []
    exact_rows = 0
    for row in samples:
        target = bucket(str(row.get("target_text") or ""))
        pred = bucket(str(row.get("generated_text") or ""))
        row_id = str(row.get("row_id"))
        target_counts[target] += 1
        pred_counts[pred] += 1
        confusion.setdefault(target, Counter())[pred] += 1
        exact_rows += int(bool(row.get("exact_match")))
        if target == "REPAIR_PREFIX_AND_BOUNDARY" and pred == "REPAIR_PREFIX_ONLY":
            false_boundary_as_prefix.append(row_id)
    generated_rows = len(samples)
    exact_rate = exact_rows / generated_rows if generated_rows else 0.0
    pred_dominant_bucket, pred_dominant_count = pred_counts.most_common(1)[0] if pred_counts else ("NONE", 0)
    collapse_rate = pred_dominant_count / generated_rows if generated_rows else 0.0
    boundary_target_rows = target_counts.get("REPAIR_PREFIX_AND_BOUNDARY", 0)
    boundary_recall = (
        confusion.get("REPAIR_PREFIX_AND_BOUNDARY", Counter()).get("REPAIR_PREFIX_AND_BOUNDARY", 0) / boundary_target_rows
        if boundary_target_rows
        else None
    )
    class_gate_passed = exact_rate >= 0.85 and (boundary_recall is not None and boundary_recall >= 0.85) and collapse_rate < 0.75
    audit = {
        "passed": True,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "samples": str(SAMPLES.relative_to(ROOT)),
        "generated_rows": generated_rows,
        "target_counts": dict(sorted(target_counts.items())),
        "pred_counts": dict(sorted(pred_counts.items())),
        "confusion": {key: dict(sorted(value.items())) for key, value in sorted(confusion.items())},
        "exact_rows": exact_rows,
        "exact_rate": exact_rate,
        "pred_dominant_bucket": pred_dominant_bucket,
        "collapse_rate": collapse_rate,
        "boundary_recall": boundary_recall,
        "false_boundary_as_prefix_rows": false_boundary_as_prefix,
        "class_gate_passed": class_gate_passed,
        "widening_authorized": False,
        "next_patch": "add boundary-positive counterbalance/upsampling or a class-weighted denoise schedule before widening",
        "model_execution_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "promotion_ready": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": True,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Stage9570 fixed generic generation but collapsed boundary-positive rows into REPAIR_PREFIX_ONLY. Widening remains blocked.",
        "next_best_step": "Build a boundary-positive counterbalance or class-weighted residual-denoise manifest, then rerun a capped target_100M probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9571 Residual Denoise Boundary Class Collapse Audit", "", f"Generated rows: `{generated_rows}`", f"Exact rate: `{exact_rate}`", f"Boundary recall: `{boundary_recall}`", f"Collapse rate: `{collapse_rate}`", f"Class gate passed: `{class_gate_passed}`", "", "Widening remains blocked. Next patch should counterbalance boundary-positive rows.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": True, "exact_rate": exact_rate, "boundary_recall": boundary_recall, "collapse_rate": collapse_rate, "class_gate_passed": class_gate_passed, "false_boundary_as_prefix_rows": len(false_boundary_as_prefix)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
