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
STAGE = 9339
NAME = "stage9339_merged_repair_interference_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9338_merged_repair_interference_probe_preexecution.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9337_routed_ladder_with_targeted_repair_manifest/routed_ladder_with_targeted_repair_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9339_merged_repair_interference_probe"
AUDIT = RUN_DIR / "stage9339_merged_repair_interference_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MERGED_REPAIR_INTERFERENCE_PROBE_AUDIT_STAGE9339.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED = ["probe_contract_audit.json", "execution_result.json", "sample_generation_audit.json", "boundary_next_token_logits.jsonl", "row_token_loss.jsonl", "module_delta_norms.json", "cleanup_proof.json", "short_output_probe.json", "repetition_probe.json", "internal_leak_probe.json"]


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
        if key == "merged_source":
            value = str(meta.get("merged_curriculum_source") or "unknown")
        elif key == "task":
            value = str(meta.get("repair_task_type") or "unknown")
        elif key == "phrase":
            value = str(target.get("phrase_id") or model_input.get("phrase_id") or "none")
        elif key == "route":
            value = str(model_input.get("opaque_phrase_route_id") or "unknown")
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
    return {name: {**counts, "exact_rate": rate(counts["exact"], counts["rows"]), "target_prefix_rate": rate(counts["target_prefix"], counts["rows"]), "boundary_rate": rate(counts["boundary"], counts["rows"]), "contentful_rate": rate(counts["contentful"], counts["rows"]), "repetition_rate": rate(counts["repetition"], counts["rows"])} for name, counts in sorted(out.items())}


def classify(samples: list[dict[str, Any]], manifest_by_id: dict[str, dict[str, Any]]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    counts = {"keeps_the_repetition": 0, "pator_fragment": 0, "associated_lis": 0, "verified_preserves": 0, "operatch": 0, "other": 0}
    failures: list[dict[str, Any]] = []
    for sample in samples:
        if sample.get("exact_match") and not sample.get("degenerate_repetition"):
            continue
        text = str(sample.get("generated_text") or "")
        labels: list[str] = []
        if "keeps the keeps" in text:
            counts["keeps_the_repetition"] += 1; labels.append("keeps_the_repetition")
        if "pator" in text:
            counts["pator_fragment"] += 1; labels.append("pator_fragment")
        if "associated lis" in text:
            counts["associated_lis"] += 1; labels.append("associated_lis")
        if "verified preserves" in text:
            counts["verified_preserves"] += 1; labels.append("verified_preserves")
        if "operatch" in text:
            counts["operatch"] += 1; labels.append("operatch")
        if not labels:
            counts["other"] += 1; labels.append("other")
        row_id = str(sample.get("row_id"))
        meta = manifest_by_id.get(row_id, {})
        model_input = meta.get("model_input") if isinstance(meta.get("model_input"), dict) else {}
        target = meta.get("target") if isinstance(meta.get("target"), dict) else {}
        failures.append({"row_id": row_id, "split": sample.get("split"), "labels": labels, "merged_source": meta.get("merged_curriculum_source"), "task": meta.get("repair_task_type"), "phrase_id": target.get("phrase_id") or model_input.get("phrase_id"), "route": model_input.get("opaque_phrase_route_id"), "surface": model_input.get("semantic_surface_kind"), "target": sample.get("target_text"), "generated": text, "exact_match": sample.get("exact_match"), "target_prefix_match": sample.get("target_prefix_match"), "degenerate_repetition": sample.get("degenerate_repetition")})
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
    if source.get("passed") is not True: failures.append("source_stage9338_not_passed")
    if contract.get("passed") is not True: failures.append("contract_not_passed")
    if contract.get("generation_prefix_field") != "model_input.active_generation_prefix_span": failures.append("wrong_generation_prefix_field")
    if execution.get("decoder_ce_rows") != 0 or contract.get("loss_counts", {}).get("decoder_ce") != 0: failures.append("decoder_ce_opened")
    if execution.get("runtime_executed") is not False or execution.get("gemma_executed") is not False or execution.get("harness_executed") is not False: failures.append("forbidden_execution_surface_opened")
    if execution.get("final_checkpoint_exported") is not False: failures.append("checkpoint_exported")
    if missing: failures.append("required_artifacts_missing")
    generated = int(samples_card.get("generated_rows") or 0)
    exact = int(samples_card.get("exact_match_rows") or 0)
    target_prefix = int(samples_card.get("target_prefix_match_rows") or 0)
    boundary = int(samples_card.get("boundary_next_token_match_rows") or 0)
    contentful = int(samples_card.get("contentful_rows") or 0)
    repetition_rows = int(repetition_probe.get("generated_repetition_rows") or 0)
    short_rows = int(short_probe.get("short_or_junk_rows") or 0)
    leak_rows = int(leak_probe.get("generated_internal_token_rows") or 0)
    safety_gate_passed = not failures
    quality_gate_passed = bool(generated == 77 and exact == 77 and target_prefix == 77 and boundary == 77 and contentful == 77 and repetition_rows == 0 and short_rows == 0 and leak_rows == 0)
    error_counts, failed_samples = classify(samples, manifest_by_id)
    return {"passed": safety_gate_passed and quality_gate_passed, "safety_gate_passed": safety_gate_passed, "quality_gate_passed": quality_gate_passed, "failures": failures, "missing_artifacts": missing, "manifest_rows": len(manifest_rows), "generated_rows": generated, "exact_match_rows": exact, "exact_match_rate": rate(exact, generated), "target_prefix_match_rate": samples_card.get("target_prefix_match_rate"), "boundary_next_token_match_rate": samples_card.get("boundary_next_token_match_rate"), "boundary_next_token_mean_expected_rank": samples_card.get("boundary_next_token_mean_expected_rank"), "contentful_rate": samples_card.get("contentful_rate"), "short_or_junk_rows": short_rows, "generated_internal_token_rows": leak_rows, "degenerate_repetition_rows": repetition_rows, "by_merged_source": bucket(samples, manifest_by_id, "merged_source"), "by_task": bucket(samples, manifest_by_id, "task"), "by_phrase": bucket(samples, manifest_by_id, "phrase"), "by_route": bucket(samples, manifest_by_id, "route"), "by_surface": bucket(samples, manifest_by_id, "surface"), "by_split": bucket(samples, manifest_by_id, "split"), "error_counts": error_counts, "failed_samples": failed_samples, "diagnosis": "targeted repair rows solved isolated residuals but merged curriculum causes phrase_b/operator rows to collapse into dependency_handle keeps_the repetition; route separation is still insufficient", "next_patch_target": "stage9340_operator_route_separation_and_file_path_with_lis_repair_manifest", "authority": dict(AUTHORITY_CLOSED)}


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
    SUMMARY.parent.mkdir(parents=True, exist_ok=True); DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = audit_run(); AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **audit}, "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))}, "decision": "The merged interference probe executed safely but failed quality gates; decoder CE remains closed.", "next_best_step": "Build Stage9340 operator-route separation and file-path `associated with` repair rows, then test those before rejoining the full mixture again.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9339 Merged Repair Interference Probe Audit", "", f"Passed: `{audit['passed']}`", f"Safety gate passed: `{audit['safety_gate_passed']}`", f"Quality gate passed: `{audit['quality_gate_passed']}`", f"Exact match rows: `{audit['exact_match_rows']}` / `{audit['generated_rows']}`", f"Target prefix match rate: `{audit['target_prefix_match_rate']}`", f"Boundary next-token match rate: `{audit['boundary_next_token_match_rate']}`", f"Contentful generation rate: `{audit['contentful_rate']}`", f"Degenerate repetition rows: `{audit['degenerate_repetition_rows']}`", f"Error counts: `{audit['error_counts']}`", "", "Safety held, but the rejoin failed. Phrase-B/operator examples now collapse toward dependency-handle `keeps the` repetition, plus a small file-path `associated lis` error. Decoder CE remains closed.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["safety_gate_passed", "quality_gate_passed", "exact_match_rate", "target_prefix_match_rate", "boundary_next_token_match_rate", "contentful_rate", "degenerate_repetition_rows", "error_counts"]}}, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
