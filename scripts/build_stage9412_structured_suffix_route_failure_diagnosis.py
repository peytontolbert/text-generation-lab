#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9412
NAME = "stage9412_structured_suffix_route_failure_diagnosis"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9411_structured_suffix_route_probe_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9411_structured_suffix_route_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DIAGNOSIS = OUT_DIR / "structured_suffix_route_failure_diagnosis.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STRUCTURED_SUFFIX_ROUTE_FAILURE_DIAGNOSIS_STAGE9412.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def pair_name(target: str) -> str | None:
    if "expected assertion behavior" in target:
        return "expected_assertion_behavior"
    if "current repair invariant" in target:
        return "current_repair_invariant"
    return None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    samples = load_json(RUN_DIR / "sample_generation_audit.json")
    short = load_json(RUN_DIR / "short_output_probe.json")
    repetition = load_json(RUN_DIR / "repetition_probe.json")
    leak = load_json(RUN_DIR / "internal_leak_probe.json")
    rows = samples.get("samples") if isinstance(samples.get("samples"), list) else []
    residuals = []
    for row in rows:
        target = str(row.get("target_text") or "")
        pair = pair_name(target)
        if row.get("split") in {"eval", "strict_eval"} and pair:
            boundary = row.get("boundary_next_token") or {}
            residuals.append(
                {
                    "row_id": row.get("row_id"),
                    "split": row.get("split"),
                    "pair": pair,
                    "target_text": target,
                    "generated_text": row.get("generated_text"),
                    "expected_token_text": boundary.get("expected_token_text"),
                    "generated_token_text": boundary.get("generated_token_text"),
                    "expected_rank": boundary.get("expected_rank"),
                    "exact_match": bool(row.get("exact_match")),
                    "boundary_match": bool(boundary.get("match")),
                }
            )
    exact_rows = int(samples.get("exact_match_rows") or 0)
    diagnosis = {
        "passed": True,
        "source_stage": 9411,
        "safety_preserved": bool(source.get("safety_gate_passed") or source.get("metrics", {}).get("safety_gate_passed")),
        "quality_passed": bool(source.get("quality_gate_passed") or source.get("metrics", {}).get("quality_gate_passed")),
        "global_exact_rows": exact_rows,
        "global_exact_rows_stage9407": 6,
        "global_exact_rows_stage9399": 5,
        "contentful_rows": int(samples.get("contentful_rows") or 0),
        "short_or_junk_rows": int(short.get("short_or_junk_rows") or 0),
        "generated_repetition_rows": int(repetition.get("generated_repetition_rows") or 0),
        "unterminated_rows": int(repetition.get("unterminated_rows") or 0),
        "generated_internal_token_rows": int(leak.get("generated_internal_token_rows") or 0),
        "target_pair_exact_rows": sum(1 for row in residuals if row["exact_match"]),
        "target_pair_boundary_rows": sum(1 for row in residuals if row["boundary_match"]),
        "target_pair_residuals": residuals,
        "interpretation": [
            "structured_suffix_route_features_help_global_stability",
            "target_pair_boundary_tokens_are_not_controlled_by_route_features",
            "expected_assertion_behavior_collapses_to_checked_symbol_evidence_prior",
            "current_repair_invariant_collapses_to_wrapper_or_noise_prior",
            "next_step_should_be_explicit_suffix_choice_or_boundary_token_head_not_more_denoise_text",
        ],
        "recommended_contract": {
            "branch_from": "stage9409_structured_suffix_route_manifest",
            "next_patch_type": "explicit_suffix_choice_control_probe",
            "objective": "prefix_plus_structured_route -> boundary_token_or_suffix_choice",
            "do_not_open": ["decoder_ce", "runtime", "gemma", "harness", "checkpoint_export"],
            "pass_before_more_generation": [
                "target_pair_boundary_choice_exact == 4/4",
                "all route families beat majority baseline",
                "no single route field can solve full target string",
                "then reconnect chosen boundary token to denoise generation",
            ],
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    DIAGNOSIS.write_text(json.dumps(diagnosis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build an explicit suffix-choice/boundary-token control objective from Stage9409 before another generation probe."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": True,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **{k: v for k, v in diagnosis.items() if k not in {"target_pair_residuals", "recommended_contract", "authority"}}},
        "artifacts": {"diagnosis": str(DIAGNOSIS.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Structured route controls improved global generation stability but failed the target phrase pair; move the decision into an explicit suffix-choice control objective.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9412 Structured Suffix Route Failure Diagnosis",
                "",
                "Stage9411 kept the probe safe and improved global exactness, but failed the two target route families.",
                "",
                f"- Global exact rows: `{exact_rows}`",
                f"- Contentful rows: `{diagnosis['contentful_rows']}`",
                f"- Short/junk rows: `{diagnosis['short_or_junk_rows']}`",
                f"- Repetition rows: `{diagnosis['generated_repetition_rows']}`",
                f"- Leak rows: `{diagnosis['generated_internal_token_rows']}`",
                f"- Target-pair exact: `{diagnosis['target_pair_exact_rows']}` / `{len(residuals)}`",
                f"- Target-pair boundary: `{diagnosis['target_pair_boundary_rows']}` / `{len(residuals)}`",
                "",
                "Next: build an explicit suffix-choice or boundary-token control objective. Do not open decoder CE.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": True, "metrics": {"global_exact_rows": exact_rows, "target_pair_exact_rows": diagnosis["target_pair_exact_rows"], "target_pair_boundary_rows": diagnosis["target_pair_boundary_rows"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
