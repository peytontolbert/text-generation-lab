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
STAGE = 9580
NAME = "stage9580_residual_denoise_prefix_primed_token_bias_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9579_residual_denoise_boundary_prefix_primed_capped_probe.json"
SAMPLES = ROOT / "runs/local/artifacts/stage9579_residual_denoise_boundary_prefix_primed_capped_probe/denoise_repair_probe/sample_generation_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "residual_denoise_prefix_primed_token_bias_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_PREFIX_PRIMED_TOKEN_BIAS_AUDIT_STAGE9580.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    metrics = source.get("metrics") or {}
    samples = load_json(SAMPLES).get("samples") or []
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9579_not_passed")
    if metrics.get("sample_balanced") is not True:
        failures.append("stage9579_sample_not_balanced")
    if metrics.get("boundary_recall") != 1.0:
        failures.append("stage9579_boundary_recall_not_one")
    if metrics.get("prefix_recall") != 0.0:
        failures.append("stage9579_prefix_recall_not_zero")

    expected_token_counts: Counter[str] = Counter()
    generated_token_counts: Counter[str] = Counter()
    expected_ranks: Counter[str] = Counter()
    expected_prob_sum: Counter[str] = Counter()
    expected_prob_n: Counter[str] = Counter()
    for row in samples:
        boundary_next = row.get("boundary_next_token") if isinstance(row.get("boundary_next_token"), dict) else {}
        expected = str(boundary_next.get("expected_token_text") or "")
        generated = str(boundary_next.get("generated_token_text") or "")
        expected_token_counts[expected] += 1
        generated_token_counts[generated] += 1
        if boundary_next.get("expected_rank") is not None:
            expected_ranks[f"{expected}:rank_{boundary_next.get('expected_rank')}"] += 1
        if boundary_next.get("expected_probability") is not None:
            expected_prob_sum[expected] += float(boundary_next.get("expected_probability"))
            expected_prob_n[expected] += 1
    expected_prob_mean = {
        key: expected_prob_sum[key] / max(1, expected_prob_n[key])
        for key in sorted(expected_prob_sum)
    }
    boundary_literal_bias_confirmed = (
        metrics.get("sample_balanced") is True
        and metrics.get("boundary_recall") == 1.0
        and metrics.get("prefix_recall") == 0.0
        and dict(generated_token_counts) == {"B": 16}
        and expected_token_counts.get("B") == 8
        and expected_token_counts.get("P") == 8
    )
    if not boundary_literal_bias_confirmed:
        failures.append("boundary_literal_bias_not_confirmed")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "sample_generation_audit": str(SAMPLES.relative_to(ROOT)),
        "sample_balanced": metrics.get("sample_balanced"),
        "boundary_recall": metrics.get("boundary_recall"),
        "prefix_recall": metrics.get("prefix_recall"),
        "boundary_next_token_match_rate": metrics.get("boundary_next_token_match_rate"),
        "expected_token_counts": dict(sorted(expected_token_counts.items())),
        "generated_token_counts": dict(sorted(generated_token_counts.items())),
        "expected_ranks": dict(sorted(expected_ranks.items())),
        "expected_probability_mean_by_token": expected_prob_mean,
        "boundary_literal_bias_confirmed": boundary_literal_bias_confirmed,
        "widening_authorized": False,
        "model_execution_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "promotion_ready": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "The prefix-primed probe learned the literal BOUNDARY route for every row. Prefix rows still rank P second, so the next patch should use neutral YES/NO decision tokens rather than literal class names.",
        "next_best_step": "Build a neutral boundary-decision manifest with shared REPAIR_DECISION= prefix and YES/NO class tokens derived from verifier boundary-miss evidence.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9580 Residual Denoise Prefix-Primed Token Bias Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Boundary literal bias confirmed: `{boundary_literal_bias_confirmed}`",
                f"Expected tokens: `{dict(sorted(expected_token_counts.items()))}`",
                f"Generated tokens: `{dict(sorted(generated_token_counts.items()))}`",
                "",
                "The next target surface should avoid literal `BOUNDARY`/`PREFIX` class words and use neutral decision tokens.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "boundary_literal_bias_confirmed": boundary_literal_bias_confirmed, "failures": failures}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
