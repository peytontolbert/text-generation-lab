#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12328_external_adapter_qc_materialization_request"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12327 = ROOT / "runs/summaries/stage12327_external_adapter_preflight.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    preflight = load_json(STAGE12327)
    request = {
        "stage": STAGE,
        "decision": "external_adapter_qc_materialization_request_ready_training_still_blocked",
        "training_allowed": False,
        "admitted_rows": 0,
        "source_preflight": {
            "stage": preflight.get("stage"),
            "open_swe_candidates": (preflight.get("open_swe_import_artifact") or {}).get("sampled_preflight_candidates", 0),
            "open_swe_priority_capped_candidates": (preflight.get("open_swe_import_artifact") or {}).get("priority_capped_candidates", 0),
            "bears_failing_passing_candidates": (preflight.get("bears_inventory") or {}).get("failing_passing_candidates", 0),
            "bears_nonrepair_blocked_candidates": (preflight.get("bears_inventory") or {}).get("nonrepair_blocked_candidates", 0),
        },
        "claim_boundary": (
            "Request/control artifact only. It authorizes QC materialization work, not training. "
            "No Open-SWE or Bears candidate may count toward 500 tasks until a later admission stage passes."
        ),
        "open_swe_qc_materialization_contract": {
            "input": "runs/local/artifacts/stage12327_external_adapter_preflight/open_swe_priority_capped_trace_support_candidates.jsonl",
            "inventory_input": "runs/local/artifacts/stage12327_external_adapter_preflight/open_swe_trace_support_candidates.jsonl",
            "target_first_batch": 50,
            "allowed_counter_if_passed": "trace_support_train_support_rows_only",
            "not_allowed_counters": [
                "external_comparable_fail_to_pass_patch_trace",
                "repair_claim",
                "strict_eval",
                "source_heldout",
            ],
            "required_safe_fields": [
                "root_id",
                "repo_family",
                "language_family",
                "source_record_ref",
                "state_before_summary_codes",
                "ordered_event_refs",
                "candidate_action_set",
                "chosen_action_semantic_type",
                "observation_status_class",
                "verifier_identity_class",
                "state_delta_codes",
                "stop_continue_label",
                "semantic_rule_id",
                "transition_function_key",
            ],
            "hard_rejects": [
                "raw trajectory text emitted to model row",
                "raw verifier output emitted before safe semantic extraction",
                "observed action marked as correct policy without reviewed alternatives",
                "patch/test co-presence treated as causality",
                "resolved flag treated as fail-to-pass proof",
                "same repo family exceeds cap in first batch",
            ],
        },
        "bears_qc_materialization_contract": {
            "input": "runs/local/artifacts/stage12327_external_adapter_preflight/bears_failing_passing_candidates.jsonl",
            "candidate_count": (preflight.get("bears_inventory") or {}).get("failing_passing_candidates", 0),
            "allowed_counter_if_passed": "external_comparable_patch_trace_review_candidates",
            "admission_requires": [
                "local or authoritative checkout/content materialization",
                "buggy_commit_sha and fixer_commit_sha resolved",
                "patch diff applies or authoritative diff lineage is proven",
                "verifier command identity recovered",
                "buggy verifier output class recovered",
                "fixed verifier output class recovered",
                "same-source patch-verifier causality proven",
                "source/test hash refs captured",
                "anti-leak rendering pass",
            ],
            "hard_rejects": [
                "passing_passing used as repair proof",
                "metadata-only build ids used as command output",
                "Travis URL existence treated as local verifier output",
                "failureDetails detail text emitted raw",
                "Bears.py first-failing-class limitation ignored",
                "branch/content absent but row admitted",
            ],
        },
        "stage12329_or_later_admission_gate": {
            "minimum_for_any_training": [
                ">=25 QC-passed rows from Stage12328 materialization",
                "zero raw content leakage",
                "zero admission without same-source event ordering",
                "repo-family cap <= 10 rows or <=20% of batch, whichever is stricter",
                "separate counts for trace-support, verifier-observation, external repair candidate, and Level-3",
            ],
            "minimum_for_repair_claim": [
                "actual before/after verifier classes",
                "patch diff/apply proof",
                "same-source verifier command/output proof",
                "failing/passing or fail-to-pass transition not inferred from labels alone",
            ],
        },
        "subagent_instructions": [
            "Do not generate training rows directly from raw Open-SWE trajectories.",
            "First extract safe semantic transition facts, then run deterministic QC.",
            "For Bears, inspect only failing_passing candidates first; passing_passing remains blocked.",
            "Report every rejected candidate with a blocker reason so we know whether the bottleneck is checkout, verifier output, causality, or anti-leak rendering.",
        ],
    }
    (OUT / "external_adapter_qc_materialization_request.json").write_text(
        json.dumps(request, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "EXTERNAL_ADAPTER_QC_MATERIALIZATION_REQUEST_STAGE12328.md").write_text(
        "# Stage12328 External Adapter QC Materialization Request\n\n"
        "Training remains blocked. This request defines the QC materialization contracts for Open-SWE trace-support and Bears failing/passing candidates.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
