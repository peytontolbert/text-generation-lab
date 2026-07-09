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
STAGE = 9608
NAME = "stage9608_prefix_primed_suffix_continuation_failure_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9607_prefix_primed_two_phase_tiny_probe.json"
PHASE2_DIR = ROOT / "runs/local/artifacts/stage9607_prefix_primed_two_phase_tiny_probe/two_phase_probe/phase2_residual_denoise_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "prefix_primed_suffix_continuation_failure_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PREFIX_PRIMED_SUFFIX_CONTINUATION_FAILURE_AUDIT_STAGE9608.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
    source = load_json(SOURCE_SUMMARY)
    generation = load_json(PHASE2_DIR / "sample_generation_audit.json")
    repetition = load_json(PHASE2_DIR / "repetition_probe.json")
    quality = load_json(PHASE2_DIR / "denoise_repair_quality_audit.json")
    step_losses = load_jsonl(PHASE2_DIR / "loss_by_step.jsonl")
    eval_losses = load_jsonl(PHASE2_DIR / "eval_loss_by_checkpoint.jsonl")
    samples = generation.get("samples") if isinstance(generation.get("samples"), list) else []

    boundary_available = 0
    boundary_match = 0
    repeated_rows: list[str] = []
    mismatch_after_boundary: list[dict[str, Any]] = []
    generated_phrase_counts = Counter()
    for sample in samples:
        row_id = str(sample.get("row_id"))
        boundary = sample.get("boundary_next_token") if isinstance(sample.get("boundary_next_token"), dict) else {}
        if boundary.get("available"):
            boundary_available += 1
        if boundary.get("match"):
            boundary_match += 1
        generated = str(sample.get("generated_text") or "")
        for phrase in ["localized by the localized", "relevant rep", " inv inv", "?roduce an"]:
            if phrase in generated:
                generated_phrase_counts[phrase] += 1
        if sample.get("degenerate_repetition"):
            repeated_rows.append(row_id)
        if sample.get("generation_prefix_start_match") and boundary.get("match") and not sample.get("target_prefix_match"):
            mismatch_after_boundary.append(
                {
                    "row_id": row_id,
                    "split": sample.get("split"),
                    "prefix": sample.get("generation_prefix_text"),
                    "expected_next": boundary.get("expected_token_text"),
                    "generated_excerpt": generated[:180],
                    "target_excerpt": str(sample.get("target_text") or "")[:180],
                }
            )

    train_losses = [float(row["loss"]) for row in step_losses if "loss" in row]
    loss_first = train_losses[0] if train_losses else None
    loss_last = train_losses[-1] if train_losses else None
    eval_by_split = {str(row.get("split")): row.get("loss") for row in eval_losses}

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9607_safety_probe_not_passed")
    if source.get("metrics", {}).get("quality_gate") is not False:
        failures.append("stage9607_quality_gate_not_failed_as_expected")
    if generation.get("generation_prefix_start_rate") != 1.0:
        failures.append("prefix_start_not_solved")
    if (generation.get("boundary_next_token_match_rate") or 0.0) < 0.9:
        failures.append("boundary_next_token_not_solved_enough")
    if (repetition.get("degenerate_repetition_rate") or 0.0) < 0.5:
        failures.append("repetition_not_primary_failure")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "phase2_dir": str(PHASE2_DIR.relative_to(ROOT)),
        "stage9607_quality_gate": source.get("metrics", {}).get("quality_gate"),
        "phase1_eval_suffix_choice_exact": source.get("metrics", {}).get("phase1_eval_suffix_choice_exact"),
        "phase1_strict_suffix_choice_exact": source.get("metrics", {}).get("phase1_strict_suffix_choice_exact"),
        "phase2_generation_prefix_start_rate": generation.get("generation_prefix_start_rate"),
        "phase2_boundary_next_token_match_rate": generation.get("boundary_next_token_match_rate"),
        "phase2_contentful_generation_rate": quality.get("contentful_generation_rate"),
        "phase2_target_prefix_match_rate": quality.get("target_prefix_match_rate"),
        "phase2_degenerate_repetition_rate": repetition.get("degenerate_repetition_rate"),
        "phase2_unterminated_rate": repetition.get("unterminated_rate"),
        "boundary_available_rows": boundary_available,
        "boundary_match_rows": boundary_match,
        "mismatch_after_boundary_rows": len(mismatch_after_boundary),
        "mismatch_after_boundary_examples": mismatch_after_boundary[:8],
        "repeated_rows": repeated_rows,
        "generated_phrase_counts": dict(generated_phrase_counts),
        "phase2_loss_first": loss_first,
        "phase2_loss_last": loss_last,
        "phase2_eval_loss_by_split": eval_by_split,
        "root_cause": {
            "suffix_choice_gate_solved": True,
            "prefix_priming_solved": generation.get("generation_prefix_start_rate") == 1.0,
            "first_suffix_token_mostly_solved": (generation.get("boundary_next_token_match_rate") or 0.0) >= 0.9,
            "multi_token_suffix_continuation_failed": True,
            "needs_ladder_or_second_span_support": True,
        },
        "recommended_patch": {
            "stage9609": "build_suffix_continuation_ladder_manifest",
            "requirements": [
                "derive rows from Stage9605 clean targets",
                "train short second-span continuations before full suffix",
                "keep active_generation_prefix_span audited and under cap",
                "include anti-repetition negatives for localized/relevant/inv loops",
                "keep decoder_ce/runtime/Gemma/harness/export closed",
                "run contract-only preflight before execution",
            ],
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build Stage9609 suffix-continuation ladder/support manifest from Stage9605, then run contract-only preflight before another tiny probe."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Stage9607 solved suffix choice, prefix priming, and most boundary-next-token predictions, but failed multi-token suffix continuation through local phrase repetition.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9608 Prefix-Primed Suffix Continuation Failure Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Prefix start rate: `{audit['phase2_generation_prefix_start_rate']}`",
                f"Boundary next-token match rate: `{audit['phase2_boundary_next_token_match_rate']}`",
                f"Target prefix match rate: `{audit['phase2_target_prefix_match_rate']}`",
                f"Degenerate repetition rate: `{audit['phase2_degenerate_repetition_rate']}`",
                f"Loss first/last: `{audit['phase2_loss_first']}` / `{audit['phase2_loss_last']}`",
                "",
                "Finding: the reconnect is no longer failing at the controller or prefix boundary. It fails after the first suffix token, usually by repeating local fragments such as `localized by the localized`, `relevant rep`, or `inv inv`.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
