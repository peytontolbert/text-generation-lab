#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10601
NAME = "stage10601_mixed_contract_non_a_diagnostic_result_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "mixed_contract_non_a_diagnostic_result_audit.json"

BASELINE_RESULT = ROOT / "runs/local/artifacts/stage10594_fresh_python_cpp_mixed_contract_probe/bounded_decoder_probe/execution_result.json"
DIAGNOSTIC_RESULT = ROOT / "runs/local/artifacts/stage10599_mixed_contract_non_a_diagnostic_probe/bounded_decoder_probe/execution_result.json"
CANARY_AUDIT = ROOT / "runs/local/artifacts/stage10600_mixed_contract_non_a_diagnostic_canary_audit/mixed_contract_non_a_diagnostic_canary_audit.json"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10591_fresh_python_cpp_visible_candidate_mixed_contract_package/strict_eval_rows.jsonl"
DIAGNOSTIC_PACKAGE = ROOT / "runs/local/artifacts/stage10597_mixed_contract_non_a_diagnostic_support_package/mixed_contract_non_a_diagnostic_support_package.json"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def metric(rows: list[dict[str, Any]], field: str) -> float | None:
    vals = [row for row in rows if isinstance(row.get(field), bool)]
    if not vals:
        return None
    return sum(1 for row in vals if row.get(field) is True) / len(vals)


def structure(rows: list[dict[str, Any]], subtype: str, pred_field: str) -> dict[str, Any]:
    subset = [row for row in rows if str(row.get("target_subtype") or "") == subtype]
    target_counts = Counter(str(row.get("target_text") or "") for row in subset)
    pred_counts = Counter(str(row.get(pred_field) or "") for row in subset)
    return {
        "rows": len(subset),
        "target_text_counts": dict(sorted(target_counts.items())),
        "predicted_text_counts": dict(sorted(pred_counts.items())),
        "dominant_target_text": target_counts.most_common(1)[0][0] if target_counts else None,
        "dominant_target_text_fraction": (target_counts.most_common(1)[0][1] / len(subset)) if subset else None,
        "dominant_predicted_text": pred_counts.most_common(1)[0][0] if pred_counts else None,
        "dominant_predicted_text_fraction": (pred_counts.most_common(1)[0][1] / len(subset)) if subset else None,
    }


def merge_rows(execution: dict[str, Any], strict_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    strict_cards = (((execution.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("row_cards") or [])
    row_index = {str(row.get("row_id") or ""): row for row in strict_rows}
    return [{**row_index.get(str(card.get("row_id") or ""), {}), **card} for card in strict_cards]


def subtype_lang(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    buckets: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        buckets[str(row.get("target_subtype") or "unknown")][str(row.get("language_family") or "unknown")].append(row)
    out: dict[str, Any] = {}
    for subtype, langs in sorted(buckets.items()):
        out[subtype] = {}
        for lang, bucket in sorted(langs.items()):
            out[subtype][lang] = {
                "rows": len(bucket),
                "full_vocab_top1_accuracy": metric(bucket, field),
            }
    return out


def main() -> None:
    baseline = load_json(BASELINE_RESULT)
    diagnostic = load_json(DIAGNOSTIC_RESULT)
    canary = load_json(CANARY_AUDIT)
    strict_rows = load_jsonl(STRICT_ROWS)
    package = load_json(DIAGNOSTIC_PACKAGE)

    baseline_merged = merge_rows(baseline, strict_rows)
    diagnostic_merged = merge_rows(diagnostic, strict_rows)

    baseline_strict = ((baseline.get("bounded_choice_eval") or {}).get("strict_eval") or {})
    diagnostic_strict = ((diagnostic.get("bounded_choice_eval") or {}).get("strict_eval") or {})

    fresh_strict_target_dist = Counter(str(row.get("target_subtype") or "") for row in strict_rows)
    fresh_language_dist = Counter(str(row.get("language_family") or "") for row in strict_rows)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "inputs": {
            "baseline_execution_result": display(BASELINE_RESULT),
            "diagnostic_execution_result": display(DIAGNOSTIC_RESULT),
            "canary_audit": display(CANARY_AUDIT),
            "strict_rows": display(STRICT_ROWS),
            "diagnostic_package": display(DIAGNOSTIC_PACKAGE),
        },
        "claim_scope": [
            "Compares the stage10599 diagnostic run directly against the stage10594 mixed-contract baseline on the same 189-row fresh strict package.",
            "Keeps the repaired 24-row canary as a regression gate and reports whether same-surface non-A support improved the harder mixed-contract interface.",
            "This is diagnostic-only because the added support reuses same-surface strict roots.",
        ],
        "current_state": {
            "baseline_fresh_overall_exact": baseline_strict.get("full_vocab_top1_accuracy"),
            "diagnostic_fresh_overall_exact": diagnostic_strict.get("full_vocab_top1_accuracy"),
            "fresh_overall_delta_diagnostic_minus_baseline": (
                (diagnostic_strict.get("full_vocab_top1_accuracy") or 0.0)
                - (baseline_strict.get("full_vocab_top1_accuracy") or 0.0)
            ),
            "baseline_rows_with_target_rank_1": baseline_strict.get("rows_with_target_rank_1"),
            "diagnostic_rows_with_target_rank_1": diagnostic_strict.get("rows_with_target_rank_1"),
            "repaired_canary_bounded_accuracy": ((canary.get("summary") or {}).get("bounded_accuracy")),
        },
        "fresh_split_shape": {
            "strict_rows": len(strict_rows),
            "strict_language_counts": dict(sorted(fresh_language_dist.items())),
            "strict_target_subtype_counts": dict(sorted(fresh_strict_target_dist.items())),
            "diagnostic_added_rows": ((package.get("rows") or {}).get("diagnostic_added_rows")),
            "diagnostic_train_rows": ((package.get("rows") or {}).get("train_rows")),
        },
        "baseline_structure_audit": {
            "retrieve_answer_abstain": structure(baseline_merged, "retrieve_answer_abstain", "full_vocab_top1_text"),
            "verifier_outcome_masked": structure(baseline_merged, "verifier_outcome_masked", "full_vocab_top1_text"),
            "decisive_evidence_top1": structure(baseline_merged, "decisive_evidence_top1", "full_vocab_top1_text"),
        },
        "diagnostic_structure_audit": {
            "retrieve_answer_abstain": structure(diagnostic_merged, "retrieve_answer_abstain", "full_vocab_top1_text"),
            "verifier_outcome_masked": structure(diagnostic_merged, "verifier_outcome_masked", "full_vocab_top1_text"),
            "decisive_evidence_top1": structure(diagnostic_merged, "decisive_evidence_top1", "full_vocab_top1_text"),
        },
        "baseline_per_subtype_language": subtype_lang(baseline_merged, "full_vocab_top1_match"),
        "diagnostic_per_subtype_language": subtype_lang(diagnostic_merged, "full_vocab_top1_match"),
        "truthful_read": [
            "This run is non-promotable by construction because it trains on same-surface strict roots with non-A retrieve/verifier targets.",
            "Its value is narrow: it tells us whether simple non-A support scarcity caused the stage10594 collapse on the harder mixed-contract package.",
            "If the diagnostic accuracy does not exceed stage10594 meaningfully, the problem is more likely representation or optimization than missing B/D examples.",
        ],
        "next_actions": [
            "If stage10599 does not improve on stage10594, stop adding same-surface support and move to interface or objective redesign.",
            "Keep the repaired 24-row canary fixed as a regression gate rather than a training target.",
            "Do not use stage10599 in any headline or Gemma comparison because it is diagnostic-only.",
        ],
        "outputs": {
            "audit_json": display(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
