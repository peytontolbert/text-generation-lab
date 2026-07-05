from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from gate_status_contract import gate_status_card, passed_gate_status

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}
LOSS_MASK_CLOSED = {
    "surface_role_ce": False,
    "repair_surface_ce": False,
    "build_mode_ce": False,
    "allowed_import_policy_ce": False,
    "blocked_import_policy_ce": False,
    "repo_dependency_policy_ce": False,
    "action_sequence_ce": False,
    "file_plan_ce": False,
    "symbol_binding_ce": False,
    "edit_localization_ce": False,
    "patch_operator_ce": False,
    "verifier_repair_ce": False,
    "bounded_decoder_argument_ce": False,
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
}


def opaque(value: str, prefix: str = "o") -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def build_bounded_decoder_argument_controls(neutral_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, source in enumerate(neutral_rows):
        old_id = str(source.get("row_id") or source.get("semantic_key") or index)
        old_semantic_key = str(source.get("semantic_key") or "")
        old_parts = old_semantic_key.split(":")
        context_group = old_parts[2] if len(old_parts) >= 3 else opaque(old_id, "ctx")
        corrupted = dict(source.get("corrupted_state") or {})
        clean = dict(source.get("clean_state") or {})
        features = dict(corrupted.get("bounded_argument_features") or {})
        budget = dict(corrupted.get("budget") or {})
        rows.append({
            "row_id": "stage8797_" + opaque(old_id, "row"),
            "split": source.get("split"),
            "objective_family": "bounded_decoder_argument_controls",
            "route": "CANDIDATE_NEEDS_AUDIT",
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "gate_status": passed_gate_status(),
            "source_stage": "stage8797_from_stage8645_bounded_decoder_arguments_neutral_manifest",
            "source_row_ref": {
                "source_stage": source.get("source_stage", "stage8645_bounded_decoder_arguments_neutral_manifest"),
                "source_row_id_hash": opaque(old_id, "srcrow"),
                "source_row_id_in_model_input": False,
            },
            "semantic_key": f"{source.get('split')}:{corrupted.get('language')}:{opaque(old_id, 'sem')}",
            "corrupted_state": {
                "task_family": "bounded_decoder_argument_controls",
                "language": corrupted.get("language"),
                "file_extension": corrupted.get("file_extension"),
                "argument_signal": corrupted.get("argument_signal"),
                "context_group": context_group,
                "bounded_argument_features": features,
                "budget": budget,
            },
            "clean_state": {
                "bounded_argument_type": clean.get("bounded_argument_type"),
                "action_sequence": clean.get("action_sequence"),
                "file_plan": clean.get("file_plan"),
            },
            "anti_cheat": {
                "raw_source_included": False,
                "raw_decoder_text_included": False,
                "raw_patch_body_included": False,
                "target_label_in_id": False,
                "source_row_id_in_model_input": False,
                "requires_shortcut_audit_before_training": True,
                "requires_recovered_gate_status_before_compiler": True,
            },
        })
    return rows


def build_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = Counter((row.get("clean_state") or {}).get("bounded_argument_type") for row in rows)
    splits = Counter(row.get("split") for row in rows)
    signals = Counter((row.get("corrupted_state") or {}).get("argument_signal") for row in rows)
    loss_counts = Counter()
    for row in rows:
        for key, enabled in (row.get("loss_mask") or {}).items():
            if enabled:
                loss_counts[key] += 1
    return {
        "rows": len(rows),
        "labels": dict(sorted(labels.items())),
        "splits": dict(sorted(splits.items())),
        "argument_signals": dict(sorted(signals.items())),
        "gate_status": gate_status_card(rows),
        "authority_rows": sum(int(any((row.get("authority") or {}).values())) for row in rows),
        "training_loss_rows": sum(int(any((row.get("loss_mask") or {}).values())) for row in rows),
        "loss_counts": dict(sorted(loss_counts.items())),
        "raw_source_rows": sum(int((row.get("anti_cheat") or {}).get("raw_source_included") is True) for row in rows),
        "raw_decoder_text_rows": sum(int((row.get("anti_cheat") or {}).get("raw_decoder_text_included") is True) for row in rows),
    }
