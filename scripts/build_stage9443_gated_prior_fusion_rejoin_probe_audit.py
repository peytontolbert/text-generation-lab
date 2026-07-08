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
STAGE = 9443
NAME = "stage9443_gated_prior_fusion_rejoin_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9442_gated_prior_fusion_rejoin_preexecution.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9441_gated_prior_fusion_rejoin_manifest/gated_prior_fusion_rejoin_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9443_gated_prior_fusion_rejoin_probe"
AUDIT = RUN_DIR / "stage9443_gated_prior_fusion_rejoin_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GATED_PRIOR_FUSION_REJOIN_PROBE_AUDIT_STAGE9443.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUIRED = [
    "probe_contract_audit.json",
    "execution_result.json",
    "sample_generation_audit.json",
    "boundary_next_token_logits.jsonl",
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "row_dynamics_history.jsonl",
    "activation_summary.jsonl",
    "module_delta_norms.json",
    "cleanup_proof.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def split_metrics(samples: list[dict]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter] = defaultdict(Counter)
    for sample in samples:
        split = str(sample.get("split"))
        counts[split]["rows"] += 1
        counts[split]["exact"] += int(bool(sample.get("exact_match")))
        counts[split]["prefix"] += int(bool(sample.get("target_prefix_match")))
        counts[split]["boundary"] += int(bool((sample.get("boundary_next_token") or {}).get("match")))
        counts[split]["contentful"] += int(not bool(sample.get("empty_output")) and not bool(sample.get("short_or_junk")))
        counts[split]["short"] += int(bool(sample.get("short_or_junk")))
        counts[split]["repetition"] += int(bool(sample.get("degenerate_repetition")))
        counts[split]["unterminated"] += int(not bool(sample.get("stopped_on_eos")))
    return {split: dict(counter) for split, counter in sorted(counts.items())}


def residual_rows(samples: list[dict], manifest_by_id: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    for sample in samples:
        if sample.get("exact_match") and sample.get("target_prefix_match") and not sample.get("degenerate_repetition"):
            continue
        row_id = str(sample.get("row_id"))
        source = manifest_by_id.get(row_id, {})
        prior = source.get("suffix_choice_prior") if isinstance(source.get("suffix_choice_prior"), dict) else {}
        rows.append(
            {
                "row_id": row_id,
                "split": sample.get("split"),
                "exact_match": bool(sample.get("exact_match")),
                "target_prefix_match": bool(sample.get("target_prefix_match")),
                "boundary_next_token_match": bool((sample.get("boundary_next_token") or {}).get("match")),
                "contentful": not bool(sample.get("empty_output")) and not bool(sample.get("short_or_junk")),
                "degenerate_repetition": bool(sample.get("degenerate_repetition")),
                "stopped_on_eos": bool(sample.get("stopped_on_eos")),
                "generated_text": sample.get("generated_text"),
                "target_text": sample.get("target_text"),
                "route": source.get("route"),
                "suffix_choice_prior_source": source.get("suffix_choice_prior_source"),
                "suffix_choice_prior": prior,
            }
        )
    return rows


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples_card = load_json(RUN_DIR / "sample_generation_audit.json")
    short_probe = load_json(RUN_DIR / "short_output_probe.json")
    repetition_probe = load_json(RUN_DIR / "repetition_probe.json")
    leak_probe = load_json(RUN_DIR / "internal_leak_probe.json")
    cleanup = load_json(RUN_DIR / "cleanup_proof.json")
    manifest_rows = load_jsonl(MANIFEST)
    manifest_by_id = {str(row.get("row_id")): row for row in manifest_rows}
    samples = samples_card.get("samples") if isinstance(samples_card.get("samples"), list) else []
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]
    by_split = split_metrics(samples)
    residuals = residual_rows(samples, manifest_by_id)

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9442_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if contract.get("loss_counts", {}).get("denoise_ce") != 50 or contract.get("loss_counts", {}).get("decoder_ce") != 0:
        failures.append("loss_counts_mismatch")
    if execution.get("runtime_executed") or execution.get("gemma_executed") or execution.get("harness_executed"):
        failures.append("forbidden_execution_surface_opened")
    if execution.get("final_checkpoint_exported"):
        failures.append("checkpoint_exported")
    if cleanup.get("cleanup_executed") is not False:
        failures.append("unexpected_cleanup_execution")
    if missing:
        failures.append("required_artifacts_missing")

    generated = int(samples_card.get("generated_rows") or 0)
    exact = int(samples_card.get("exact_match_rows") or 0)
    prefix = int(samples_card.get("target_prefix_match_rows") or 0)
    boundary = int(samples_card.get("boundary_next_token_match_rows") or 0)
    contentful = int(samples_card.get("contentful_rows") or 0)
    short_rows = int(short_probe.get("short_or_junk_rows") or 0)
    leak_rows = int(leak_probe.get("generated_internal_token_rows") or 0)
    repetition_rows = int(repetition_probe.get("generated_repetition_rows") or 0)
    unterminated_rows = int(repetition_probe.get("unterminated_rows") or 0)
    heldout_exact = by_split.get("eval", {}).get("exact", 0) + by_split.get("strict_eval", {}).get("exact", 0)
    heldout_rows = by_split.get("eval", {}).get("rows", 0) + by_split.get("strict_eval", {}).get("rows", 0)

    safety_gate_passed = not failures and generated == 50 and leak_rows == 0 and short_rows == 0
    quality_gate_passed = bool(
        safety_gate_passed
        and exact == generated
        and prefix == generated
        and boundary == generated
        and contentful == generated
        and repetition_rows == 0
        and unterminated_rows == 0
        and heldout_exact == heldout_rows
    )

    audit = {
        "passed": safety_gate_passed and quality_gate_passed,
        "safety_gate_passed": safety_gate_passed,
        "quality_gate_passed": quality_gate_passed,
        "failures": failures,
        "missing_artifacts": missing,
        "generated_rows": generated,
        "exact_match_rows": exact,
        "target_prefix_match_rows": prefix,
        "target_prefix_match_rate": samples_card.get("target_prefix_match_rate"),
        "boundary_next_token_match_rows": boundary,
        "boundary_next_token_match_rate": samples_card.get("boundary_next_token_match_rate"),
        "contentful_rows": contentful,
        "contentful_rate": samples_card.get("contentful_rate"),
        "short_or_junk_rows": short_rows,
        "generated_internal_token_rows": leak_rows,
        "degenerate_repetition_rows": repetition_rows,
        "degenerate_repetition_rate": repetition_probe.get("degenerate_repetition_rate"),
        "unterminated_rows": unterminated_rows,
        "heldout_exact_rows": heldout_exact,
        "heldout_rows": heldout_rows,
        "split_metrics": by_split,
        "residual_rows": len(residuals),
        "residual_examples": residuals[:12],
        "diagnosis": (
            "Gated prior-fusion rejoin remains execution-safe and reduces repetition versus Stage9437, "
            "but it is not quality-passing: exact and boundary-next-token accuracy remain too low, "
            "contentfulness is not complete, and a small repetition/unterminated pocket remains."
        ),
        "next_patch_target": "stage9444_gated_prior_rejoin_residual_diagnosis",
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")

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
        "decision": "The gated prior-fusion rejoin denoise probe is safety-clean but not quality-passing; decoder CE remains closed.",
        "next_best_step": "Build Stage9444 residual diagnosis: separate suffix-token misses, remaining repetition/unterminated rows, and contentfulness failures before any wider denoise training.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    DOC.write_text(
        "\n".join(
            [
                "# Stage9443 Gated Prior Fusion Rejoin Probe Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Safety gate passed: `{audit['safety_gate_passed']}`",
                f"Quality gate passed: `{audit['quality_gate_passed']}`",
                "",
                f"Generated rows: `{generated}`",
                f"Exact rows: `{exact}` / `{generated}`",
                f"Target-prefix rows: `{prefix}` / `{generated}`",
                f"Boundary next-token rows: `{boundary}` / `{generated}`",
                f"Contentful rows: `{contentful}` / `{generated}`",
                f"Short/junk rows: `{short_rows}`",
                f"Repetition rows: `{repetition_rows}`",
                f"Unterminated rows: `{unterminated_rows}`",
                f"Leak rows: `{leak_rows}`",
                f"Heldout exact rows: `{heldout_exact}` / `{heldout_rows}`",
                "",
                "Decoder CE remains closed. The next step is residual diagnosis, not widening.",
                "",
                "## Episode/Step Curriculum Note",
                "",
                "This probe remains a single-step denoise transition. The larger maintainer curriculum should keep "
                "episodes as ordered sequences of observe/orient/action/verify/repair steps, with each step yielding "
                "a typed state-action-observation transition row for supervised or verifier-rewarded training.",
                "",
            ]
        )
    )

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
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "metrics": {
                    "safety_gate_passed": safety_gate_passed,
                    "quality_gate_passed": quality_gate_passed,
                    "exact_match_rows": exact,
                    "generated_rows": generated,
                    "contentful_rows": contentful,
                    "boundary_next_token_match_rows": boundary,
                    "degenerate_repetition_rows": repetition_rows,
                    "heldout_exact_rows": heldout_exact,
                    "heldout_rows": heldout_rows,
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
