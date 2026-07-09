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
STAGE = 9577
NAME = "stage9577_residual_denoise_boundary_discriminator_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9576_residual_denoise_boundary_interleaved_capped_probe.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9575_residual_denoise_boundary_interleaved_manifest/residual_denoise_boundary_interleaved_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "residual_denoise_boundary_discriminator_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_BOUNDARY_DISCRIMINATOR_AUDIT_STAGE9577.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

KEYS_OF_INTEREST = [
    "obs_alignment_status",
    "obs_boundary_relation",
    "obs_boundary_rank_bucket",
    "obs_failure_evidence_family",
    "obs_has_boundary_next_token_miss_reason",
    "obs_residual_reason_count",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def klass(row: dict[str, Any]) -> str:
    return str((row.get("target") or {}).get("contrast_class") or "UNKNOWN")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    metrics = source.get("metrics") or {}
    rows = load_jsonl(SOURCE_MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9576_not_passed")
    if metrics.get("sample_balanced") is not True:
        failures.append("stage9576_sample_not_balanced")
    if metrics.get("boundary_recall") != 0.0:
        failures.append("stage9576_boundary_recall_not_zero")
    if metrics.get("prefix_recall") != 1.0:
        failures.append("stage9576_prefix_recall_not_one")
    if len(rows) != 48:
        failures.append("source_manifest_row_count_not_48")
    if any(any((row.get("authority") or {}).values()) for row in rows):
        failures.append("authority_rows_present")

    row_counts = Counter(klass(row) for row in rows)
    key_distributions: dict[str, dict[str, dict[str, int]]] = {}
    discriminating_keys: list[str] = []
    complete_discriminators: list[str] = []
    for key in KEYS_OF_INTEREST:
        by_class: dict[str, Counter[str]] = defaultdict(Counter)
        missing = Counter()
        for row in rows:
            cls = klass(row)
            model_input = row.get("model_input") or {}
            if key not in model_input:
                missing[cls] += 1
                continue
            by_class[cls][str(model_input[key])] += 1
        key_distributions[key] = {cls: dict(sorted(counter.items())) for cls, counter in sorted(by_class.items())}
        if by_class.get("PREFIX", Counter()) != by_class.get("BOUNDARY", Counter()):
            discriminating_keys.append(key)
        if missing.get("PREFIX", 0) == 0 and missing.get("BOUNDARY", 0) == 0 and by_class.get("PREFIX") != by_class.get("BOUNDARY"):
            complete_discriminators.append(key)

    boundary_miss_rows = [
        row
        for row in rows
        if klass(row) == "BOUNDARY"
        and (row.get("model_input") or {}).get("obs_has_boundary_next_token_miss_reason") is True
        and (row.get("model_input") or {}).get("obs_boundary_relation") == "boundary_miss"
    ]
    prefix_boundary_match_rows = [
        row
        for row in rows
        if klass(row) == "PREFIX"
        and (row.get("model_input") or {}).get("obs_has_boundary_next_token_miss_reason") is False
        and (row.get("model_input") or {}).get("obs_boundary_relation") == "boundary_match"
    ]
    evidence_gate_passed = len(boundary_miss_rows) == row_counts.get("BOUNDARY", 0) and len(prefix_boundary_match_rows) == row_counts.get("PREFIX", 0)

    learned_collapse_confirmed = (
        metrics.get("sample_balanced") is True
        and metrics.get("boundary_recall") == 0.0
        and metrics.get("prefix_recall") == 1.0
        and (metrics.get("pred_counts") or {}).get("PREFIX") == 16
    )
    class_gate_passed = bool(metrics.get("class_gate_passed"))
    semantic_issue = evidence_gate_passed and learned_collapse_confirmed and not class_gate_passed

    if not discriminating_keys:
        failures.append("no_model_input_discriminators_found")
    if not evidence_gate_passed:
        failures.append("boundary_evidence_not_complete")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "row_counts": dict(sorted(row_counts.items())),
        "stage9576_exact_rate": metrics.get("exact_rate"),
        "stage9576_sample_balanced": metrics.get("sample_balanced"),
        "stage9576_boundary_recall": metrics.get("boundary_recall"),
        "stage9576_prefix_recall": metrics.get("prefix_recall"),
        "stage9576_pred_counts": metrics.get("pred_counts"),
        "stage9576_confusion": metrics.get("confusion"),
        "class_gate_passed": class_gate_passed,
        "learned_collapse_confirmed": learned_collapse_confirmed,
        "discriminating_keys": discriminating_keys,
        "complete_discriminators": complete_discriminators,
        "key_distributions": key_distributions,
        "boundary_miss_rows": len(boundary_miss_rows),
        "prefix_boundary_match_rows": len(prefix_boundary_match_rows),
        "evidence_gate_passed": evidence_gate_passed,
        "semantic_issue": semantic_issue,
        "widening_authorized": False,
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
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Stage9576 fixed generation sample bias, but the decoder still maps all balanced boundary samples to PREFIX despite complete boundary evidence in model_input.",
        "next_best_step": "Build a boundary-evidence amplified target-surface manifest that keeps denoise CE only, preserves closed authority, and makes the first decoded class token depend on explicit verifier observation fields.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9577 Residual Denoise Boundary Discriminator Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Sample balanced: `{audit['stage9576_sample_balanced']}`",
                f"Boundary recall: `{audit['stage9576_boundary_recall']}`",
                f"Prefix recall: `{audit['stage9576_prefix_recall']}`",
                f"Evidence gate passed: `{evidence_gate_passed}`",
                f"Learned collapse confirmed: `{learned_collapse_confirmed}`",
                "",
                "The next issue is not sample bias. Boundary evidence is present, but the denoise decoder still emits the prefix-only class for all sampled rows.",
                "",
                "Next: build a boundary-evidence amplified manifest before any widening.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": audit["passed"],
                "evidence_gate_passed": evidence_gate_passed,
                "learned_collapse_confirmed": learned_collapse_confirmed,
                "discriminating_keys": discriminating_keys,
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
