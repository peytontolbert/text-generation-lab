#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from objective_row_judge import judge_row


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8645_bounded_decoder_arguments_neutral_manifest"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8645_bounded_decoder_arguments_neutral_manifest.json"

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
ACTION_CONTEXTS = [
    ("add_import_plan", "A structured action selected an approved import argument."),
    ("callsite_plan", "A structured action selected a call argument."),
    ("literal_plan", "A structured action selected a literal argument."),
    ("path_plan", "A structured action selected a file path argument."),
    ("name_plan", "A structured action selected an identifier argument."),
    ("hold_plan", "A structured action determined decode should be held."),
]

ARG_TYPES = {
    "ARG_NAME": {
        "signal": "identifier_argument_visible",
        "sequence": ["PACKAGE_IDENTIFIER_ARG"],
    },
    "ARG_LITERAL": {
        "signal": "literal_argument_visible",
        "sequence": ["PACKAGE_LITERAL_ARG"],
    },
    "ARG_IMPORT": {
        "signal": "approved_import_argument_visible",
        "sequence": ["PACKAGE_IMPORT_ARG"],
    },
    "ARG_CALL": {
        "signal": "call_argument_visible",
        "sequence": ["PACKAGE_CALL_ARG"],
    },
    "ARG_PATH": {
        "signal": "path_argument_visible",
        "sequence": ["PACKAGE_PATH_ARG"],
    },
    "RETRIEVE_MORE": {
        "signal": "argument_evidence_missing",
        "sequence": ["RETRIEVE_MORE"],
    },
    "HOLD_LONG_OUTPUT": {
        "signal": "argument_over_budget_visible",
        "sequence": ["HOLD_LONG_OUTPUT"],
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
    # There is no decoder CE here. This only teaches the pre-decode argument route/packaging decision.
    enabled = {"action_sequence_ce", "file_plan_ce"}
    return {key: key in enabled for key in keys}


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for split in ["train", "eval", "strict"]:
        for lang_idx, (language, ext) in enumerate(LANGUAGES):
            for ctx_idx, (ctx_key, ctx_text) in enumerate(ACTION_CONTEXTS):
                neutral = lang_idx + ctx_idx
                for arg_type, spec in ARG_TYPES.items():
                    row_id = f"stage8645_{split}_{language}_{ctx_key}_{arg_type.lower()}"
                    decode_allowed = arg_type not in {"RETRIEVE_MORE", "HOLD_LONG_OUTPUT"}
                    corrupted_state = {
                        "task_family": "bounded_decoder_arguments",
                        "language": language,
                        "file_extension": ext,
                        "authorized_structured_action": ctx_text,
                        "argument_signal": spec["signal"],
                        "bounded_argument_features": {
                            "small_argument_required": True,
                            "argument_evidence_visible": arg_type != "RETRIEVE_MORE",
                            "over_budget_signal": arg_type == "HOLD_LONG_OUTPUT",
                            "approved_import_policy_visible": neutral % 3 == 0,
                            "path_context_visible": neutral % 4 == 0,
                            "symbol_context_visible": neutral % 2 == 0,
                        },
                        "budget": {
                            "target_length_bucket": ["tiny", "short", "medium"][neutral % 3],
                            "max_arg_tokens": 16,
                            "decoder_budget_ok": False,
                        },
                    }
                    clean_state = {
                        "bounded_argument_type": arg_type,
                        "action_sequence": spec["sequence"],
                        "file_plan": f"package {arg_type.lower()} as structured bounded decoder argument without enabling decoder_ce",
                    }
                    row = {
                        "row_id": row_id,
                        "split": split,
                        "objective_family": "bounded_decoder_arguments",
                        "route": "KEEP_STRUCTURED",
                        "authority": AUTHORITY_CLOSED,
                        "corrupted_state": corrupted_state,
                        "clean_state": clean_state,
                        "loss_mask": loss_mask(),
                        "source_stage": "stage8629_recovery_completion_queue",
                        "semantic_key": f"{split}:{language}:{ctx_key}:{arg_type}",
                    }
                    judged = judge_row(
                        {
                            "row_id": row_id,
                            "objective_family": "bounded_decoder_arguments",
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
    labels = set(ARG_TYPES)
    leak_rows: list[str] = []
    split_type = Counter()
    signal_counts = Counter()
    loss_counts = Counter()
    authority_rows = 0
    decoder_rows = 0
    for row in rows:
        visible = json.dumps(row["corrupted_state"], sort_keys=True)
        for label in labels:
            if label in visible:
                leak_rows.append(row["row_id"])
                break
        authority_rows += int(any(row["authority"].values()))
        decoder_rows += int(row["loss_mask"].get("decoder_ce", False))
        arg_type = row["clean_state"]["bounded_argument_type"]
        split_type[(row["split"], arg_type)] += 1
        signal_counts[row["corrupted_state"]["argument_signal"]] += 1
        for key, value in row["loss_mask"].items():
            loss_counts[key] += int(value)
    per_split_type_ok = all(count == len(LANGUAGES) * len(ACTION_CONTEXTS) for count in split_type.values())
    return {
        "rows": len(rows),
        "leak_row_count": len(leak_rows),
        "leak_rows": leak_rows[:20],
        "authority_row_count": authority_rows,
        "decoder_ce_rows": decoder_rows,
        "split_argument_type_counts": {f"{k[0]}:{k[1]}": v for k, v in sorted(split_type.items())},
        "argument_signal_counts": dict(sorted(signal_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "per_split_argument_type_balanced": per_split_type_ok,
        "passed": len(leak_rows) == 0 and authority_rows == 0 and decoder_rows == 0 and per_split_type_ok,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    manifest = OUT_DIR / "bounded_decoder_arguments_neutral_manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    audit_card = audit(rows)
    (OUT_DIR / "audit_card.json").write_text(json.dumps(audit_card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": 8645,
        "stage_name": "stage8645_bounded_decoder_arguments_neutral_manifest",
        "passed": audit_card["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": audit_card,
        "artifacts": {
            "manifest": str(manifest.relative_to(ROOT)),
            "audit_card": str((OUT_DIR / "audit_card.json").relative_to(ROOT)),
            "builder": "scripts/build_stage8645_bounded_decoder_arguments_neutral_manifest.py",
        },
        "decision": "Bounded-decoder argument builder restored as structured argument packaging only. decoder_ce remains disabled.",
        "next_best_step": "Run shortcut baselines over bounded-decoder argument corrupted_state before any decoder candidate consideration.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
