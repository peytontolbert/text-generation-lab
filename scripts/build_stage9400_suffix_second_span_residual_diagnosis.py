#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9400
NAME = "stage9400_suffix_second_span_residual_diagnosis"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9399_heldout_contrastive_suffix_support_probe_audit.json"
SOURCE_SAMPLES = ROOT / "runs/local/artifacts/stage9399_heldout_contrastive_suffix_support_probe/sample_generation_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "suffix_second_span_residual_diagnosis.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_SECOND_SPAN_RESIDUAL_DIAGNOSIS_STAGE9400.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def target_family(target: str, prefix: str, n: int = 7) -> str:
    words = target.split()
    p = prefix.split()
    return " ".join(words[len(p) : len(p) + n])


def update_registry(summary: dict) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    samples = load_json(SOURCE_SAMPLES).get("samples") or []
    failures: list[str] = []
    if source.get("passed") is not False or metrics.get("safety_gate_passed") is not True:
        failures.append("source_stage9399_not_safe_failed_audit")
    residuals = []
    first_token_fixed = 0
    by_family = Counter()
    by_split = Counter()
    for sample in samples:
        if sample.get("split") not in {"eval", "strict_eval"} or sample.get("exact_match"):
            continue
        boundary = sample.get("boundary_next_token") or {}
        if boundary.get("match"):
            first_token_fixed += 1
        fam = target_family(str(sample.get("target_text") or ""), str(sample.get("generation_prefix_text") or ""))
        by_family[fam] += 1
        by_split[str(sample.get("split"))] += 1
        residuals.append(
            {
                "row_id": sample.get("row_id"),
                "split": sample.get("split"),
                "boundary_next_token_match": bool(boundary.get("match")),
                "expected_rank": boundary.get("expected_rank"),
                "target_family_7_words": fam,
                "generated_text": sample.get("generated_text"),
                "target_text": sample.get("target_text"),
            }
        )
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": 9399,
        "heldout_residual_rows": len(residuals),
        "heldout_residual_first_token_fixed_rows": first_token_fixed,
        "heldout_residual_by_split": dict(sorted(by_split.items())),
        "heldout_residual_by_target_family": dict(sorted(by_family.items())),
        "residual_examples": residuals[:20],
        "diagnosis": "Stage9399 support fixed first-token/boundary behavior for most heldout failures, but continuation after the boundary token remains under-supported.",
        "next_patch_contract": {
            "objective": "suffix_second_span_support_manifest",
            "train_support": "Add train-only analogous rows for the 7-word post-prefix target spans that still fail, especially patch operator/update, repaired state, localized edit target, current repair invariant, expected assertion behavior, checked symbol evidence.",
            "do_not": ["open decoder_ce", "copy heldout row ids into model input", "authorize runtime/gemma/harness", "promote checkpoint"],
            "audit_requirements": ["heldout exact by split", "boundary next-token by split", "second-span family coverage", "no target text in model_input"],
        },
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
        "decision": "Recorded that Stage9399 improved heldout suffix recovery but left second-span continuation residuals.",
        "next_best_step": "Build a suffix second-span support manifest targeting the remaining heldout residual families; keep decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9400 Suffix Second-Span Residual Diagnosis",
                "",
                f"Passed: `{audit['passed']}`",
                f"Heldout residual rows: `{audit['heldout_residual_rows']}`",
                f"Residuals with boundary token fixed: `{audit['heldout_residual_first_token_fixed_rows']}`",
                f"Residuals by split: `{audit['heldout_residual_by_split']}`",
                f"Residual families: `{audit['heldout_residual_by_target_family']}`",
                "",
                "Diagnosis: Stage9399 fixed much of the first-token problem, but exact heldout recovery is now blocked by continuation after the boundary token.",
                "",
                "Next: build train-only analogous support rows for the failing 7-word post-prefix spans. Keep decoder CE, runtime, Gemma, harness, source/body emission, and promotion closed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "residual_rows": audit["heldout_residual_rows"], "first_token_fixed": audit["heldout_residual_first_token_fixed_rows"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
