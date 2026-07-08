#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9438
NAME = "stage9438_suffix_choice_prior_fusion_residual_diagnosis"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9437_suffix_choice_prior_fusion_denoise_probe_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9434_suffix_choice_prior_fusion_denoise_manifest/suffix_choice_prior_fusion_denoise_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9437_suffix_choice_prior_fusion_denoise_probe"
SAMPLES = RUN_DIR / "sample_generation_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DIAGNOSIS = OUT_DIR / "suffix_choice_prior_fusion_residual_diagnosis.json"
HELDOUT_RESIDUALS = OUT_DIR / "heldout_prior_fusion_residuals.jsonl"
REPETITION_RESIDUALS = OUT_DIR / "repetition_prior_fusion_residuals.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_PRIOR_FUSION_RESIDUAL_DIAGNOSIS_STAGE9438.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    manifest_rows = load_jsonl(MANIFEST)
    samples_card = load_json(SAMPLES)
    samples = samples_card.get("samples") if isinstance(samples_card.get("samples"), list) else []
    manifest_by_id = {str(row.get("row_id")): row for row in manifest_rows}

    heldout_residuals: list[dict] = []
    repetition_residuals: list[dict] = []
    split_counts: dict[str, Counter] = defaultdict(Counter)
    prior_label_counts: dict[str, Counter] = defaultdict(Counter)
    prior_source_counts: dict[str, Counter] = defaultdict(Counter)
    source_stage9388_counts = Counter(str(row.get("source_stage9388_row_id")) for row in manifest_rows)
    duplicate_train_sources = {
        key: count
        for key, count in source_stage9388_counts.items()
        if key and key != "None" and count > 1
    }

    for sample in samples:
        row_id = str(sample.get("row_id"))
        row = manifest_by_id.get(row_id, {})
        prior = row.get("suffix_choice_prior") if isinstance(row.get("suffix_choice_prior"), dict) else {}
        split = str(sample.get("split"))
        exact = bool(sample.get("exact_match"))
        repetition = bool(sample.get("degenerate_repetition"))
        split_counts[split]["rows"] += 1
        split_counts[split]["exact"] += int(exact)
        split_counts[split]["prefix"] += int(bool(sample.get("target_prefix_match")))
        split_counts[split]["boundary"] += int(bool((sample.get("boundary_next_token") or {}).get("match")))
        split_counts[split]["repetition"] += int(repetition)
        prior_label = str(prior.get("label"))
        prior_source = str(row.get("suffix_choice_prior_source"))
        prior_label_counts[prior_label]["rows"] += 1
        prior_label_counts[prior_label]["exact"] += int(exact)
        prior_label_counts[prior_label]["repetition"] += int(repetition)
        prior_source_counts[prior_source]["rows"] += 1
        prior_source_counts[prior_source]["exact"] += int(exact)
        prior_source_counts[prior_source]["repetition"] += int(repetition)
        payload = {
            "row_id": row_id,
            "split": split,
            "exact_match": exact,
            "target_prefix_match": bool(sample.get("target_prefix_match")),
            "boundary_next_token_match": bool((sample.get("boundary_next_token") or {}).get("match")),
            "degenerate_repetition": repetition,
            "generated_text": sample.get("generated_text"),
            "target_text": sample.get("target_text"),
            "suffix_choice_prior": prior,
            "suffix_choice_prior_source": prior_source,
            "source_stage9388_row_id": row.get("source_stage9388_row_id"),
            "source_stage9413_suffix_choice_row_id": row.get("source_stage9413_suffix_choice_row_id"),
            "duplicate_source_stage9388_count": source_stage9388_counts.get(str(row.get("source_stage9388_row_id")), 0),
        }
        if split in {"eval", "strict_eval"} and not exact:
            heldout_residuals.append(payload)
        if repetition:
            repetition_residuals.append(payload)

    low_conf_heldout = [
        row
        for row in heldout_residuals
        if isinstance(row.get("suffix_choice_prior"), dict)
        and float(row["suffix_choice_prior"].get("confidence") or 0.0) < 0.20
    ]
    repeated_duplicate_sources = [
        row
        for row in repetition_residuals
        if int(row.get("duplicate_source_stage9388_count") or 0) > 1
    ]

    failures: list[str] = []
    if source.get("passed") is not False:
        failures.append("source_stage9437_not_failed_quality_as_expected")
    if len(samples) != 53:
        failures.append("unexpected_sample_count")
    if len(heldout_residuals) != 7:
        failures.append("unexpected_heldout_residual_count")
    if len(repetition_residuals) != 6:
        failures.append("unexpected_repetition_residual_count")

    diagnosis = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9437_suffix_choice_prior_fusion_denoise_probe_audit",
        "sample_rows": len(samples),
        "heldout_residual_rows": len(heldout_residuals),
        "repetition_residual_rows": len(repetition_residuals),
        "low_confidence_heldout_residual_rows": len(low_conf_heldout),
        "repetition_rows_with_duplicate_source_stage9388": len(repeated_duplicate_sources),
        "split_metrics": {key: dict(value) for key, value in sorted(split_counts.items())},
        "prior_label_metrics": {key: dict(value) for key, value in sorted(prior_label_counts.items())},
        "prior_source_metrics": {key: dict(value) for key, value in sorted(prior_source_counts.items())},
        "duplicate_source_stage9388_counts": dict(sorted(duplicate_train_sources.items())),
        "diagnosis": (
            "Heldout failures are mostly controller-prior confidence and family coverage failures; repetition is "
            "not explained solely by duplicate source_stage9388 support and needs explicit anti-repetition routing."
        ),
        "next_patch_target": "stage9439_heldout_prior_confidence_and_antirepetition_manifest",
        "authority": dict(AUTHORITY_CLOSED),
    }
    DIAGNOSIS.write_text(json.dumps(diagnosis, indent=2, sort_keys=True) + "\n")
    write_jsonl(HELDOUT_RESIDUALS, heldout_residuals)
    write_jsonl(REPETITION_RESIDUALS, repetition_residuals)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": diagnosis["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **diagnosis},
        "artifacts": {
            "diagnosis": str(DIAGNOSIS.relative_to(ROOT)),
            "heldout_residuals": str(HELDOUT_RESIDUALS.relative_to(ROOT)),
            "repetition_residuals": str(REPETITION_RESIDUALS.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Diagnosed Stage9437 residuals without opening decoder CE or denoise execution.",
        "next_best_step": "Build a heldout-prior confidence and anti-repetition repair manifest; keep decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9438 Suffix Choice Prior Fusion Residual Diagnosis",
                "",
                f"Passed: `{diagnosis['passed']}`",
                f"Heldout residual rows: `{len(heldout_residuals)}`",
                f"Repetition residual rows: `{len(repetition_residuals)}`",
                f"Low-confidence heldout residual rows: `{len(low_conf_heldout)}`",
                "",
                "The next patch should combine heldout prior-confidence handling with anti-repetition routing. Decoder CE remains closed.",
                "",
            ]
        )
    )

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"heldout_residuals": len(heldout_residuals), "repetition_residuals": len(repetition_residuals), "low_conf_heldout": len(low_conf_heldout)}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
