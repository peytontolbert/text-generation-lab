#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10608
NAME = "stage10608_v27_semantic_output_metric_contract"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "v27_semantic_output_metric_contract.json"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

PREFIX_AUDIT = ROOT / "runs/local/artifacts/stage10606_semantic_output_probe_prefix_inflation_audit/semantic_output_probe_prefix_inflation_audit.json"
INTERFACE_AUDIT = ROOT / "runs/local/artifacts/stage10603_fresh_python_cpp_mixed_contract_semantic_output_audit/fresh_python_cpp_mixed_contract_semantic_output_audit.json"
SEMANTIC_REQUEST = ROOT / "runs/local/artifacts/stage10604_fresh_python_cpp_mixed_contract_semantic_output_probe_request/fresh_python_cpp_mixed_contract_semantic_output_probe_request.json"
OLD_BASELINE = ROOT / "runs/local/artifacts/stage10594_fresh_python_cpp_mixed_contract_probe/bounded_decoder_probe/execution_result.json"
DIAG_BASELINE = ROOT / "runs/local/artifacts/stage10599_mixed_contract_non_a_diagnostic_probe/bounded_decoder_probe/execution_result.json"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    prefix = load_json(PREFIX_AUDIT)
    interface = load_json(INTERFACE_AUDIT)
    request = load_json(SEMANTIC_REQUEST)
    old = load_json(OLD_BASELINE)
    diag = load_json(DIAG_BASELINE)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "inputs": {
            "prefix_inflation_audit": display(PREFIX_AUDIT),
            "interface_audit": display(INTERFACE_AUDIT),
            "semantic_probe_request": display(SEMANTIC_REQUEST),
            "old_baseline": display(OLD_BASELINE),
            "diagnostic_baseline": display(DIAG_BASELINE),
        },
        "claim_scope": [
            "Freezes the valid promotion metrics for semantic-output successors of v2.7 after the stage10605 first-token inflation finding.",
            "Separates unsafe first-token full-vocab metrics from promotable semantic-output metrics.",
            "This is the metric contract that future 100M-vs-Gemma comparisons on semantic-output rows must satisfy.",
        ],
        "current_evidence": {
            "stage10605_full_vocab_top1_accuracy": ((prefix.get("current_state") or {}).get("stage10605_full_vocab_top1_accuracy")),
            "stage10605_constrained_choice_top1_accuracy": ((prefix.get("current_state") or {}).get("stage10605_constrained_choice_top1_accuracy")),
            "stage10605_dominant_full_vocab_prediction": ((prefix.get("dominant_predictions") or {}).get("full_vocab") or [None])[0],
            "semantic_decoder_equals_label_rows": ((interface.get("strict_eval") or {}).get("decoder_equals_label_rows")),
            "strict_mean_decoder_token_length": ((interface.get("strict_eval") or {}).get("mean_decoder_token_length")),
            "stage10594_full_vocab_top1_accuracy": (((old.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("full_vocab_top1_accuracy")),
            "stage10599_full_vocab_top1_accuracy": (((diag.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("full_vocab_top1_accuracy")),
        },
        "unsafe_metrics": [
            {
                "metric": "first_token_full_vocab_top1_accuracy",
                "status": "blocked_for_promotion",
                "reason": "Multi-token semantic outputs can get artificial credit from shared first-token overlap, as demonstrated by stage10605 predicting constant A across all strict rows.",
            },
            {
                "metric": "rows_with_target_rank_1_on_first_token",
                "status": "blocked_for_promotion",
                "reason": "This is also first-token based and inherits the same inflation mode.",
            },
        ],
        "promotable_metrics": [
            {
                "metric": "exact_semantic_output_match_rate",
                "status": "required",
                "definition": "Generated semantic output string must exactly match the full target decoder_text after stripping whitespace.",
            },
            {
                "metric": "constrained_semantic_choice_accuracy",
                "status": "required",
                "definition": "Choice scoring must use bounded_choice_target_label or an equivalent semantic-choice target, not decoder_text first-token overlap.",
            },
            {
                "metric": "contentful_generation_rate",
                "status": "required_context",
                "definition": "Report alongside exact match so empty or junk generations cannot masquerade as progress.",
            },
        ],
        "required_honesty_gates": [
            "No semantic-output stage may be promoted or compared to Gemma using first-token full-vocab accuracy alone.",
            "Any semantic-output Gemma comparison must use the exact same semantic-output target strings and the same exact-match scorer.",
            "Bounded-choice constrained scoring must remain decoupled from decoder_text via bounded_choice_target_label or an equivalent explicit field.",
            "If exact semantic-output scoring is unavailable, the stage is diagnostic-only.",
        ],
        "next_actions": [
            "Finish stage10607 or an equivalent exact-sequence audit and use it as the headline metric for stage10605-like semantic-output probes.",
            "If exact semantic-output generation stays poor while constrained choice is useful, switch the main comparison surface to semantic constrained scoring rather than decoder free generation.",
            "Only after the metric contract is enforced should the next multilingual v2.7 Gemma comparison be run on this path.",
        ],
        "truthful_read": [
            "The semantic-output interface repair is still valid and worth keeping.",
            "The stage10605 apparent gain is not promotable because the metric was still gameable at the first-token level.",
            "This contract prevents that eval-hacking mode from reappearing in future v2.7 promotion candidates.",
        ],
        "outputs": {
            "metric_contract_json": display(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, payload)
    write_json(RUN_SUMMARY_JSON, payload)
    print(json.dumps({
        "stage": STAGE,
        "blocked_metric": payload["unsafe_metrics"][0]["metric"],
        "required_metric": payload["promotable_metrics"][0]["metric"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
