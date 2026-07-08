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
STAGE = 9408
NAME = "stage9408_minimal_phrase_disambiguation_failure_diagnosis"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9407_minimal_phrase_disambiguation_probe_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9407_minimal_phrase_disambiguation_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DIAGNOSIS = OUT_DIR / "minimal_phrase_disambiguation_failure_diagnosis.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MINIMAL_PHRASE_DISAMBIGUATION_FAILURE_DIAGNOSIS_STAGE9408.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def target_pair(row: dict) -> str | None:
    target = str(row.get("target_text") or "")
    if "expected assertion behavior" in target:
        return "expected_assertion_behavior"
    if "current repair invariant" in target:
        return "current_repair_invariant"
    return None


def compact_residual(row: dict) -> dict:
    boundary = row.get("boundary_next_token") or {}
    return {
        "row_id": row.get("row_id"),
        "split": row.get("split"),
        "pair": target_pair(row),
        "target_text": row.get("target_text"),
        "generated_text": row.get("generated_text"),
        "exact_match": bool(row.get("exact_match")),
        "boundary_match": bool(boundary.get("match")),
        "expected_rank": boundary.get("expected_rank"),
        "expected_token_text": boundary.get("expected_token_text"),
        "generated_token_text": boundary.get("generated_token_text"),
    }


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

    heldout_pair_residuals = [
        compact_residual(row)
        for row in rows
        if row.get("split") in {"eval", "strict_eval"} and target_pair(row)
    ]
    support_residuals = [
        compact_residual(row)
        for row in rows
        if str(row.get("row_id", "")).startswith("stage9405_phrase_disambig")
    ]
    pair_counts = Counter(str(row.get("pair")) for row in heldout_pair_residuals)
    pair_exact = Counter(str(row.get("pair")) for row in heldout_pair_residuals if row.get("exact_match"))
    pair_boundary = Counter(str(row.get("pair")) for row in heldout_pair_residuals if row.get("boundary_match"))
    support_exact = sum(1 for row in support_residuals if row.get("exact_match"))
    support_repetition_rows = [
        row_id
        for row_id in repetition.get("row_ids", [])
        if str(row_id).startswith("stage9405_phrase_disambig")
    ]

    findings = []
    if source.get("safety_gate_passed") is True or source.get("metrics", {}).get("safety_gate_passed") is True:
        findings.append("safety_contract_held")
    if len(heldout_pair_residuals) == 4 and sum(1 for row in heldout_pair_residuals if row.get("exact_match")) == 0:
        findings.append("target_pair_exact_regressed_to_zero")
    if pair_boundary.get("expected_assertion_behavior", 0) == pair_counts.get("expected_assertion_behavior", 0) == 2:
        findings.append("expected_assertion_first_boundary_recovered_but_suffix_copied_support")
    if pair_boundary.get("current_repair_invariant", 0) == 0:
        findings.append("current_repair_invariant_boundary_still_loses_to_answer_focused")
    if support_repetition_rows:
        findings.append("new_phrase_support_row_reintroduced_repetition")
    if support_exact == 0 and len(support_residuals) == 2:
        findings.append("new_phrase_support_rows_not_self_stable")

    recommended_contract = {
        "branch_from": "stage9397_heldout_contrastive_suffix_support_manifest",
        "do_not_build_on": [
            "stage9401_suffix_second_span_support_manifest",
            "stage9405_minimal_phrase_disambiguation_manifest",
        ],
        "blocked_patch_type": "more_surface_phrase_text_support_rows",
        "next_patch_type": "structured_suffix_route_disambiguation_or_suffix_choice_control",
        "requirements": [
            "Keep decoder CE closed.",
            "Use denoise-only or structured-control loss masks.",
            "Do not add exact heldout target copies to train.",
            "Add route/discriminator features outside copied target text, then audit single-feature shortcuts.",
            "Pass support-row self-stability before measuring heldout recovery.",
        ],
        "candidate_fields": [
            "suffix_route_family",
            "suffix_intent_class",
            "post_prefix_continuation_class",
            "avoid_answer_focused_prior",
            "value_small_vs_checked_value_discriminator",
            "current_invariant_vs_generic_answer_discriminator",
        ],
    }

    diagnosis = {
        "passed": True,
        "source_stage": 9407,
        "safety_preserved": bool(source.get("safety_gate_passed") or source.get("metrics", {}).get("safety_gate_passed")),
        "quality_passed": bool(source.get("quality_gate_passed") or source.get("metrics", {}).get("quality_gate_passed")),
        "generated_rows": samples.get("generated_rows"),
        "exact_match_rows": samples.get("exact_match_rows"),
        "target_pair_heldout_rows": len(heldout_pair_residuals),
        "target_pair_exact_rows": sum(1 for row in heldout_pair_residuals if row.get("exact_match")),
        "target_pair_boundary_rows": sum(1 for row in heldout_pair_residuals if row.get("boundary_match")),
        "support_rows": len(support_residuals),
        "support_exact_rows": support_exact,
        "support_repetition_rows": support_repetition_rows,
        "short_or_junk_rows": int(short.get("short_or_junk_rows") or 0),
        "generated_repetition_rows": int(repetition.get("generated_repetition_rows") or 0),
        "unterminated_rows": int(repetition.get("unterminated_rows") or 0),
        "generated_internal_token_rows": int(leak.get("generated_internal_token_rows") or 0),
        "findings": findings,
        "heldout_pair_residuals": heldout_pair_residuals,
        "support_residuals": support_residuals,
        "recommended_contract": recommended_contract,
        "authority": dict(AUTHORITY_CLOSED),
    }
    DIAGNOSIS.write_text(json.dumps(diagnosis, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = "Build a structured suffix-route disambiguation/choice-control manifest from the Stage9397 basis; do not add more phrase-text support rows."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": True,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **{k: v for k, v in diagnosis.items() if k not in {"heldout_pair_residuals", "support_residuals", "recommended_contract", "authority"}}},
        "artifacts": {"diagnosis": str(DIAGNOSIS.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Stage9407 preserved safety but failed quality; phrase-text support is unstable and should not be extended.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9408 Minimal Phrase Disambiguation Failure Diagnosis",
                "",
                "Stage9407 preserved the closed-boundary safety contract, but failed the targeted quality gate.",
                "",
                f"- Target-pair heldout exact: `{diagnosis['target_pair_exact_rows']}` / `{diagnosis['target_pair_heldout_rows']}`",
                f"- Target-pair boundary: `{diagnosis['target_pair_boundary_rows']}` / `{diagnosis['target_pair_heldout_rows']}`",
                f"- New support exact: `{support_exact}` / `{len(support_residuals)}`",
                f"- Support repetition rows: `{support_repetition_rows}`",
                f"- Short/junk rows: `{diagnosis['short_or_junk_rows']}`",
                f"- Leak rows: `{diagnosis['generated_internal_token_rows']}`",
                "",
                "Main findings:",
                "",
                *[f"- `{finding}`" for finding in findings],
                "",
                "Next contract: branch from Stage9397, not Stage9401 or Stage9405. Do not add more surface phrase-text support rows; switch to structured suffix-route disambiguation or a suffix-choice control surface with shortcut audit.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(reg_rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": True, "metrics": {k: diagnosis[k] for k in ["target_pair_exact_rows", "target_pair_boundary_rows", "support_exact_rows", "generated_repetition_rows"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
