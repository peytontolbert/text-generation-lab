#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9333
NAME = "stage9333_routed_ladder_suffix_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9332_routed_ladder_probe_preexecution.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9331_routed_ladder_suffix_manifest/routed_ladder_suffix_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9333_routed_ladder_suffix_probe"
AUDIT = RUN_DIR / "stage9333_routed_ladder_suffix_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTED_LADDER_SUFFIX_PROBE_AUDIT_STAGE9333.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED = [
    "probe_contract_audit.json",
    "execution_result.json",
    "sample_generation_audit.json",
    "boundary_next_token_logits.jsonl",
    "row_token_loss.jsonl",
    "module_delta_norms.json",
    "cleanup_proof.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def rate(n: int, d: int) -> float | None:
    return n / d if d else None


def bucket(samples: list[dict[str, Any]], manifest_by_id: dict[str, dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for sample in samples:
        meta = manifest_by_id.get(str(sample.get("row_id")), {})
        model_input = meta.get("model_input") if isinstance(meta.get("model_input"), dict) else {}
        target = meta.get("target") if isinstance(meta.get("target"), dict) else {}
        if key == "source":
            value = str(meta.get("combined_curriculum_source") or model_input.get("routed_ladder_source") or "unknown")
        elif key == "phrase":
            value = str(target.get("phrase_id") or model_input.get("phrase_id") or "none")
        elif key == "route":
            value = str(model_input.get("opaque_phrase_route_id") or "unknown")
        elif key == "prefix_words":
            value = str(model_input.get("active_generation_prefix_words", "unknown"))
        elif key == "surface":
            value = str(model_input.get("semantic_surface_kind") or model_input.get("anchor_object_kind") or "unknown")
        elif key == "split":
            value = str(sample.get("split") or "unknown")
        else:
            value = "unknown"
        item = out.setdefault(value, {"rows": 0, "exact": 0, "target_prefix": 0, "boundary": 0, "contentful": 0, "repetition": 0})
        item["rows"] += 1
        item["exact"] += int(bool(sample.get("exact_match")))
        item["target_prefix"] += int(bool(sample.get("target_prefix_match")))
        item["contentful"] += int(not bool(sample.get("empty_output")) and not bool(sample.get("short_or_junk")))
        item["repetition"] += int(bool(sample.get("degenerate_repetition")))
        boundary = sample.get("boundary_next_token") if isinstance(sample.get("boundary_next_token"), dict) else {}
        item["boundary"] += int(bool(boundary.get("match")))
    return {
        name: {
            **counts,
            "exact_rate": rate(counts["exact"], counts["rows"]),
            "target_prefix_rate": rate(counts["target_prefix"], counts["rows"]),
            "boundary_rate": rate(counts["boundary"], counts["rows"]),
            "contentful_rate": rate(counts["contentful"], counts["rows"]),
            "repetition_rate": rate(counts["repetition"], counts["rows"]),
        }
        for name, counts in sorted(out.items())
    }


def classify_errors(samples: list[dict[str, Any]], manifest_by_id: dict[str, dict[str, Any]]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    counts = {
        "keeps_the_repetition": 0,
        "verified_inserted_before_preserves": 0,
        "operatch_repetition": 0,
        "extra_verified_before_preserves": 0,
        "boundary_whitespace_over_expected": 0,
        "other": 0,
    }
    failures: list[dict[str, Any]] = []
    for sample in samples:
        exact = bool(sample.get("exact_match"))
        prefix = bool(sample.get("target_prefix_match"))
        repetition = bool(sample.get("degenerate_repetition"))
        if exact and prefix and not repetition:
            continue
        row_id = str(sample.get("row_id"))
        meta = manifest_by_id.get(row_id, {})
        text = str(sample.get("generated_text") or "")
        boundary = sample.get("boundary_next_token") if isinstance(sample.get("boundary_next_token"), dict) else {}
        labels: list[str] = []
        if "keeps the keeps" in text:
            counts["keeps_the_repetition"] += 1
            labels.append("keeps_the_repetition")
        if "verified preserves" in text:
            counts["verified_inserted_before_preserves"] += 1
            labels.append("verified_inserted_before_preserves")
        if "operatch" in text:
            counts["operatch_repetition"] += 1
            labels.append("operatch_repetition")
        if "that verified preserves" in text:
            counts["extra_verified_before_preserves"] += 1
            labels.append("extra_verified_before_preserves")
        if boundary and not boundary.get("match") and boundary.get("generated_token_text") == " ":
            counts["boundary_whitespace_over_expected"] += 1
            labels.append("boundary_whitespace_over_expected")
        if not labels:
            counts["other"] += 1
            labels.append("other")
        model_input = meta.get("model_input") if isinstance(meta.get("model_input"), dict) else {}
        target = meta.get("target") if isinstance(meta.get("target"), dict) else {}
        failures.append({
            "row_id": row_id,
            "split": sample.get("split"),
            "source": meta.get("combined_curriculum_source"),
            "phrase_id": target.get("phrase_id") or model_input.get("phrase_id"),
            "route": model_input.get("opaque_phrase_route_id"),
            "prefix_words": model_input.get("active_generation_prefix_words"),
            "labels": labels,
            "target": sample.get("target_text"),
            "generated": text,
            "exact_match": sample.get("exact_match"),
            "target_prefix_match": sample.get("target_prefix_match"),
            "boundary_match": boundary.get("match") if boundary else None,
            "boundary_expected_token": boundary.get("expected_token_text") if boundary else None,
            "boundary_generated_token": boundary.get("generated_token_text") if boundary else None,
        })
    return counts, failures


def audit_run() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples_card = load_json(RUN_DIR / "sample_generation_audit.json")
    short_probe = load_json(RUN_DIR / "short_output_probe.json")
    repetition_probe = load_json(RUN_DIR / "repetition_probe.json")
    leak_probe = load_json(RUN_DIR / "internal_leak_probe.json")
    samples = samples_card.get("samples") if isinstance(samples_card.get("samples"), list) else []
    manifest_rows = load_jsonl(MANIFEST)
    manifest_by_id = {str(row.get("row_id")): row for row in manifest_rows}
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9332_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if contract.get("generation_prefix_field") != "model_input.active_generation_prefix_span":
        failures.append("wrong_generation_prefix_field")
    if execution.get("decoder_ce_rows") != 0 or contract.get("loss_counts", {}).get("decoder_ce") != 0:
        failures.append("decoder_ce_opened")
    if execution.get("runtime_executed") is not False or execution.get("gemma_executed") is not False or execution.get("harness_executed") is not False:
        failures.append("forbidden_execution_surface_opened")
    if execution.get("final_checkpoint_exported") is not False:
        failures.append("checkpoint_exported")
    if missing:
        failures.append("required_artifacts_missing")
    safety_gate_passed = not failures
    generated = int(samples_card.get("generated_rows") or 0)
    exact = int(samples_card.get("exact_match_rows") or 0)
    target_prefix = int(samples_card.get("target_prefix_match_rows") or 0)
    boundary = int(samples_card.get("boundary_next_token_match_rows") or 0)
    contentful = int(samples_card.get("contentful_rows") or 0)
    repetition_rows = int(repetition_probe.get("generated_repetition_rows") or sum(1 for row in samples if row.get("degenerate_repetition")))
    short_rows = int(short_probe.get("short_or_junk_rows") or 0)
    leak_rows = int(leak_probe.get("generated_internal_token_rows") or 0)
    quality_gate_passed = bool(generated == 56 and exact == 56 and target_prefix == 56 and boundary == 56 and contentful == 56 and repetition_rows == 0 and short_rows == 0 and leak_rows == 0)
    error_counts, failed_samples = classify_errors(samples, manifest_by_id)
    return {
        "passed": safety_gate_passed and quality_gate_passed,
        "safety_gate_passed": safety_gate_passed,
        "quality_gate_passed": quality_gate_passed,
        "failures": failures,
        "missing_artifacts": missing,
        "manifest_rows": len(manifest_rows),
        "generated_rows": generated,
        "exact_match_rows": exact,
        "exact_match_rate": rate(exact, generated),
        "target_prefix_match_rows": target_prefix,
        "target_prefix_match_rate": samples_card.get("target_prefix_match_rate"),
        "boundary_next_token_match_rows": boundary,
        "boundary_next_token_match_rate": samples_card.get("boundary_next_token_match_rate"),
        "boundary_next_token_mean_expected_rank": samples_card.get("boundary_next_token_mean_expected_rank"),
        "contentful_rows": contentful,
        "contentful_rate": samples_card.get("contentful_rate"),
        "short_or_junk_rows": short_rows,
        "generated_internal_token_rows": leak_rows,
        "degenerate_repetition_rows": repetition_rows,
        "by_source": bucket(samples, manifest_by_id, "source"),
        "by_phrase": bucket(samples, manifest_by_id, "phrase"),
        "by_route": bucket(samples, manifest_by_id, "route"),
        "by_prefix_words": bucket(samples, manifest_by_id, "prefix_words"),
        "by_surface": bucket(samples, manifest_by_id, "surface"),
        "by_split": bucket(samples, manifest_by_id, "split"),
        "error_counts": error_counts,
        "failed_samples": failed_samples,
        "diagnosis": "safety_contract_held_but_routed_phrase_rows_interfere_with_ladder_suffixes; main residuals are keeps_the repetition, verified insertion before preserves, and operatch repetition",
        "next_patch_target": "stage9334_targeted_anti_insertion_repetition_curriculum_for_keeps_the_verified_preserves_and_operatch",
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = audit_run()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "The routed-ladder probe executed safely but failed quality gates; decoder CE remains closed.",
        "next_best_step": "Build Stage9334 targeted anti-insertion/repetition rows for `keeps the`, `verified preserves`, and `operatch`, then run a smaller repair probe before reconnecting the full routed ladder.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9333 Routed Ladder Suffix Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Safety gate passed: `{audit['safety_gate_passed']}`",
        f"Quality gate passed: `{audit['quality_gate_passed']}`",
        f"Exact match rows: `{audit['exact_match_rows']}` / `{audit['generated_rows']}`",
        f"Target prefix match rate: `{audit['target_prefix_match_rate']}`",
        f"Boundary next-token match rate: `{audit['boundary_next_token_match_rate']}`",
        f"Contentful generation rate: `{audit['contentful_rate']}`",
        f"Degenerate repetition rows: `{audit['degenerate_repetition_rows']}`",
        f"Error counts: `{audit['error_counts']}`",
        "",
        "The safety contract held: decoder CE, runtime, Gemma, harness, scoring, and checkpoint export stayed closed.",
        "The quality contract failed after merging routed phrase rows back with the ladder. Residual failures are concentrated in `keeps the` repetition, `verified preserves` insertion, and `operatch` repetition.",
        "Next patch should be targeted anti-insertion/repetition rows, not a generic wider probe.",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["safety_gate_passed", "quality_gate_passed", "exact_match_rate", "target_prefix_match_rate", "boundary_next_token_match_rate", "contentful_rate", "degenerate_repetition_rows", "error_counts"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
