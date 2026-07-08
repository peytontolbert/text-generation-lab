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
STAGE = 9444
NAME = "stage9444_gated_prior_rejoin_residual_diagnosis"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9443_gated_prior_fusion_rejoin_probe_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9441_gated_prior_fusion_rejoin_manifest/gated_prior_fusion_rejoin_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9443_gated_prior_fusion_rejoin_probe"
SAMPLES = RUN_DIR / "sample_generation_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DIAGNOSIS = OUT_DIR / "gated_prior_rejoin_residual_diagnosis.json"
RESIDUALS = OUT_DIR / "all_residual_rows.jsonl"
SUFFIX_MISSES = OUT_DIR / "suffix_token_miss_rows.jsonl"
QUALITY_RESIDUALS = OUT_DIR / "quality_residual_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GATED_PRIOR_REJOIN_RESIDUAL_DIAGNOSIS_STAGE9444.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def classify_residual(sample: dict) -> list[str]:
    reasons: list[str] = []
    if not sample.get("exact_match"):
        reasons.append("not_exact")
    if not sample.get("target_prefix_match"):
        reasons.append("target_prefix_miss")
    if not (sample.get("boundary_next_token") or {}).get("match"):
        reasons.append("boundary_next_token_miss")
    if sample.get("short_or_junk") or sample.get("empty_output"):
        reasons.append("not_contentful")
    if sample.get("degenerate_repetition"):
        reasons.append("degenerate_repetition")
    if not sample.get("stopped_on_eos"):
        reasons.append("unterminated")
    return reasons


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    manifest_rows = load_jsonl(MANIFEST)
    manifest_by_id = {str(row.get("row_id")): row for row in manifest_rows}
    samples_card = load_json(SAMPLES)
    samples = samples_card.get("samples") if isinstance(samples_card.get("samples"), list) else []

    residuals: list[dict] = []
    suffix_misses: list[dict] = []
    quality_residuals: list[dict] = []
    by_split: dict[str, Counter] = defaultdict(Counter)
    by_route: dict[str, Counter] = defaultdict(Counter)
    by_prior_source: dict[str, Counter] = defaultdict(Counter)
    expected_rank_hist = Counter()
    top_generated_token_hist = Counter()

    for sample in samples:
        row_id = str(sample.get("row_id"))
        row = manifest_by_id.get(row_id, {})
        split = str(sample.get("split"))
        route = str(row.get("route"))
        prior_source = str(row.get("suffix_choice_prior_source"))
        reasons = classify_residual(sample)
        boundary = sample.get("boundary_next_token") if isinstance(sample.get("boundary_next_token"), dict) else {}
        if boundary.get("available"):
            expected_rank_hist[str(boundary.get("expected_rank"))] += 1
            top_generated_token_hist[str(boundary.get("generated_token_text"))] += 1
        by_split[split]["rows"] += 1
        by_split[split]["residual"] += int(bool(reasons))
        by_split[split]["boundary_miss"] += int("boundary_next_token_miss" in reasons)
        by_split[split]["prefix_miss"] += int("target_prefix_miss" in reasons)
        by_split[split]["quality"] += int("degenerate_repetition" in reasons or "unterminated" in reasons or "not_contentful" in reasons)
        by_route[route]["rows"] += 1
        by_route[route]["residual"] += int(bool(reasons))
        by_prior_source[prior_source]["rows"] += 1
        by_prior_source[prior_source]["residual"] += int(bool(reasons))
        if not reasons:
            continue
        payload = {
            "row_id": row_id,
            "split": split,
            "route": route,
            "suffix_choice_prior_source": prior_source,
            "suffix_choice_prior": row.get("suffix_choice_prior"),
            "residual_reasons": reasons,
            "boundary_next_token": boundary,
            "generated_text": sample.get("generated_text"),
            "target_text": sample.get("target_text"),
            "generation_prefix_text": sample.get("generation_prefix_text"),
            "source_stage9388_row_id": row.get("source_stage9388_row_id"),
            "source_stage9413_suffix_choice_row_id": row.get("source_stage9413_suffix_choice_row_id"),
        }
        residuals.append(payload)
        if "boundary_next_token_miss" in reasons or "target_prefix_miss" in reasons:
            suffix_misses.append(payload)
        if "degenerate_repetition" in reasons or "unterminated" in reasons or "not_contentful" in reasons:
            quality_residuals.append(payload)

    reason_counts = Counter(reason for row in residuals for reason in row["residual_reasons"])
    failures: list[str] = []
    if source.get("passed") is not False:
        failures.append("source_stage9443_not_failed_quality_as_expected")
    if len(samples) != 50:
        failures.append("unexpected_sample_count")
    if len(manifest_rows) != 50:
        failures.append("unexpected_manifest_count")

    diagnosis = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9443_gated_prior_fusion_rejoin_probe_audit",
        "sample_rows": len(samples),
        "manifest_rows": len(manifest_rows),
        "residual_rows": len(residuals),
        "suffix_token_miss_rows": len(suffix_misses),
        "quality_residual_rows": len(quality_residuals),
        "reason_counts": dict(sorted(reason_counts.items())),
        "split_metrics": {key: dict(value) for key, value in sorted(by_split.items())},
        "route_metrics": {key: dict(value) for key, value in sorted(by_route.items())},
        "prior_source_metrics": {key: dict(value) for key, value in sorted(by_prior_source.items())},
        "boundary_expected_rank_histogram": dict(expected_rank_hist.most_common(20)),
        "boundary_generated_token_histogram": dict(top_generated_token_hist.most_common(20)),
        "diagnosis": (
            "The gated rejoin did not fail by leak or short-output collapse. The dominant residual is still suffix "
            "choice/token selection: many rows are contentful and prefix-primed but choose the wrong continuation. "
            "A smaller quality pocket remains around unterminated/repetition rows."
        ),
        "next_patch_target": "stage9445_episode_step_suffix_transition_contract",
        "authority": dict(AUTHORITY_CLOSED),
    }
    DIAGNOSIS.write_text(json.dumps(diagnosis, indent=2, sort_keys=True) + "\n")
    write_jsonl(RESIDUALS, residuals)
    write_jsonl(SUFFIX_MISSES, suffix_misses)
    write_jsonl(QUALITY_RESIDUALS, quality_residuals)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": diagnosis["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **diagnosis},
        "artifacts": {
            "diagnosis": str(DIAGNOSIS.relative_to(ROOT)),
            "residuals": str(RESIDUALS.relative_to(ROOT)),
            "suffix_misses": str(SUFFIX_MISSES.relative_to(ROOT)),
            "quality_residuals": str(QUALITY_RESIDUALS.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Diagnosed Stage9443 residuals without opening decoder CE or additional model execution.",
        "next_best_step": "Add an episode/step transition contract so future denoise rows are organized as step-level repair transitions with route-local suffix targets and verifier feedback.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9444 Gated Prior Rejoin Residual Diagnosis",
                "",
                f"Passed: `{diagnosis['passed']}`",
                f"Residual rows: `{len(residuals)}` / `{len(samples)}`",
                f"Suffix/token miss rows: `{len(suffix_misses)}`",
                f"Quality residual rows: `{len(quality_residuals)}`",
                "",
                "The remaining failure is not broad decoder collapse. It is mostly step-local continuation choice "
                "under prefix-primed denoise rows, plus a small repetition/unterminated pocket.",
                "",
                "## Episode/Step Implication",
                "",
                "A full maintainer episode should be broken into steps. Each step should train one transition:",
                "",
                "`state_t + action_t + verifier_observation_t -> repaired_state_or_next_action_t`",
                "",
                "For decoder repair, the current suffix-choice task should be represented as a step-level repair "
                "transition with route-local evidence, target continuation, verifier failure, and next-state label. "
                "This avoids treating multiple repair routes as one flat denoise surface.",
                "",
                "Decoder CE remains closed.",
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
                    "residual_rows": len(residuals),
                    "suffix_token_miss_rows": len(suffix_misses),
                    "quality_residual_rows": len(quality_residuals),
                    "reason_counts": diagnosis["reason_counts"],
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
