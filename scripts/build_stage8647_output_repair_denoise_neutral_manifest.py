#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from objective_row_judge import judge_row


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8647_output_repair_denoise_neutral_manifest"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8647_output_repair_denoise_neutral_manifest.json"

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
SURFACES = [
    ("maintainer_answer", "A user-facing maintainer answer candidate exists."),
    ("patch_plan", "A patch-plan candidate exists."),
    ("test_plan", "A test-plan candidate exists."),
    ("bounded_argument", "A bounded argument candidate exists."),
    ("verifier_summary", "A verifier-summary candidate exists."),
    ("repo_answer", "A repo-answer candidate exists."),
]

REPAIR_ROUTES = {
    "REPAIR_INTERNAL_LEAK": {
        "signal": "internal_token_leak_visible",
        "sequence": ["MASK_INTERNAL_TOKENS", "RENDER_SAFE_SURFACE"],
    },
    "REPAIR_SHORT_OUTPUT": {
        "signal": "short_output_visible",
        "sequence": ["EXPAND_FROM_STRUCTURED_STATE", "VERIFY_SURFACE"],
    },
    "REPAIR_REPETITION": {
        "signal": "degenerate_repetition_visible",
        "sequence": ["MASK_REPEATED_SPANS", "RENDER_SAFE_SURFACE"],
    },
    "REPAIR_WRONG_SURFACE": {
        "signal": "wrong_surface_visible",
        "sequence": ["RESELECT_SURFACE", "RENDER_SAFE_SURFACE"],
    },
    "ABSTAIN_UNRECOVERABLE": {
        "signal": "unsafe_or_unrecoverable_visible",
        "sequence": ["ABSTAIN_UNRECOVERABLE"],
    },
}

REPAIR_ORDER = list(REPAIR_ROUTES)


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
    # Denoise CE remains closed here; this is only repair-route classification.
    enabled = {"repair_surface_ce", "action_sequence_ce", "file_plan_ce"}
    return {key: key in enabled for key in keys}


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for split in ["train", "eval", "strict"]:
        for lang_idx, (language, ext) in enumerate(LANGUAGES):
            for surface_idx, (surface_key, surface_text) in enumerate(SURFACES):
                neutral = lang_idx + surface_idx
                for repair, spec in REPAIR_ROUTES.items():
                    repair_idx = REPAIR_ORDER.index(repair)
                    row_id = f"stage8647_{split}_{language}_{surface_key}_{repair.lower()}"
                    # These are visible context-quality bits, not repair-label bits.
                    # Rotate them independently of the label so they cannot replace
                    # the semantic repair signal during shortcut audits.
                    neutral_context_bits = {
                        "has_internal_token_shape": (neutral + repair_idx) % 5 in {0, 3},
                        "too_short": (neutral + repair_idx + 1) % 5 in {0, 3},
                        "has_repetition": (neutral + repair_idx + 2) % 5 in {0, 3},
                        "surface_mismatch": (neutral + repair_idx + 3) % 5 in {0, 3},
                        "unsafe_or_unrecoverable": (neutral + repair_idx + 4) % 5 in {0, 3},
                        "verifier_feedback_visible": neutral % 2 == 0,
                        "structured_state_available": neutral % 3 != 0,
                    }
                    corrupted_state = {
                        "task_family": "output_repair_denoise",
                        "language": language,
                        "file_extension": ext,
                        "candidate_surface": surface_text,
                        "repair_signal": spec["signal"],
                        "bad_output_features": neutral_context_bits,
                        "budget": {
                            "max_repair_steps": 2,
                            "decoder_budget_ok": False,
                            "denoise_training_authorized": False,
                        },
                    }
                    clean_state = {
                        "output_repair_action": repair,
                        "action_sequence": spec["sequence"],
                        "file_plan": f"route {repair.lower()} without enabling denoise_ce or decoder_ce",
                    }
                    row = {
                        "row_id": row_id,
                        "split": split,
                        "objective_family": "output_repair_denoise",
                        "route": "KEEP_STRUCTURED",
                        "authority": AUTHORITY_CLOSED,
                        "corrupted_state": corrupted_state,
                        "clean_state": clean_state,
                        "loss_mask": loss_mask(),
                        "source_stage": "stage8629_recovery_completion_queue",
                        "semantic_key": f"{split}:{language}:{surface_key}:{repair}",
                    }
                    judged = judge_row(
                        {
                            "row_id": row_id,
                            "objective_family": "output_repair_denoise",
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
    labels = set(REPAIR_ROUTES)
    leak_rows: list[str] = []
    split_repair = Counter()
    signal_counts = Counter()
    loss_counts = Counter()
    authority_rows = 0
    decoder_rows = 0
    denoise_rows = 0
    for row in rows:
        visible = json.dumps(row["corrupted_state"], sort_keys=True)
        for label in labels:
            if label in visible:
                leak_rows.append(row["row_id"])
                break
        authority_rows += int(any(row["authority"].values()))
        decoder_rows += int(row["loss_mask"].get("decoder_ce", False))
        denoise_rows += int(row["loss_mask"].get("denoise_ce", False))
        repair = row["clean_state"]["output_repair_action"]
        split_repair[(row["split"], repair)] += 1
        signal_counts[row["corrupted_state"]["repair_signal"]] += 1
        for key, value in row["loss_mask"].items():
            loss_counts[key] += int(value)
    per_split_repair_ok = all(count == len(LANGUAGES) * len(SURFACES) for count in split_repair.values())
    return {
        "rows": len(rows),
        "leak_row_count": len(leak_rows),
        "leak_rows": leak_rows[:20],
        "authority_row_count": authority_rows,
        "decoder_ce_rows": decoder_rows,
        "denoise_ce_rows": denoise_rows,
        "split_repair_counts": {f"{k[0]}:{k[1]}": v for k, v in sorted(split_repair.items())},
        "repair_signal_counts": dict(sorted(signal_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "per_split_repair_balanced": per_split_repair_ok,
        "passed": len(leak_rows) == 0 and authority_rows == 0 and decoder_rows == 0 and denoise_rows == 0 and per_split_repair_ok,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    manifest = OUT_DIR / "output_repair_denoise_neutral_manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    audit_card = audit(rows)
    (OUT_DIR / "audit_card.json").write_text(json.dumps(audit_card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": 8647,
        "stage_name": "stage8647_output_repair_denoise_neutral_manifest",
        "passed": audit_card["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": audit_card,
        "artifacts": {
            "manifest": str(manifest.relative_to(ROOT)),
            "audit_card": str((OUT_DIR / "audit_card.json").relative_to(ROOT)),
            "builder": "scripts/build_stage8647_output_repair_denoise_neutral_manifest.py",
        },
        "decision": "Output-repair/denoise builder restored as repair-route classification only. denoise_ce and decoder_ce remain disabled.",
        "next_best_step": "Run shortcut baselines over output-repair corrupted_state before any denoise-training candidate consideration.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
