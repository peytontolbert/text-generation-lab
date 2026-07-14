#!/usr/bin/env python3
"""Define the Transition-Root-250 supply contract after transition head probes plateaued."""

from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11967
NAME = "stage11967_transition_root_250_supply_contract"
OUT = ART / NAME
SUMMARY = OUT / "transition_root_250_supply_contract.json"
CURRENT_ROWS = ART / "stage11958_transition_5k_v1_augmented_package/transition_projection_rows_5k_v1_augmented.jsonl"
CURRENT_RECORDS = ART / "stage11958_transition_5k_v1_augmented_package/verified_transition_records_5k_v1_augmented.jsonl"
BASE_RECORDS = ART / "stage11955_transition_5k_v1_multisource_package/verified_transition_records_5k_v1.jsonl"
COUNTERFACTUAL_RECORDS = ART / "stage11957_transition_counterfactual_status_augmentation/counterfactual_transition_records.jsonl"
DECISION_11966 = ART / "stage11966_transition_status_control_decision/transition_status_control_decision.json"

MIN_LANGUAGE_ROOTS = {"python": 50, "rust": 50, "c_cpp": 50}
WEB_MAX_FRACTION = 0.40
MIN_INDEPENDENT_ROOTS = 250
MIN_STATUS_RECORDS = {
    "FAIL_TO_PASS": 50,
    "PASS_TO_PASS": 100,
    "PASS_CURRENT_BUILD": 40,
    "PASS_CURRENT_BUILD_AND_RUN": 40,
    "INSUFFICIENT_EVIDENCE": 40,
    "NOT_EXERCISED": 40,
}
VERIFIER_REMOVED_MAX_FRACTION = 0.20


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def root_id(record: dict[str, Any]) -> str:
    task_intent = record.get("task_intent") if isinstance(record.get("task_intent"), dict) else {}
    return str(
        record.get("root_id")
        or record.get("root_lineage_key")
        or task_intent.get("root_id")
        or record.get("source_lineage_ref")
        or "unknown"
    )


def language(record: dict[str, Any]) -> str:
    task_intent = record.get("task_intent") if isinstance(record.get("task_intent"), dict) else {}
    return str(record.get("language_family") or task_intent.get("language_family") or record.get("language") or "unknown")


def verifier_status(record: dict[str, Any]) -> str:
    targets = record.get("training_projection_targets") if isinstance(record.get("training_projection_targets"), dict) else {}
    value = (
        record.get("verifier_transition")
        or record.get("observed_verifier_transition")
        or record.get("verifier_status")
        or targets.get("verifier_transition")
    )
    if isinstance(value, dict):
        value = value.get("transition") or value.get("status")
    if not value:
        verifier = record.get("verifier_result") if isinstance(record.get("verifier_result"), dict) else {}
        value = verifier.get("transition") or verifier.get("verifier_status") or verifier.get("status")
    return str(value or "unknown").upper()


def source_kind(record: dict[str, Any]) -> str:
    rid = str(record.get("record_id") or record.get("transition_record_id") or record.get("row_id") or "")
    if "counterfactual" in rid:
        return "counterfactual"
    if record.get("counterfactual") or record.get("counterfactual_transition"):
        return "counterfactual"
    return "base"


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    roots_by_language: dict[str, set[str]] = defaultdict(set)
    records_by_language = Counter()
    records_by_status = Counter()
    records_by_source = Counter()
    roots = set()
    for record in records:
        rid = root_id(record)
        lang = language(record)
        roots.add(rid)
        roots_by_language[lang].add(rid)
        records_by_language[lang] += 1
        records_by_status[verifier_status(record)] += 1
        records_by_source[source_kind(record)] += 1
    return {
        "records": len(records),
        "independent_roots": len(roots),
        "root_counts_by_language": {lang: len(values) for lang, values in sorted(roots_by_language.items())},
        "record_counts_by_language": dict(records_by_language),
        "record_counts_by_status": dict(records_by_status),
        "record_counts_by_source_kind": dict(records_by_source),
    }


def deficits(summary: dict[str, Any]) -> dict[str, Any]:
    root_counts = summary.get("root_counts_by_language") or {}
    status_counts = summary.get("record_counts_by_status") or {}
    records = int(summary.get("records") or 0)
    independent_roots = int(summary.get("independent_roots") or 0)
    out: dict[str, Any] = {
        "independent_roots_needed": max(0, MIN_INDEPENDENT_ROOTS - independent_roots),
        "language_root_deficits": {lang: max(0, minimum - int(root_counts.get(lang, 0))) for lang, minimum in MIN_LANGUAGE_ROOTS.items()},
        "status_record_deficits": {status: max(0, minimum - int(status_counts.get(status, 0))) for status, minimum in MIN_STATUS_RECORDS.items()},
    }
    web_roots = int(root_counts.get("web_js_ts_html", 0) or 0)
    max_web_roots = int(independent_roots * WEB_MAX_FRACTION)
    out["web_root_over_cap"] = max(0, web_roots - max_web_roots) if independent_roots else web_roots
    verifier_removed = int(status_counts.get("VERIFIER_REMOVED", 0) or 0)
    max_removed = int(records * VERIFIER_REMOVED_MAX_FRACTION)
    out["verifier_removed_record_over_cap"] = max(0, verifier_removed - max_removed) if records else verifier_removed
    return out


def main() -> None:
    current_records = read_jsonl(CURRENT_RECORDS)
    base_records = read_jsonl(BASE_RECORDS)
    counter_records = read_jsonl(COUNTERFACTUAL_RECORDS)
    current_summary = summarize_records(current_records)
    base_summary = summarize_records(base_records)
    counter_summary = summarize_records(counter_records)
    current_deficits = deficits(current_summary)
    base_deficits = deficits(base_summary)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "transition_root_250_supply_contract_ready",
        "why_now": [
            "Stage11960 and Stage11964 improved train fit but collapsed transfer, so more augmented rows from the same roots are not the next lever.",
            "Stage11966 keeps Stage11924 as the selected transition frontier at 364/640, below Gemma 386/640.",
            "The next valid frontier attempt needs independent executable roots and balanced verifier statuses before training.",
        ],
        "contract": {
            "minimum_independent_roots": MIN_INDEPENDENT_ROOTS,
            "minimum_language_roots": MIN_LANGUAGE_ROOTS,
            "web_max_fraction_of_roots": WEB_MAX_FRACTION,
            "minimum_status_records": MIN_STATUS_RECORDS,
            "verifier_removed_max_fraction_of_records": VERIFIER_REMOVED_MAX_FRACTION,
            "counterfactual_rows_count_for_training_only": True,
            "counterfactual_rows_count_for_root_scale": False,
            "required_transition_shape": [
                "baseline observed",
                "relevant artifact found",
                "verifier/test selected",
                "evidence sufficiency judged",
                "patch or no-patch decision",
                "verifier transition predicted",
                "continue/stop decision",
            ],
            "required_record_fields": [
                "root_id",
                "root_lineage_key",
                "repo_id",
                "language_family",
                "source_snapshot_or_commit",
                "state_before",
                "candidate_actions_or_options",
                "selected_verifier_path",
                "observed_verifier_transition",
                "tool_or_verifier_observation",
                "state_after_or_state_delta",
                "continue_stop_label",
                "anti_cheat",
                "split_component",
            ],
            "anti_cheat_requirements": [
                "no prompt-target leak before options",
                "deterministic opaque option shuffle declared",
                "root/repo/time split isolation",
                "no singleton options in eval",
                "visible source or verifier evidence for every gold option",
                "counterfactual rows marked train_support_only",
            ],
            "training_runtime_requirements": [
                "evaluate every 100-200 steps on old 640, v2 validation/strict, source-heldout smoke, and status/control eval",
                "early stop if old 640 drops below 350",
                "early stop if train improves while validation drops for two checkpoints",
                "report confusion by semantic status and task type",
            ],
            "promotion_gate": {
                "old_transition_640": ">=386/640 for Gemma win, >=364/640 for retention",
                "source_heldout_smoke": ">6/12 for real transfer progress",
                "protected_filtered_strict": "22/22",
                "protected_old_canary_strict": "23/23",
                "protected_residual_bank": ">=7/10",
                "status_control_validation": "must improve Stage11924 baseline without strict collapse",
            },
        },
        "current_supply_audit": {
            "base_records_only": base_summary,
            "base_record_deficits": base_deficits,
            "augmented_current_records": current_summary,
            "augmented_current_deficits": current_deficits,
            "counterfactual_records_only": counter_summary,
            "interpretation": [
                "Stage11958 reaches row scale only by counterfactual augmentation, not independent executable roots.",
                "Independent root count remains far below the 250-root contract.",
                "Verifier-removed rows are overrepresented in augmented records and must be capped in the next package.",
            ],
        },
        "next_stage_recommendation": {
            "stage": "stage11968_transition_root_250_candidate_miner",
            "goal": "Mine/admit executable transition roots until the Stage11967 contract passes before any new transition training.",
            "priority_order": [
                "real FAIL_TO_PASS roots",
                "PASS_CURRENT_BUILD and PASS_CURRENT_BUILD_AND_RUN roots",
                "NOT_EXERCISED and INSUFFICIENT_EVIDENCE roots with real verifier/test context",
                "Rust/Python/C++ language deficits",
                "web roots only under the 40% cap",
            ],
        },
        "milestone_decomposition_lane": {
            "status": "deferred_separate_lane",
            "projection_family": "milestone_decomposition_policy",
            "reason": "Useful for long-horizon maintainer policy, but should not be mixed into transition-status recovery until Stage11924 transition baseline is surpassed or a clean root-scale package exists.",
        },
        "source_artifacts": {
            "stage11966_decision": rel(DECISION_11966),
            "current_rows": rel(CURRENT_ROWS),
            "current_records": rel(CURRENT_RECORDS),
            "base_records": rel(BASE_RECORDS),
            "counterfactual_records": rel(COUNTERFACTUAL_RECORDS),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "current_supply_audit": artifact["current_supply_audit"], "next_stage": artifact["next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
