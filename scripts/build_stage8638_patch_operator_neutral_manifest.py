#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from objective_row_judge import judge_row


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8638_patch_operator_neutral_manifest"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8638_patch_operator_neutral_manifest.json"

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
EDIT_NEEDS = [
    ("boundary_check", "Visible evidence says a small boundary behavior must change."),
    ("new_helper", "Visible evidence says a missing local helper should be introduced."),
    ("bad_expression", "Visible evidence points to a wrong expression-level transformation."),
    ("unsafe_call", "Visible evidence says an existing call needs a wrapper or guard."),
    ("missing_import", "Visible evidence says an approved dependency reference is absent."),
    ("test_gap", "Visible evidence says a regression test needs to be added."),
]

OPERATORS = {
    "MODIFY_EXISTING_SYMBOL": "modify_existing_symbol_visible",
    "INSERT_FUNCTION": "insert_local_function_visible",
    "REPLACE_EXPR": "replace_expression_visible",
    "WRAP_CALL": "wrap_call_visible",
    "ADD_IMPORT": "approved_import_missing_visible",
    "ADD_TEST_CASE": "test_case_gap_visible",
    "UPDATE_CONFIG_FIELD": "config_field_update_visible",
    "CREATE_FILE": "new_file_needed_visible",
    "BUILD_ADAPTER": "adapter_layer_needed_visible",
    "ROLLBACK_PATCH": "rollback_required_visible",
    "RETRIEVE_MORE": "operator_evidence_missing",
    "ABSTAIN_UNSAFE": "operator_unsafe_or_blocked",
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
    enabled = {"patch_operator_ce", "action_sequence_ce", "file_plan_ce"}
    return {key: key in enabled for key in keys}


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for split in ["train", "eval", "strict"]:
        for lang_idx, (language, ext) in enumerate(LANGUAGES):
            for need_idx, (need_key, need_text) in enumerate(EDIT_NEEDS):
                neutral = lang_idx + need_idx
                for operator, signal in OPERATORS.items():
                    row_id = f"stage8638_{split}_{language}_{need_key}_{operator.lower()}"
                    corrupted_state = {
                        "task_family": "patch_operator",
                        "language": language,
                        "file_extension": ext,
                        "localized_edit_need": need_text,
                        "operator_signal": signal,
                        "target_scope_features": {
                            "target_kind_hint": ["symbol", "file", "config", "test"][neutral % 4],
                            "has_visible_test": neutral % 2 == 0,
                            "has_visible_import_policy": neutral % 3 == 0,
                            "has_visible_config": neutral % 4 == 0,
                            "bounded_patch_required": True,
                        },
                        "budget": {
                            "max_hunks": 2,
                            "max_files": 2,
                            "decoder_budget_ok": False,
                        },
                    }
                    action_sequence = {
                        "MODIFY_EXISTING_SYMBOL": ["READ_SYMBOL", "PLAN_SYMBOL_EDIT"],
                        "INSERT_FUNCTION": ["READ_FILE", "PLAN_INSERT_FUNCTION"],
                        "REPLACE_EXPR": ["READ_SYMBOL", "PLAN_EXPR_REPLACE"],
                        "WRAP_CALL": ["READ_CALLSITE", "PLAN_CALL_WRAP"],
                        "ADD_IMPORT": ["CHECK_IMPORT_POLICY", "PLAN_IMPORT_ADD"],
                        "ADD_TEST_CASE": ["READ_TESTS", "PLAN_TEST_ADD"],
                        "UPDATE_CONFIG_FIELD": ["READ_CONFIG", "PLAN_CONFIG_UPDATE"],
                        "CREATE_FILE": ["PLAN_NEW_FILE", "PLAN_TEST"],
                        "BUILD_ADAPTER": ["READ_ALLOWED_SOURCE", "PLAN_ADAPTER"],
                        "ROLLBACK_PATCH": ["INSPECT_PATCH", "PLAN_ROLLBACK"],
                        "RETRIEVE_MORE": ["SEARCH_REPO", "READ_MORE_CONTEXT"],
                        "ABSTAIN_UNSAFE": ["ABSTAIN_UNSAFE"],
                    }[operator]
                    clean_state = {
                        "patch_operator": operator,
                        "action_sequence": action_sequence,
                        "file_plan": f"apply {operator.lower()} only after verifier-visible target stays bounded",
                    }
                    row = {
                        "row_id": row_id,
                        "split": split,
                        "objective_family": "patch_operator",
                        "route": "KEEP_STRUCTURED",
                        "authority": AUTHORITY_CLOSED,
                        "corrupted_state": corrupted_state,
                        "clean_state": clean_state,
                        "loss_mask": loss_mask(),
                        "source_stage": "stage8629_recovery_completion_queue",
                        "semantic_key": f"{split}:{language}:{need_key}:{operator}",
                    }
                    judged = judge_row(
                        {
                            "row_id": row_id,
                            "objective_family": "patch_operator",
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
    labels = set(OPERATORS)
    leak_rows: list[str] = []
    split_operator = Counter()
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
        op = row["clean_state"]["patch_operator"]
        split_operator[(row["split"], op)] += 1
        signal_counts[row["corrupted_state"]["operator_signal"]] += 1
        for key, value in row["loss_mask"].items():
            loss_counts[key] += int(value)
    per_split_operator_ok = all(count == len(LANGUAGES) * len(EDIT_NEEDS) for count in split_operator.values())
    return {
        "rows": len(rows),
        "leak_row_count": len(leak_rows),
        "leak_rows": leak_rows[:20],
        "authority_row_count": authority_rows,
        "split_operator_counts": {f"{k[0]}:{k[1]}": v for k, v in sorted(split_operator.items())},
        "operator_signal_counts": dict(sorted(signal_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "per_split_operator_balanced": per_split_operator_ok,
        "passed": len(leak_rows) == 0 and authority_rows == 0 and per_split_operator_ok,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    manifest = OUT_DIR / "patch_operator_neutral_manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    audit_card = audit(rows)
    (OUT_DIR / "audit_card.json").write_text(json.dumps(audit_card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": 8638,
        "stage_name": "stage8638_patch_operator_neutral_manifest",
        "passed": audit_card["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": audit_card,
        "artifacts": {
            "manifest": str(manifest.relative_to(ROOT)),
            "audit_card": str((OUT_DIR / "audit_card.json").relative_to(ROOT)),
            "builder": "scripts/build_stage8638_patch_operator_neutral_manifest.py",
        },
        "decision": "Patch-operator neutral builder restored as no-authority structured rows only. Training/runtime/decode remain closed.",
        "next_best_step": "Run shortcut baselines over patch-operator corrupted_state before training candidate consideration.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
