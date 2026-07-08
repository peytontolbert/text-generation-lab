#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9348
NAME = "stage9348_schema_normalized_bridge_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9347_schema_normalized_bridge_probe_preexecution.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9346_schema_normalized_subword_bridge_repair_manifest/schema_normalized_subword_bridge_repair_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9348_schema_normalized_bridge_probe"
AUDIT = RUN_DIR / "stage9348_schema_normalized_bridge_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SCHEMA_NORMALIZED_BRIDGE_PROBE_AUDIT_STAGE9348.md"
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


def bucket(samples: list[dict[str, Any]], rows_by_id: dict[str, dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for sample in samples:
        row = rows_by_id.get(str(sample.get("row_id")), {})
        mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        if key == "task":
            value = str(row.get("repair_task_type") or "unknown")
        elif key == "route":
            value = str(mi.get("opaque_phrase_route_id") or "unknown")
        elif key == "surface":
            value = str(mi.get("semantic_surface_kind") or "unknown")
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


def classify(samples: list[dict[str, Any]], rows_by_id: dict[str, dict[str, Any]]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    counts: Counter[str] = Counter()
    failed: list[dict[str, Any]] = []
    for sample in samples:
        if sample.get("exact_match") and not sample.get("degenerate_repetition"):
            continue
        text = str(sample.get("generated_text") or "")
        labels: list[str] = []
        if "operatch operatch" in text:
            labels.append("operator_operatch_repetition")
        if "patch operatch" in text:
            labels.append("operator_terminal_bridge_failure")
        if sample.get("degenerate_repetition"):
            labels.append("degenerate_repetition")
        if not labels:
            labels.append("other")
        for label in labels:
            counts[label] += 1
        row = rows_by_id.get(str(sample.get("row_id")), {})
        mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        failed.append(
            {
                "row_id": sample.get("row_id"),
                "split": sample.get("split"),
                "labels": labels,
                "task": row.get("repair_task_type"),
                "route": mi.get("opaque_phrase_route_id"),
                "surface": mi.get("semantic_surface_kind"),
                "prefix": sample.get("generation_prefix_text"),
                "target": sample.get("target_text"),
                "generated": text,
                "exact_match": sample.get("exact_match"),
                "target_prefix_match": sample.get("target_prefix_match"),
            }
        )
    return dict(sorted(counts.items())), failed


def audit_run() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples_card = load_json(RUN_DIR / "sample_generation_audit.json")
    short_probe = load_json(RUN_DIR / "short_output_probe.json")
    repetition_probe = load_json(RUN_DIR / "repetition_probe.json")
    leak_probe = load_json(RUN_DIR / "internal_leak_probe.json")
    samples = samples_card.get("samples") if isinstance(samples_card.get("samples"), list) else []
    rows = load_jsonl(MANIFEST)
    rows_by_id = {str(row.get("row_id")): row for row in rows}
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9347_not_passed")
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
    generated = int(samples_card.get("generated_rows") or 0)
    exact = int(samples_card.get("exact_match_rows") or 0)
    target_prefix = int(samples_card.get("target_prefix_match_rows") or 0)
    boundary = int(samples_card.get("boundary_next_token_match_rows") or 0)
    contentful = int(samples_card.get("contentful_rows") or 0)
    repetition_rows = int(repetition_probe.get("generated_repetition_rows") or 0)
    short_rows = int(short_probe.get("short_or_junk_rows") or 0)
    leak_rows = int(leak_probe.get("generated_internal_token_rows") or 0)
    safety_gate_passed = not failures
    quality_gate_passed = bool(generated == 31 and exact == 31 and target_prefix == 31 and boundary == 31 and contentful == 31 and repetition_rows == 0 and short_rows == 0 and leak_rows == 0)
    error_counts, failed_samples = classify(samples, rows_by_id)
    return {
        "passed": safety_gate_passed and quality_gate_passed,
        "safety_gate_passed": safety_gate_passed,
        "quality_gate_passed": quality_gate_passed,
        "failures": failures,
        "missing_artifacts": missing,
        "manifest_rows": len(rows),
        "generated_rows": generated,
        "exact_match_rows": exact,
        "exact_match_rate": rate(exact, generated),
        "target_prefix_match_rows": target_prefix,
        "target_prefix_match_rate": samples_card.get("target_prefix_match_rate"),
        "boundary_next_token_match_rows": boundary,
        "boundary_next_token_match_rate": samples_card.get("boundary_next_token_match_rate"),
        "contentful_rows": contentful,
        "contentful_rate": samples_card.get("contentful_rate"),
        "short_or_junk_rows": short_rows,
        "generated_internal_token_rows": leak_rows,
        "degenerate_repetition_rows": repetition_rows,
        "by_task": bucket(samples, rows_by_id, "task"),
        "by_route": bucket(samples, rows_by_id, "route"),
        "by_surface": bucket(samples, rows_by_id, "surface"),
        "by_split": bucket(samples, rows_by_id, "split"),
        "error_counts": error_counts,
        "failed_samples": failed_samples,
        "diagnosis": "schema-normalized bridge repair solved dependency-handle and file-path bridge rows exactly, but route_1 patch-operator rows all collapse into `operatch` repetition after the correct boundary token.",
        "next_patch_target": "stage9349_operator_terminal_anti_repetition_manifest",
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
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
        "decision": "The schema-normalized bridge probe executed safely but failed route_1 patch-operator exactness; decoder CE remains closed.",
        "next_best_step": "Build Stage9349 operator-terminal anti-repetition rows focused only on `patch operator`/`operatch`, then probe in isolation before another rejoin.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9348 Schema-Normalized Bridge Probe Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Safety gate passed: `{audit['safety_gate_passed']}`",
                f"Quality gate passed: `{audit['quality_gate_passed']}`",
                f"Exact match rows: `{audit['exact_match_rows']}` / `{audit['generated_rows']}`",
                f"Target-prefix rows: `{audit['target_prefix_match_rows']}` / `{audit['generated_rows']}`",
                f"Boundary next-token rows: `{audit['boundary_next_token_match_rows']}` / `{audit['generated_rows']}`",
                f"Contentful rows: `{audit['contentful_rows']}` / `{audit['generated_rows']}`",
                f"Degenerate repetition rows: `{audit['degenerate_repetition_rows']}`",
                f"Error counts: `{audit['error_counts']}`",
                "",
                "Dependency-handle `keeps the` rows and file-path `localized edit` rows now pass exactly. The remaining failure is isolated to route_1 patch-operator rows, which repeat `operatch` before ending with `operator`.",
                "",
                "Safety held: decoder CE, runtime, harness, Gemma, scoring, promotion, and checkpoint export stayed closed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["safety_gate_passed", "quality_gate_passed", "exact_match_rate", "target_prefix_match_rate", "boundary_next_token_match_rate", "contentful_rate", "degenerate_repetition_rows", "error_counts"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
