#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9537
NAME = "stage9537_episode_obs_diag_component_overlay_analysis"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9525_episode_obs_diag_residual_gate_manifest/episode_obs_diag_residual_gate_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9536_episode_obs_diag_python_boundary_upsample_probe_audit.json"
BASE_SUMMARY = ROOT / "runs/summaries/stage9528_episode_obs_diag_residual_gate_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9537_episode_obs_diag_component_overlay_analysis"
ANALYSIS = OUT_DIR / "episode_obs_diag_component_overlay_analysis.json"
ROW_ANALYSIS = OUT_DIR / "episode_obs_diag_component_overlay_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_COMPONENT_OVERLAY_ANALYSIS_STAGE9537.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


ORDERED_REASONS = [
    "not_exact",
    "target_prefix_miss",
    "boundary_next_token_miss",
    "degenerate_repetition",
    "unterminated",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def observed_reasons(row: dict) -> list[str]:
    transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    observation = transition.get("observation_t") if isinstance(transition.get("observation_t"), dict) else {}
    reasons = observation.get("residual_reasons")
    if isinstance(reasons, list):
        return [str(reason) for reason in reasons]
    return []


def compose_failure_type(row: dict) -> str:
    reasons = set(observed_reasons(row))
    ordered = [reason for reason in ORDERED_REASONS if reason in reasons]
    return "none" if not ordered else "+".join(ordered)


def target_failure_type(row: dict) -> str:
    transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    verifier = transition.get("reward_or_verifier") if isinstance(transition.get("reward_or_verifier"), dict) else {}
    return str(verifier.get("failure_type") or "none")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    base = load_json(BASE_SUMMARY)
    rows = load_jsonl(SOURCE_MANIFEST)
    failures: list[str] = []
    if source.get("metrics", {}).get("safety_passed") is not True:
        failures.append("stage9536_not_safe")
    if base.get("metrics", {}).get("safety_passed") is not True:
        failures.append("stage9528_not_safe")
    if not rows:
        failures.append("missing_source_rows")

    split_counts = Counter()
    target_counts = Counter()
    composed_counts = Counter()
    overlay_exact_by_split = Counter()
    overlay_rows_by_split = Counter()
    mismatches: list[dict] = []
    row_records: list[dict] = []
    for row in rows:
        split = str(row.get("split"))
        target = target_failure_type(row)
        composed = compose_failure_type(row)
        exact = target == composed
        split_counts[split] += 1
        target_counts[target] += 1
        composed_counts[composed] += 1
        overlay_rows_by_split[split] += 1
        overlay_exact_by_split[split] += int(exact)
        record = {
            "row_id": row.get("row_id"),
            "split": split,
            "language_family": row.get("language_family"),
            "target_failure_type": target,
            "composed_failure_type": composed,
            "exact": exact,
            "observed_reasons": observed_reasons(row),
            "obs_prefix_relation": (row.get("model_input") or {}).get("obs_prefix_relation"),
            "obs_boundary_relation": (row.get("model_input") or {}).get("obs_boundary_relation"),
        }
        row_records.append(record)
        if not exact:
            mismatches.append(record)

    overlay_exact_rates = {
        split: (overlay_exact_by_split[split] / overlay_rows_by_split[split])
        for split in sorted(overlay_rows_by_split)
    }
    if mismatches:
        failures.append("component_overlay_mismatches")
    if overlay_exact_rates.get("eval") != 1.0 or overlay_exact_rates.get("strict_eval") != 1.0:
        failures.append("component_overlay_eval_or_strict_not_exact")

    ROW_ANALYSIS.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in row_records))
    analysis = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "target_counts": dict(sorted(target_counts.items())),
        "composed_counts": dict(sorted(composed_counts.items())),
        "overlay_exact_rates": overlay_exact_rates,
        "mismatches": mismatches,
        "stage9528_learned_eval_exact": base.get("metrics", {}).get("final_eval_joint_proxy_exact"),
        "stage9528_learned_strict_exact": base.get("metrics", {}).get("final_strict_joint_proxy_exact"),
        "stage9536_upsample_eval_exact": source.get("metrics", {}).get("final_eval_joint_proxy_exact"),
        "stage9536_upsample_strict_exact": source.get("metrics", {}).get("final_strict_joint_proxy_exact"),
        "decision": "Use deterministic observation-component composition as effective failure_type authority; keep learned composite failure_type head as telemetry.",
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "promotion_ready": False,
    }
    ANALYSIS.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": analysis["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **analysis},
        "artifacts": {
            "analysis": str(ANALYSIS.relative_to(ROOT)),
            "rows": str(ROW_ANALYSIS.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": analysis["decision"],
        "next_best_step": "Build Stage9538 component-overlay contract that records effective_failure_type_composed_from_observation while keeping learned failure_type telemetry-only; do not run another training probe until this authority split is audited.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9537 Episode Observation Diagnosis Component Overlay Analysis",
        "",
        f"Passed: `{analysis['passed']}`",
        f"Rows: `{len(rows)}`",
        f"Split counts: `{dict(split_counts)}`",
        f"Overlay exact rates: `{overlay_exact_rates}`",
        f"Stage9528 learned eval/strict: `{analysis['stage9528_learned_eval_exact']}` / `{analysis['stage9528_learned_strict_exact']}`",
        f"Stage9536 upsample eval/strict: `{analysis['stage9536_upsample_eval_exact']}` / `{analysis['stage9536_upsample_strict_exact']}`",
        "",
        analysis["decision"],
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": analysis["passed"], "overlay_exact_rates": overlay_exact_rates, "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
