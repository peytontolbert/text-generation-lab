#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from objective_row_judge import judge_row


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8630_intent_to_build_neutral_manifest"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8630_intent_to_build_neutral_manifest.json"

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

LANGUAGES = [
    ("python", "py"),
    ("typescript", "ts"),
    ("rust", "rs"),
    ("cpp", "cpp"),
]

TASKS = [
    ("parse_config", "parse a small configuration payload and return normalized fields"),
    ("validate_input", "validate a user-supplied value and return a structured error"),
    ("format_report", "format computed values into a concise report object"),
    ("load_records", "load records from a local input object and filter invalid entries"),
    ("compute_summary", "compute a deterministic summary from in-memory values"),
    ("adapter_wrapper", "wrap an existing helper behind a stable local interface"),
]

MODES = {
    "USE_WHITELIST_IMPORT": {
        "evidence": "Approved dependency already exposes the exact capability and its public interface is visible.",
        "action_sequence": ["SELECT_IMPORT", "READ_ALLOWED_SOURCE", "BUILD_WRAPPER", "CREATE_TEST", "RUN_VERIFIER"],
        "file_plan": "create wrapper around approved dependency and targeted smoke test",
    },
    "BUILD_ON_TOP": {
        "evidence": "Approved repository provides a related helper, but the task still needs local glue logic.",
        "action_sequence": ["SEARCH_ALLOWED_REPO", "READ_ALLOWED_SOURCE", "BUILD_WRAPPER", "CREATE_TEST", "RUN_VERIFIER"],
        "file_plan": "build adapter layer using visible helper behavior and add focused test",
    },
    "BUILD_FROM_SCRATCH": {
        "evidence": "No approved dependency is relevant, and the goal is small enough for local primitive implementation.",
        "action_sequence": ["BUILD_FROM_SCRATCH", "CREATE_FILE", "CREATE_TEST", "RUN_VERIFIER"],
        "file_plan": "implement local function from visible requirements and add deterministic test",
    },
    "RETRIEVE_MORE": {
        "evidence": "The requested behavior depends on unspecified API details or missing repository context.",
        "action_sequence": ["SEARCH_ALLOWED_REPO", "READ_ALLOWED_SOURCE"],
        "file_plan": "retrieve missing source or docs before choosing build path",
    },
    "ABSTAIN_UNSAFE": {
        "evidence": "The only apparent dependency path is blocked or the requested operation violates the safety policy.",
        "action_sequence": ["REJECT_IMPORT"],
        "file_plan": "do not generate code; report blocked dependency or unsafe request",
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
    enabled = {
        "build_mode_ce",
        "allowed_import_policy_ce",
        "blocked_import_policy_ce",
        "repo_dependency_policy_ce",
        "action_sequence_ce",
        "file_plan_ce",
    }
    return {key: key in enabled for key in keys}


def row_id(*parts: Any) -> str:
    return "stage8630_" + "_".join(str(p) for p in parts)


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for split in ["train", "eval", "strict"]:
        for lang_idx, (lang, ext) in enumerate(LANGUAGES):
            for task_idx, (task_key, task_text) in enumerate(TASKS):
                for mode, spec in MODES.items():
                    rid = row_id(split, lang, task_key, mode.lower())
                    import_state = {
                        "USE_WHITELIST_IMPORT": "approved_exact_dependency_visible",
                        "BUILD_ON_TOP": "approved_partial_dependency_visible",
                        "BUILD_FROM_SCRATCH": "no_relevant_approved_dependency",
                        "RETRIEVE_MORE": "dependency_or_source_context_missing",
                        "ABSTAIN_UNSAFE": "dependency_blocked_or_policy_unsafe",
                    }[mode]
                    neutral_bit = task_idx + lang_idx
                    corrupted_state = {
                        "task_family": "intent_to_build_strategy",
                        "language": lang,
                        "file_extension": ext,
                        "user_goal": task_text,
                        "available_evidence": spec["evidence"],
                        "import_state": import_state,
                        "repo_state": {
                            "allowed_repository_visible": neutral_bit % 2 == 0,
                            "blocked_dependency_signal": neutral_bit % 3 == 0,
                            "missing_context_signal": neutral_bit % 3 == 1,
                            "can_create_file": neutral_bit % 2 == 1,
                            "test_required": True,
                        },
                        "budget": {
                            "max_files": 2,
                            "max_patch_hunks": 2,
                            "decoder_budget_ok": False,
                        },
                    }
                    clean_state = {
                        "build_mode": mode,
                        "action_sequence": spec["action_sequence"],
                        "file_plan": spec["file_plan"],
                        "allowed_import_policy": "ALLOW_VISIBLE_APPROVED_IMPORT" if mode in {"USE_WHITELIST_IMPORT", "BUILD_ON_TOP"} else "NO_APPROVED_IMPORT_USE",
                        "blocked_import_policy": "REJECT_BLOCKED_IMPORT" if mode == "ABSTAIN_UNSAFE" else "NO_BLOCKED_IMPORT_REQUESTED",
                        "repo_dependency_policy": import_state,
                    }
                    row = {
                        "row_id": rid,
                        "split": split,
                        "objective_family": "intent_to_build_strategy",
                        "route": "KEEP_STRUCTURED",
                        "authority": AUTHORITY_CLOSED,
                        "corrupted_state": corrupted_state,
                        "clean_state": clean_state,
                        "loss_mask": loss_mask(),
                        "source_stage": "stage8629_recovery_completion_queue",
                        "semantic_key": f"{split}:{lang}:{task_key}:{mode}",
                    }
                    judged = judge_row(
                        {
                            "row_id": rid,
                            "objective_family": "intent_to_build_strategy",
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
    labels = set(MODES)
    leak_rows: list[str] = []
    authority_rows: list[str] = []
    split_mode = Counter()
    import_state_counts = Counter()
    loss_counts = Counter()
    for row in rows:
        text = json.dumps(row["corrupted_state"], sort_keys=True)
        clean = row["clean_state"]
        for label in labels:
            if label in text:
                leak_rows.append(row["row_id"])
                break
        if any(row["authority"].values()):
            authority_rows.append(row["row_id"])
        split_mode[(row["split"], clean["build_mode"])] += 1
        import_state_counts[row["corrupted_state"]["import_state"]] += 1
        for key, value in row["loss_mask"].items():
            loss_counts[key] += int(value)
    per_split_mode_ok = all(count == len(TASKS) * len(LANGUAGES) for count in split_mode.values())
    return {
        "rows": len(rows),
        "leak_rows": leak_rows[:20],
        "leak_row_count": len(leak_rows),
        "authority_row_count": len(authority_rows),
        "split_mode_counts": {f"{k[0]}:{k[1]}": v for k, v in sorted(split_mode.items())},
        "import_state_counts": dict(sorted(import_state_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "per_split_mode_balanced": per_split_mode_ok,
        "passed": len(leak_rows) == 0 and len(authority_rows) == 0 and per_split_mode_ok,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    manifest = OUT_DIR / "intent_to_build_neutral_manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    audit_card = audit(rows)
    (OUT_DIR / "audit_card.json").write_text(json.dumps(audit_card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": 8630,
        "stage_name": "stage8630_intent_to_build_neutral_manifest",
        "passed": audit_card["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": audit_card,
        "artifacts": {
            "manifest": str(manifest.relative_to(ROOT)),
            "audit_card": str((OUT_DIR / "audit_card.json").relative_to(ROOT)),
            "builder": "scripts/build_stage8630_intent_to_build_neutral_manifest.py",
        },
        "decision": "Intent-to-build neutral masked objective builder restored as no-authority structured rows only. Training/runtime/decode remain closed.",
        "next_best_step": "Run stricter shortcut baselines over corrupted_state before any training candidate is considered.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
