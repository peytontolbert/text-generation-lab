#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9572
NAME = "stage9572_residual_denoise_boundary_contrast_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9571_residual_denoise_boundary_class_collapse_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9566_residual_denoise_target_rendered_manifest/residual_denoise_target_rendered_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "residual_denoise_boundary_contrast_manifest.jsonl"
CARD = OUT_DIR / "residual_denoise_boundary_contrast_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_BOUNDARY_CONTRAST_MANIFEST_STAGE9572.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def cls(row: dict[str, Any]) -> str:
    text = str((row.get("target") or {}).get("decoder_text") or "")
    return "BOUNDARY" if "AND_BOUNDARY" in text or "BOUNDARY" in text else "PREFIX"


def label_for(row: dict[str, Any]) -> str:
    return "BOUNDARY_REPAIR" if cls(row) == "BOUNDARY" else "PREFIX_ONLY_REPAIR"


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
    source_rows = load_jsonl(SOURCE_MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9571_not_passed")
    if (source.get("metrics") or {}).get("class_gate_passed") is not False:
        failures.append("stage9571_did_not_record_class_collapse")

    by_split_class: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in source_rows:
        by_split_class[str(row.get("split"))][cls(row)].append(row)

    balanced_rows: list[dict[str, Any]] = []
    duplicates = 0
    for split in ["train", "eval", "strict_eval"]:
        prefix_rows = by_split_class[split]["PREFIX"]
        boundary_rows = by_split_class[split]["BOUNDARY"]
        target_count = max(len(prefix_rows), len(boundary_rows))
        for klass, rows in [("PREFIX", prefix_rows), ("BOUNDARY", boundary_rows)]:
            if not rows:
                failures.append(f"missing_class:{split}:{klass}")
                continue
            for idx in range(target_count):
                src = rows[idx % len(rows)]
                out = deepcopy(src)
                if idx >= len(rows):
                    duplicates += 1
                    out["row_id"] = f"{src['row_id']}__stage9572_dup_{idx}"
                    out["source_stage9572_duplicate_from"] = src["row_id"]
                target = dict(out.get("target") or {})
                rendered = label_for(out)
                target["decoder_text"] = rendered
                target["label"] = rendered
                target["rendered_from"] = ["boundary_contrast_class"]
                target["contrast_class"] = klass
                out["target"] = target
                out["boundary_contrast_contract"] = {
                    "stage": STAGE,
                    "contrast_class": klass,
                    "disjoint_target_prefix": True,
                    "duplicate_for_balance": idx >= len(rows),
                    "visible_to_model_input": False,
                }
                balanced_rows.append(out)

    counts = Counter((row.get("split"), (row.get("target") or {}).get("contrast_class")) for row in balanced_rows)
    loss_counts = Counter(loss for row in balanced_rows for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)
    if dict(loss_counts) != {"denoise_ce": len(balanced_rows)}:
        failures.append("loss_mask_not_denoise_only")
    if any(any((row.get("authority") or {}).values()) for row in balanced_rows):
        failures.append("authority_rows_present")
    if any("contrast_class" in (row.get("model_input") or {}) for row in balanced_rows):
        failures.append("contrast_label_leaked_to_model_input")
    expected_counts = {("train", "PREFIX"): 15, ("train", "BOUNDARY"): 15, ("eval", "PREFIX"): 4, ("eval", "BOUNDARY"): 4, ("strict_eval", "PREFIX"): 5, ("strict_eval", "BOUNDARY"): 5}
    if dict(counts) != expected_counts:
        failures.append("unexpected_balanced_counts")

    with MANIFEST.open("w", encoding="utf-8") as f:
        for row in balanced_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    card = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "manifest_sha256": sha256(MANIFEST),
        "rows": len(balanced_rows),
        "duplicates_added": duplicates,
        "balanced_counts": {f"{split}:{klass}": count for (split, klass), count in sorted(counts.items())},
        "loss_counts": dict(sorted(loss_counts.items())),
        "target_counts": dict(sorted(Counter((row.get("target") or {}).get("decoder_text") for row in balanced_rows).items())),
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
        "decision": "Built a balanced boundary-contrast denoise manifest with disjoint target starts to address Stage9571 class collapse.",
        "next_best_step": "Run a target_100M contract preflight and capped probe over the Stage9572 boundary-contrast manifest.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9572 Residual Denoise Boundary Contrast Manifest", "", f"Passed: `{card['passed']}`", f"Rows: `{len(balanced_rows)}`", f"Duplicates added: `{duplicates}`", f"Counts: `{card['balanced_counts']}`", "", "Targets now use disjoint starts: `PREFIX_ONLY_REPAIR` and `BOUNDARY_REPAIR`.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(balanced_rows), "duplicates_added": duplicates, "counts": card["balanced_counts"], "failures": failures}, indent=2, sort_keys=True))
    if not card["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
