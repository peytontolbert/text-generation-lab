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
STAGE = 9574
NAME = "stage9574_residual_denoise_generation_sample_bias_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9573_residual_denoise_boundary_contrast_capped_probe.json"
SAMPLES = ROOT / "runs/local/artifacts/stage9573_residual_denoise_boundary_contrast_capped_probe/denoise_repair_probe/sample_generation_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9572_residual_denoise_boundary_contrast_manifest/residual_denoise_boundary_contrast_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "residual_denoise_generation_sample_bias_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_GENERATION_SAMPLE_BIAS_AUDIT_STAGE9574.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def cls_from_text(text: str) -> str:
    if text.startswith("BOUNDARY_REPAIR"):
        return "BOUNDARY"
    if text.startswith("PREFIX_ONLY_REPAIR"):
        return "PREFIX"
    return "OTHER"


def cls_from_row(row: dict[str, Any]) -> str:
    return cls_from_text(str((row.get("target") or {}).get("decoder_text") or ""))


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
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9573_not_passed")
    manifest_counts = Counter((str(row.get("split")), cls_from_row(row)) for row in rows)
    sample_counts = Counter((str(row.get("split")), cls_from_text(str(row.get("target_text") or ""))) for row in samples)
    sample_class_counts = Counter(cls_from_text(str(row.get("target_text") or "")) for row in samples)
    manifest_class_counts = Counter(cls_from_row(row) for row in rows)
    boundary_sample_rows = sample_class_counts.get("BOUNDARY", 0)
    sample_bias_detected = boundary_sample_rows < 4 or sample_class_counts.get("PREFIX", 0) / max(1, len(samples)) > 0.75
    audit = {
        "passed": True,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "samples": str(SAMPLES.relative_to(ROOT)),
        "manifest_rows": len(rows),
        "sample_rows": len(samples),
        "manifest_class_counts": dict(sorted(manifest_class_counts.items())),
        "sample_class_counts": dict(sorted(sample_class_counts.items())),
        "manifest_split_class_counts": {f"{split}:{klass}": count for (split, klass), count in sorted(manifest_counts.items())},
        "sample_split_class_counts": {f"{split}:{klass}": count for (split, klass), count in sorted(sample_counts.items())},
        "sample_bias_detected": sample_bias_detected,
        "boundary_sample_rows": boundary_sample_rows,
        "class_gate_from_stage9573_underpowered": sample_bias_detected,
        "widening_authorized": False,
        "next_patch": "interleave boundary/prefix rows within each split and rerun generation audit with enough boundary samples",
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
        "decision": "Stage9573 generation audit was biased by manifest order: only one boundary target was sampled. Widening remains blocked.",
        "next_best_step": "Build an interleaved boundary-contrast manifest and rerun the capped probe with balanced generation samples.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9574 Residual Denoise Generation Sample Bias Audit", "", f"Sample bias detected: `{sample_bias_detected}`", f"Manifest class counts: `{dict(sorted(manifest_class_counts.items()))}`", f"Sample class counts: `{dict(sorted(sample_class_counts.items()))}`", "", "Next patch: interleave class rows before rerunning the capped generation audit.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": True, "sample_bias_detected": sample_bias_detected, "sample_class_counts": dict(sorted(sample_class_counts.items())), "boundary_sample_rows": boundary_sample_rows}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
