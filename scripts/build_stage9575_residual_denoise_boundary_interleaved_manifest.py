#!/usr/bin/env python3
from __future__ import annotations

import hashlib
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
STAGE = 9575
NAME = "stage9575_residual_denoise_boundary_interleaved_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9574_residual_denoise_generation_sample_bias_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9572_residual_denoise_boundary_contrast_manifest/residual_denoise_boundary_contrast_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "residual_denoise_boundary_interleaved_manifest.jsonl"
CARD = OUT_DIR / "residual_denoise_boundary_interleaved_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_BOUNDARY_INTERLEAVED_MANIFEST_STAGE9575.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def klass(row: dict[str, Any]) -> str:
    return str((row.get("target") or {}).get("contrast_class") or "UNKNOWN")


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
    rows = load_jsonl(SOURCE_MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9574_not_passed")
    if (source.get("metrics") or {}).get("sample_bias_detected") is not True:
        failures.append("stage9574_did_not_record_sample_bias")

    by_split_class: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_split_class[str(row.get("split"))][klass(row)].append(row)

    interleaved: list[dict[str, Any]] = []
    for split in ["train", "eval", "strict_eval"]:
        prefix = by_split_class[split]["PREFIX"]
        boundary = by_split_class[split]["BOUNDARY"]
        if len(prefix) != len(boundary):
            failures.append(f"unbalanced_split:{split}")
        for idx in range(max(len(prefix), len(boundary))):
            if idx < len(prefix):
                row = dict(prefix[idx])
                row["stage9575_interleaved_order_index"] = len(interleaved)
                interleaved.append(row)
            if idx < len(boundary):
                row = dict(boundary[idx])
                row["stage9575_interleaved_order_index"] = len(interleaved)
                interleaved.append(row)

    counts = Counter((row.get("split"), klass(row)) for row in interleaved)
    first_16_counts = Counter(klass(row) for row in interleaved[:16])
    loss_counts = Counter(loss for row in interleaved for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)
    if len(interleaved) != 48:
        failures.append("row_count_not_48")
    if first_16_counts != {"PREFIX": 8, "BOUNDARY": 8}:
        failures.append("first_generation_window_not_balanced")
    if dict(loss_counts) != {"denoise_ce": 48}:
        failures.append("loss_mask_not_denoise_only")
    if any(any((row.get("authority") or {}).values()) for row in interleaved):
        failures.append("authority_rows_present")

    with MANIFEST.open("w", encoding="utf-8") as f:
        for row in interleaved:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    card = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "manifest_sha256": sha256(MANIFEST),
        "rows": len(interleaved),
        "split_class_counts": {f"{split}:{cls}": count for (split, cls), count in sorted(counts.items())},
        "first_16_class_counts": dict(sorted(first_16_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "model_execution_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "promotion_ready": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **card},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Interleaved boundary and prefix residual-denoise rows so the generation audit window samples both classes.",
        "next_best_step": "Run a capped target_100M probe over the interleaved boundary-contrast manifest and audit balanced boundary recall.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9575 Residual Denoise Boundary Interleaved Manifest", "", f"Passed: `{card['passed']}`", f"Rows: `{len(interleaved)}`", f"First 16 class counts: `{dict(sorted(first_16_counts.items()))}`", "", "The manifest remains denoise-only and authority-closed.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(interleaved), "first_16_class_counts": dict(sorted(first_16_counts.items())), "failures": failures}, indent=2, sort_keys=True))
    if not card["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
