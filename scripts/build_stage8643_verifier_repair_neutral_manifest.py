#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from objective_row_judge import judge_row


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8643_verifier_repair_neutral_manifest"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8643_verifier_repair_neutral_manifest.json"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

LANGUAGES = [("python", "py"), ("typescript", "ts"), ("rust", "rs"), ("cpp", "cpp")]
PATCH_CONTEXTS = [
    ("small_symbol_edit", "A bounded symbol edit was proposed and verifier feedback is available."),
    ("import_patch", "An import/dependency patch was proposed and verifier feedback is available."),
    ("test_update", "A test update was proposed and verifier feedback is available."),
    ("config_change", "A config change was proposed and verifier feedback is available."),
    ("adapter_patch", "An adapter wrapper patch was proposed and verifier feedback is available."),
    ("rollback_candidate", "A patch candidate appears to regress a visible behavior."),
]

REPAIR_ACTIONS = {
    "DIAGNOSE_FAILURE": {
        "signal": "failure_kind_unclear_visible",
        "sequence": ["READ_VERIFIER_LOG", "CLASSIFY_FAILURE"],
    },
    "RERUN_VERIFIER": {
        "signal": "verifier_result_inconclusive_visible",
        "sequence": ["RERUN_VERIFIER"],
    },
    "LOCALIZE_FAILURE": {
        "signal": "failure_points_to_different_location_visible",
        "sequence": ["READ_FAILURE_LOCATION", "LOCALIZE_FAILURE"],
    },
    "REPAIR_SYNTAX": {
        "signal": "syntax_error_visible",
        "sequence": ["READ_SYNTAX_ERROR", "PLAN_SYNTAX_REPAIR"],
    },
    "REPAIR_ASSERTION": {
        "signal": "assertion_mismatch_visible",
        "sequence": ["READ_ASSERTION", "PLAN_ASSERTION_REPAIR"],
    },
    "REPAIR_IMPORT": {
        "signal": "import_error_visible",
        "sequence": ["READ_IMPORT_ERROR", "PLAN_IMPORT_REPAIR"],
    },
    "REPAIR_API_CALL": {
        "signal": "api_call_mismatch_visible",
        "sequence": ["READ_CALLSITE", "PLAN_API_CALL_REPAIR"],
    },
    "ROLLBACK_OR_ABSTAIN": {
        "signal": "regression_or_unsafe_patch_visible",
        "sequence": ["ROLLBACK_OR_ABSTAIN"],
    },
    "RETRIEVE_MORE": {
        "signal": "verifier_evidence_missing",
        "sequence": ["SEARCH_REPO", "READ_MORE_CONTEXT"],
    },
}


def loss_mask() -> dict[str, bool]:
    keys = [
        "surface_role_ce",
        "repair_surface_ce",
        "build_mode_ce",
        "allowed_import_policy_ce",
        "blocked_import_policy_ce",
        "repo_dependency_policy_ce",
        "action_sequence_ce",
        "file_plan_ce",
        "symbol_binding_ce",
        "edit_localization_ce",
        "patch_operator_ce",
        "verifier_repair_ce",
        "decoder_ce",
        "denoise_ce",
        "runtime_reward",
    ]
    enabled = {"verifier_repair_ce", "action_sequence_ce", "file_plan_ce"}
    return {key: key in enabled for key in keys}


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for split in ["train", "eval", "strict"]:
        for lang_idx, (language, ext) in enumerate(LANGUAGES):
            for ctx_idx, (ctx_key, ctx_text) in enumerate(PATCH_CONTEXTS):
                neutral = lang_idx + ctx_idx
                for action, spec in REPAIR_ACTIONS.items():
                    row_id = f"stage8643_{split}_{language}_{ctx_key}_{action.lower()}"
                    corrupted_state = {
                        "task_family": "verifier_repair",
                        "language": language,
                        "file_extension": ext,
                        "patch_context": ctx_text,
                        "verifier_signal": spec["signal"],
                        "verifier_packet": {
                            "log_available": neutral % 2 == 0,
                            "test_name_visible": neutral % 3 == 0,
                            "source_location_visible": neutral % 4 == 0,
                            "patch_summary_visible": True,
                            "runtime_execution_authorized": False,
                        },
                        "budget": {
                            "max_repair_steps": 2,
                            "decoder_budget_ok": False,
                            "runtime_reward_allowed": False,
                        },
                    }
                    clean_state = {
                        "verifier_repair_action": action,
                        "action_sequence": spec["sequence"],
                        "file_plan": f"handle {action.lower()} from verifier evidence without executing runtime",
                    }
                    row = {
                        "row_id": row_id,
                        "split": split,
                        "objective_family": "verifier_repair",
                        "route": "KEEP_STRUCTURED",
                        "authority": AUTHORITY_CLOSED,
                        "corrupted_state": corrupted_state,
                        "clean_state": clean_state,
                        "loss_mask": loss_mask(),
                        "source_stage": "stage8629_recovery_completion_queue",
                        "semantic_key": f"{split}:{language}:{ctx_key}:{action}",
                    }
                    judged = judge_row(
                        {
                            "row_id": row_id,
                            "objective_family": "verifier_repair",
                            "corrupted_state": corrupted_state,
                            "clean_state": clean_state,
                            "decode_allowed": False,
                            "decoder_budget_ok": False,
                        }
                    )
                    row["judge_route_card"] = {
                        "route": "KEEP_STRUCTURED",
                        "judge_reasons": judged["judge_reasons"],
                        "features": judged["features"],
                    }
                    rows.append(row)
    return rows


def audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = set(REPAIR_ACTIONS)
    leak_rows: list[str] = []
    split_action = Counter()
    signal_counts = Counter()
    loss_counts = Counter()
    authority_rows = 0
    for row in rows:
        visible = json.dumps(row["corrupted_state"], sort_keys=True)
        for label in labels:
            if label in visible:
                leak_rows.append(row["row_id"])
                break
        authority_rows += int(any(row["authority"].values()))
        action = row["clean_state"]["verifier_repair_action"]
        split_action[(row["split"], action)] += 1
        signal_counts[row["corrupted_state"]["verifier_signal"]] += 1
        for key, value in row["loss_mask"].items():
            loss_counts[key] += int(value)
    per_split_action_ok = all(count == len(LANGUAGES) * len(PATCH_CONTEXTS) for count in split_action.values())
    return {
        "rows": len(rows),
        "leak_row_count": len(leak_rows),
        "leak_rows": leak_rows[:20],
        "authority_row_count": authority_rows,
        "split_action_counts": {f"{k[0]}:{k[1]}": v for k, v in sorted(split_action.items())},
        "verifier_signal_counts": dict(sorted(signal_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "per_split_action_balanced": per_split_action_ok,
        "passed": len(leak_rows) == 0 and authority_rows == 0 and per_split_action_ok,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    manifest = OUT_DIR / "verifier_repair_neutral_manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    audit_card = audit(rows)
    (OUT_DIR / "audit_card.json").write_text(json.dumps(audit_card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": 8643,
        "stage_name": "stage8643_verifier_repair_neutral_manifest",
        "passed": audit_card["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": audit_card,
        "artifacts": {
            "manifest": str(manifest.relative_to(ROOT)),
            "audit_card": str((OUT_DIR / "audit_card.json").relative_to(ROOT)),
            "builder": "scripts/build_stage8643_verifier_repair_neutral_manifest.py",
        },
        "decision": "Verifier-repair neutral builder restored as no-authority structured rows only. Runtime, reward, decode, and training remain closed.",
        "next_best_step": "Run shortcut baselines over verifier-repair corrupted_state before training candidate consideration.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
