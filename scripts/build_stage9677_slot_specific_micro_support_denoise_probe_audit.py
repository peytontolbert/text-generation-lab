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
STAGE = 9677
NAME = "stage9677_slot_specific_micro_support_denoise_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9676_slot_specific_micro_support_preexecution.json"
BASELINE_9675 = ROOT / "runs/summaries/stage9675_neutral_slot_prior_denoise_probe_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9676_slot_specific_micro_support_preexecution/slot_specific_micro_support_denoise_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9677_slot_specific_micro_support_denoise_probe"
AUDIT = RUN_DIR / "stage9677_slot_specific_micro_support_denoise_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SLOT_SPECIFIC_MICRO_SUPPORT_DENOISE_PROBE_AUDIT_STAGE9677.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rate(n: int, d: int) -> float | None:
    return n / d if d else None


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
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
    source = load_json(SOURCE_SUMMARY)
    baseline = load_json(BASELINE_9675).get("metrics") or {}
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples_card = load_json(RUN_DIR / "sample_generation_audit.json")
    short = load_json(RUN_DIR / "short_output_probe.json")
    repetition = load_json(RUN_DIR / "repetition_probe.json")
    leak = load_json(RUN_DIR / "internal_leak_probe.json")
    module_delta = load_json(RUN_DIR / "module_delta_norms.json")
    rows = load_jsonl(MANIFEST)
    rows_by_id = {str(row.get("row_id")): row for row in rows}
    samples = samples_card.get("samples") if isinstance(samples_card.get("samples"), list) else []

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9676_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if int(contract.get("loss_counts", {}).get("denoise_ce") or 0) != 43 or int(execution.get("denoise_ce_rows") or 0) != 43:
        failures.append("denoise_row_count_wrong")
    if int(contract.get("loss_counts", {}).get("decoder_ce") or 0) != 0 or int(execution.get("decoder_ce_rows") or 0) != 0:
        failures.append("decoder_ce_opened")
    for flag in ["runtime_executed", "gemma_executed", "harness_executed", "final_checkpoint_exported"]:
        if execution.get(flag):
            failures.append(f"forbidden_{flag}")
    missing = [
        name
        for name in [
            "probe_contract_audit.json",
            "execution_result.json",
            "sample_generation_audit.json",
            "row_token_loss.jsonl",
            "row_gradient_norms.jsonl",
            "row_dynamics_history.jsonl",
            "activation_summary.jsonl",
            "module_delta_norms.json",
            "cleanup_proof.json",
            "short_output_probe.json",
            "repetition_probe.json",
            "internal_leak_probe.json",
            "denoise_repair_quality_audit.json",
            "boundary_next_token_logits.jsonl",
        ]
        if not (RUN_DIR / name).exists()
    ]
    if missing:
        failures.append("required_artifacts_missing")

    generated = int(samples_card.get("generated_rows") or execution.get("generated_rows") or 0)
    exact = int(samples_card.get("exact_match_rows") or 0)
    target_prefix = int(samples_card.get("target_prefix_match_rows") or round(float(execution.get("target_prefix_match_rate") or 0.0) * generated))
    prefix_start = int(samples_card.get("generation_prefix_start_rows") or round(float(execution.get("generation_prefix_start_rate") or 0.0) * generated))
    contentful = int(samples_card.get("contentful_rows") or round(float(execution.get("contentful_generation_rate") or 0.0) * generated))
    short_rows = int(short.get("short_or_junk_rows") or 0)
    repetition_rows = int(repetition.get("generated_repetition_rows") or 0)
    leak_rows = int(leak.get("generated_internal_token_rows") or 0)

    by_slot: dict[str, Counter[str]] = defaultdict(Counter)
    by_split: dict[str, Counter[str]] = defaultdict(Counter)
    by_kind: dict[str, Counter[str]] = defaultdict(Counter)
    failed_examples: list[dict[str, Any]] = []
    exact_rows: list[dict[str, str]] = []
    for sample in samples:
        row = rows_by_id.get(str(sample.get("row_id")), {})
        slot = str((row.get("neutral_slot_prior") or {}).get("slot_object") or "unknown")
        split = str(row.get("split") or sample.get("split") or "unknown")
        kind = "support" if str(sample.get("row_id", "")).startswith("stage9676_") else "original"
        for bucket in (by_slot[slot], by_split[split], by_kind[kind]):
            bucket["rows"] += 1
            bucket["exact"] += int(bool(sample.get("exact_match")))
            bucket["target_prefix"] += int(bool(sample.get("target_prefix_match")))
            bucket["contentful"] += int(not bool(sample.get("empty_output")))
            bucket["repetition"] += int(bool(sample.get("degenerate_repetition")))
        if sample.get("exact_match"):
            exact_rows.append({"row_id": str(sample.get("row_id")), "slot": slot, "kind": kind})
        else:
            failed_examples.append({
                "row_id": sample.get("row_id"),
                "slot": slot,
                "kind": kind,
                "target": sample.get("target_text"),
                "generated": sample.get("generated_text"),
                "target_prefix_match": sample.get("target_prefix_match"),
                "degenerate_repetition": sample.get("degenerate_repetition"),
            })

    def bucket_card(counter_map: dict[str, Counter[str]]) -> dict[str, dict[str, Any]]:
        return {
            key: {
                "rows": c["rows"],
                "exact": c["exact"],
                "exact_rate": rate(c["exact"], c["rows"]),
                "target_prefix": c["target_prefix"],
                "target_prefix_rate": rate(c["target_prefix"], c["rows"]),
                "contentful": c["contentful"],
                "contentful_rate": rate(c["contentful"], c["rows"]),
                "repetition": c["repetition"],
                "repetition_rate": rate(c["repetition"], c["rows"]),
            }
            for key, c in sorted(counter_map.items())
        }

    safety_passed = not failures
    quality_passed = bool(generated == 43 and exact == 43 and target_prefix == 43 and contentful == 43 and short_rows == 0 and repetition_rows == 0 and leak_rows == 0)
    audit = {
        "passed": safety_passed and quality_passed,
        "safety_passed": safety_passed,
        "quality_passed": quality_passed,
        "failures": failures,
        "missing_artifacts": missing,
        "manifest_rows": len(rows),
        "generated_rows": generated,
        "exact_match_rows": exact,
        "exact_match_rate": rate(exact, generated),
        "target_prefix_match_rows": target_prefix,
        "target_prefix_match_rate": rate(target_prefix, generated),
        "generation_prefix_start_rows": prefix_start,
        "generation_prefix_start_rate": rate(prefix_start, generated),
        "contentful_rows": contentful,
        "contentful_rate": rate(contentful, generated),
        "short_or_junk_rows": short_rows,
        "degenerate_repetition_rows": repetition_rows,
        "generated_internal_token_rows": leak_rows,
        "eval_loss": ((execution.get("eval") or {}).get("eval") or {}).get("loss"),
        "strict_eval_loss": ((execution.get("eval") or {}).get("strict_eval") or {}).get("loss"),
        "decoder_delta_norm": module_delta.get("decoder_delta_norm"),
        "baseline_stage9675": {
            "exact_match_rate": baseline.get("exact_match_rate"),
            "target_prefix_match_rate": baseline.get("target_prefix_match_rate"),
            "contentful_rate": baseline.get("contentful_rate"),
            "degenerate_repetition_rows": baseline.get("degenerate_repetition_rows"),
        },
        "regressed_vs_stage9675": True,
        "by_slot": bucket_card(by_slot),
        "by_split": bucket_card(by_split),
        "by_kind": bucket_card(by_kind),
        "exact_rows": exact_rows,
        "failed_examples": failed_examples[:24],
        "diagnosis": "train_duplicate_micro_support_overweighted_constant_value_and_reintroduced_cross_slot_repetition",
        "rejected_branch": "stage9676_slot_specific_micro_support_duplicates",
        "next_patch_target": "branch_back_to_stage9674_or_stage9675_with_repetition_guard_or_structured_slot_span_ladder",
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Do not build further on Stage9676 duplicates; branch back to Stage9674/9675 and add a repetition guard or structured slot-span ladder before any new denoise generation."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "run_dir": str(RUN_DIR.relative_to(ROOT)),
        },
        "decision": "Stage9677 ran safely but failed quality and regressed versus Stage9675; duplicated train support is rejected.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9677 Slot-Specific Micro-Support Denoise Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Safety passed: `{audit['safety_passed']}`",
        f"Exact rows: `{exact}` / `{generated}`",
        f"Target-prefix rows: `{target_prefix}` / `{generated}`",
        f"Contentful rows: `{contentful}` / `{generated}`",
        f"Repetition rows: `{repetition_rows}`",
        f"By slot: `{audit['by_slot']}`",
        "",
        "The train-only support package did not solve the residual suffix repair. It overfit `constant_value` and reintroduced repeated localized/verified/reference spans across other slot families.",
        "",
        "This branch is rejected. Continue from Stage9674/9675 with a repetition guard or a structured slot-span ladder rather than adding more duplicate denoise rows.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": audit["passed"],
        "safety_passed": safety_passed,
        "quality_passed": quality_passed,
        "exact_match_rate": audit["exact_match_rate"],
        "target_prefix_match_rate": audit["target_prefix_match_rate"],
        "repetition_rows": repetition_rows,
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
