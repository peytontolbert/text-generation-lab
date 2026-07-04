#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from objective_row_judge import judge_row


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8636_edit_localization_neutral_manifest"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8636_edit_localization_neutral_manifest.json"

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
TASKS = [
    ("login_check", "A behavior check fails after validating user credentials."),
    ("config_timeout", "A runtime path uses the wrong timeout behavior."),
    ("report_format", "An assertion expects a stable report field."),
    ("startup_path", "The application starts through the wrong entry behavior."),
    ("helper_call", "A helper call returns a mismatched value."),
    ("fixture_shape", "A test fixture shape is inconsistent with expected behavior."),
]

TARGETS = {
    "TARGET_FILE": {
        "evidence": "The visible failure is localized to a file-level responsibility but no specific symbol is available.",
        "locality_signal": "file_responsibility_visible",
        "action_sequence": ["READ_FILE", "LOCALIZE_FILE", "PLAN_PATCH"],
    },
    "TARGET_SYMBOL": {
        "evidence": "A visible call or definition points to the symbol that owns the behavior.",
        "locality_signal": "symbol_owner_visible",
        "action_sequence": ["BIND_SYMBOL", "READ_SYMBOL", "PLAN_PATCH"],
    },
    "TARGET_CONFIG": {
        "evidence": "Visible configuration evidence controls the failing behavior.",
        "locality_signal": "configuration_control_visible",
        "action_sequence": ["READ_CONFIG", "LOCALIZE_CONFIG_FIELD", "PLAN_PATCH"],
    },
    "TARGET_TEST": {
        "evidence": "The source behavior is valid, but the visible test expectation is stale or malformed.",
        "locality_signal": "test_expectation_visible",
        "action_sequence": ["READ_TEST", "LOCALIZE_ASSERTION", "PLAN_TEST_PATCH"],
    },
    "TARGET_ENTRYPOINT": {
        "evidence": "The visible failure occurs through startup or command entry behavior.",
        "locality_signal": "entry_behavior_visible",
        "action_sequence": ["READ_ENTRYPOINT", "LOCALIZE_ENTRY_FLOW", "PLAN_PATCH"],
    },
    "RETRIEVE_MORE": {
        "evidence": "The visible evidence is insufficient to choose a safe edit target.",
        "locality_signal": "target_evidence_missing",
        "action_sequence": ["SEARCH_REPO", "READ_MORE_CONTEXT"],
    },
    "ABSTAIN_UNBOUND": {
        "evidence": "The visible evidence conflicts or points outside the allowed repository boundary.",
        "locality_signal": "target_conflict_or_unbound",
        "action_sequence": ["ABSTAIN_UNBOUND"],
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
    enabled = {"edit_localization_ce", "action_sequence_ce", "file_plan_ce"}
    return {key: key in enabled for key in keys}


def row_id(*parts: Any) -> str:
    return "stage8636_" + "_".join(str(p).lower() for p in parts)


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for split in ["train", "eval", "strict"]:
        for lang_idx, (language, ext) in enumerate(LANGUAGES):
            for task_idx, (task_key, task_text) in enumerate(TASKS):
                neutral_bit = lang_idx + task_idx
                for target, spec in TARGETS.items():
                    rid = row_id(split, language, task_key, target)
                    corrupted_state = {
                        "task_family": "edit_localization",
                        "language": language,
                        "file_extension": ext,
                        "task_observation": task_text,
                        "visible_locality_evidence": spec["evidence"],
                        "locality_signal": spec["locality_signal"],
                        "graph_packet": {
                            "opaque_graph_id": f"g{neutral_bit % 5}",
                            "query_node_type": ["failure_log", "callsite", "test", "config"][neutral_bit % 4],
                            "edge_family_count": 2 + (neutral_bit % 3),
                            "candidate_node_count": 3 + (neutral_bit % 4),
                        },
                        "neutral_context_bits": {
                            "tests_visible": neutral_bit % 2 == 0,
                            "config_visible": neutral_bit % 3 == 0,
                            "entrypoint_visible": neutral_bit % 4 == 0,
                            "symbol_names_visible": neutral_bit % 2 == 1,
                        },
                        "budget": {
                            "max_files": 2,
                            "max_symbols": 2,
                            "decoder_budget_ok": False,
                        },
                    }
                    clean_state = {
                        "edit_localization_target": target,
                        "action_sequence": spec["action_sequence"],
                        "file_plan": f"localize {target.lower()} through visible evidence and keep patch bounded",
                    }
                    row = {
                        "row_id": rid,
                        "split": split,
                        "objective_family": "edit_localization",
                        "route": "KEEP_STRUCTURED",
                        "authority": AUTHORITY_CLOSED,
                        "corrupted_state": corrupted_state,
                        "clean_state": clean_state,
                        "loss_mask": loss_mask(),
                        "source_stage": "stage8629_recovery_completion_queue",
                        "semantic_key": f"{split}:{language}:{task_key}:{target}",
                    }
                    judged = judge_row(
                        {
                            "row_id": rid,
                            "objective_family": "edit_localization",
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
    labels = set(TARGETS)
    leak_rows: list[str] = []
    authority_rows: list[str] = []
    split_target = Counter()
    locality_counts = Counter()
    loss_counts = Counter()
    for row in rows:
        visible = json.dumps(row["corrupted_state"], sort_keys=True)
        for label in labels:
            if label in visible:
                leak_rows.append(row["row_id"])
                break
        if any(row["authority"].values()):
            authority_rows.append(row["row_id"])
        target = row["clean_state"]["edit_localization_target"]
        split_target[(row["split"], target)] += 1
        locality_counts[row["corrupted_state"]["locality_signal"]] += 1
        for key, value in row["loss_mask"].items():
            loss_counts[key] += int(value)
    per_split_target_ok = all(count == len(TASKS) * len(LANGUAGES) for count in split_target.values())
    return {
        "rows": len(rows),
        "leak_row_count": len(leak_rows),
        "leak_rows": leak_rows[:20],
        "authority_row_count": len(authority_rows),
        "split_target_counts": {f"{k[0]}:{k[1]}": v for k, v in sorted(split_target.items())},
        "locality_signal_counts": dict(sorted(locality_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "per_split_target_balanced": per_split_target_ok,
        "passed": len(leak_rows) == 0 and len(authority_rows) == 0 and per_split_target_ok,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    manifest = OUT_DIR / "edit_localization_neutral_manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    audit_card = audit(rows)
    (OUT_DIR / "audit_card.json").write_text(json.dumps(audit_card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": 8636,
        "stage_name": "stage8636_edit_localization_neutral_manifest",
        "passed": audit_card["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": audit_card,
        "artifacts": {
            "manifest": str(manifest.relative_to(ROOT)),
            "audit_card": str((OUT_DIR / "audit_card.json").relative_to(ROOT)),
            "builder": "scripts/build_stage8636_edit_localization_neutral_manifest.py",
        },
        "decision": "Edit-localization neutral builder restored as no-authority structured rows only. Training/runtime/decode remain closed.",
        "next_best_step": "Run shortcut baselines over edit-localization corrupted_state before training candidate consideration.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
