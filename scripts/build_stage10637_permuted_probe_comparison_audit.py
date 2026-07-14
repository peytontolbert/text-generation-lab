#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10637
NAME = "stage10637_permuted_probe_comparison_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "permuted_probe_comparison_audit.json"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

RUN_10632 = ROOT / "runs/local/artifacts/stage10632_repaired_long_context_successor_probe/bounded_decoder_probe/execution_result.json"
RUN_10636 = ROOT / "runs/local/artifacts/stage10636_repaired_long_context_successor_probe_permuted/bounded_decoder_probe/execution_result.json"
LABEL_AUDIT_10633 = ROOT / "runs/local/artifacts/stage10633_repaired_long_context_label_position_audit/repaired_long_context_label_position_audit.json"
GEN_AUDIT_10636 = ROOT / "runs/local/artifacts/stage10636_repaired_long_context_successor_probe_permuted/bounded_decoder_probe/sample_generation_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def extract_strict_first_token_metrics(execution_result: dict[str, Any]) -> dict[str, Any]:
    strict = (((execution_result.get("bounded_choice_eval") or {}).get("strict_eval")) or {})
    return {
        "rows": strict.get("rows"),
        "rows_with_target_rank_1": strict.get("rows_with_target_rank_1"),
        "full_vocab_top1_accuracy": strict.get("full_vocab_top1_accuracy"),
    }


def extract_eval_decisive_exact(gen_audit: dict[str, Any]) -> dict[str, Any]:
    samples = gen_audit.get("samples") or []
    decisive_eval = [
        sample
        for sample in samples
        if sample.get("split") == "eval" and "decisive_evidence" in str(sample.get("row_id", ""))
    ]
    exact = sum(1 for sample in decisive_eval if sample.get("exact_match"))
    prefix = sum(1 for sample in decisive_eval if sample.get("target_prefix_match"))
    short = sum(1 for sample in decisive_eval if sample.get("short_or_junk"))
    generated_text_counts = Counter(str(sample.get("generated_text") or "") for sample in decisive_eval)
    return {
        "rows": len(decisive_eval),
        "exact_match_rows": exact,
        "exact_match_rate": (exact / len(decisive_eval)) if decisive_eval else None,
        "prefix_match_rows": prefix,
        "prefix_match_rate": (prefix / len(decisive_eval)) if decisive_eval else None,
        "short_or_junk_rows": short,
        "short_or_junk_rate": (short / len(decisive_eval)) if decisive_eval else None,
        "generated_text_counts": dict(sorted(generated_text_counts.items())),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)

    run_10632 = load_json(RUN_10632)
    run_10636 = load_json(RUN_10636)
    label_audit = load_json(LABEL_AUDIT_10633)
    gen_audit_10636 = load_json(GEN_AUDIT_10636)

    metrics_10632 = extract_strict_first_token_metrics(run_10632)
    metrics_10636 = extract_strict_first_token_metrics(run_10636)
    eval_exact_10636 = extract_eval_decisive_exact(gen_audit_10636)

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": False,
        "decision": "permuted_strict_slice_reduces_invalid_win_but_exact_scoring_gap_remains",
        "claim": [
            "Compare the invalid constant-slot stage10632 run against the corrected permuted stage10636 run.",
            "Treat first-token strict accuracy as insufficient for promotion when multi-character labels like E2 and E8 are valid targets.",
        ],
        "inputs": {
            "run_10632": str(RUN_10632.relative_to(ROOT)),
            "run_10636": str(RUN_10636.relative_to(ROOT)),
            "label_audit_10633": str(LABEL_AUDIT_10633.relative_to(ROOT)),
            "generation_audit_10636": str(GEN_AUDIT_10636.relative_to(ROOT)),
        },
        "invalidated_run_10632": {
            "strict_first_token_metrics": metrics_10632,
            "reason": "strict slice had constant target label and constant first-slot gold position",
            "label_position_audit": {
                "probe_strict_constant_target_label": (((label_audit.get("critical_findings") or {}).get("probe_strict_constant_target_label"))),
                "probe_strict_all_gold_in_first_position": (((label_audit.get("critical_findings") or {}).get("probe_strict_all_gold_in_first_position"))),
            },
        },
        "corrected_run_10636": {
            "strict_first_token_metrics": metrics_10636,
            "delta_vs_10632_first_token_accuracy": (
                None
                if metrics_10632["full_vocab_top1_accuracy"] is None or metrics_10636["full_vocab_top1_accuracy"] is None
                else metrics_10636["full_vocab_top1_accuracy"] - metrics_10632["full_vocab_top1_accuracy"]
            ),
            "eval_decisive_generation_exactness": eval_exact_10636,
        },
        "why_not_promotable_yet": [
            "Stage10636 removes the constant-slot shortcut and drops the repaired strict first-token score from 18/18 to 15/18.",
            "The strict metric still reflects first-token correctness, not guaranteed exact label-text correctness for multi-character labels.",
            "The available corrected generation audit shows eval decisive-evidence exact match at 0/6 while prefix match is only 1/6 and every decisive-evidence eval generation is short or junk.",
        ],
        "next_best_step": (
            "Add a strict exact-label generation audit or constrained semantic candidate scorer for the permuted decisive-evidence strict slice, "
            "then compare 100M and Gemma on that exact-scored corrected slice before promoting any long-context win."
        ),
    }

    write_json(AUDIT_JSON, audit)
    write_json(
        SUMMARY_JSON,
        {
            "stage": STAGE,
            "passed": audit["passed"],
            "audit": str(AUDIT_JSON.relative_to(ROOT)),
        },
    )
    print(json.dumps(audit["corrected_run_10636"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
