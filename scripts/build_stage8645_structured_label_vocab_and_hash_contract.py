#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8645_structured_label_vocab_and_hash_contract"
SUMMARY = ROOT / "runs" / "summaries" / "stage8645_structured_label_vocab_and_hash_contract.json"
CONFIG_OUT = ROOT / "configs" / "software_maintainer" / "structured_label_vocab_contract_stage8645.json"
TOKENIZER_POINTER = ROOT / "configs" / "tokenizer" / "agentkernel_bpe_1506_recovered_pointer.json"
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
LOSS_TO_FIELD = {
    "surface_role_ce": "surface_role",
    "repair_surface_ce": "repair_surface",
    "build_mode_ce": "build_mode",
    "allowed_import_policy_ce": "allowed_import_policy",
    "blocked_import_policy_ce": "blocked_import_policy",
    "repo_dependency_policy_ce": "repo_dependency_policy",
    "action_sequence_ce": "action_sequence",
    "file_plan_ce": "file_plan",
    "symbol_binding_ce": "symbol_binding",
    "edit_localization_ce": "edit_localization",
    "patch_operator_ce": "patch_operator",
    "verifier_repair_ce": "verifier_repair",
}
HEAD_CAPACITY = {
    "surface_role": 8,
    "repair_surface": 8,
    "action_label": 12,
    "evidence_state": 6,
    "decoder_budget_ok": 2,
    "decode_allowed": 2,
    "build_mode": 5,
    "allowed_import_policy": 4,
    "blocked_import_policy": 4,
    "repo_dependency_policy": 5,
    "action_sequence": 32,
    "file_plan": 40,
    "symbol_binding": 6,
    "edit_localization": 7,
    "patch_operator": 12,
    "verifier_repair": 9,
}
MANIFESTS = {
    "intent_to_build_strategy": ROOT / "runs" / "local" / "artifacts" / "stage8630_intent_to_build_neutral_manifest" / "intent_to_build_neutral_manifest.jsonl",
    "edit_localization": ROOT / "runs" / "local" / "artifacts" / "stage8636_edit_localization_neutral_manifest" / "edit_localization_neutral_manifest.jsonl",
    "patch_operator": ROOT / "runs" / "local" / "artifacts" / "stage8638_patch_operator_neutral_manifest" / "patch_operator_neutral_manifest.jsonl",
    "verifier_repair": ROOT / "runs" / "local" / "artifacts" / "stage8643_verifier_repair_neutral_manifest" / "verifier_repair_neutral_manifest.jsonl",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def clean_value(row: dict[str, Any], field: str) -> str | None:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    alias = {
        "symbol_binding": "binding_action",
        "edit_localization": "edit_localization_target",
        "patch_operator": "patch_operator",
        "verifier_repair": "verifier_repair_action",
    }
    keys = [field]
    if field in alias:
        keys.append(alias[field])
    for key in keys:
        if key in clean:
            value = clean[key]
            break
        if key in target:
            value = target[key]
            break
        if key in row:
            value = row[key]
            break
    else:
        return None
    if isinstance(value, list):
        return " > ".join(str(item) for item in value)
    return str(value)


def enabled_fields(row: dict[str, Any]) -> list[str]:
    mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
    return [field for loss, field in LOSS_TO_FIELD.items() if mask.get(loss)]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_OUT.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    token_pointer = json.loads(TOKENIZER_POINTER.read_text(encoding="utf-8"))
    token_json = Path(token_pointer["primary_recovered_paths"]["tokenizer_json"])
    token_config = Path(token_pointer["primary_recovered_paths"]["tokenizer_config"])
    token_hash_ok = (
        token_json.is_file()
        and token_config.is_file()
        and sha256(token_json) == token_pointer["sha256"]["tokenizer_json"]
        and sha256(token_config) == token_pointer["sha256"]["tokenizer_config"]
    )
    if not token_hash_ok:
        errors.append("recovered tokenizer hash check failed")

    manifest_cards: dict[str, Any] = {}
    global_labels: dict[str, Counter[str]] = {}
    for family, path in MANIFESTS.items():
        if not path.is_file():
            errors.append(f"missing manifest: {family} {path}")
            continue
        rows = read_rows(path)
        family_labels: dict[str, Counter[str]] = {}
        loss_counts = Counter()
        authority_rows = []
        for row in rows:
            if any(bool(v) for v in (row.get("authority") or {}).values()):
                authority_rows.append(row.get("row_id"))
            for loss, enabled in (row.get("loss_mask") or {}).items():
                loss_counts[loss] += int(bool(enabled))
            for field in enabled_fields(row):
                value = clean_value(row, field)
                if value is None:
                    errors.append(f"missing label value for {family}:{field}:{row.get('row_id')}")
                    continue
                family_labels.setdefault(field, Counter())[value] += 1
                global_labels.setdefault(field, Counter())[value] += 1
        field_cards = {}
        for field, counts in sorted(family_labels.items()):
            labels = sorted(counts)
            capacity = HEAD_CAPACITY.get(field, 0)
            fits = len(labels) <= capacity
            if not fits:
                errors.append(f"head capacity exceeded for {family}:{field}: labels={len(labels)} capacity={capacity}")
            field_cards[field] = {
                "labels": {label: index for index, label in enumerate(labels)},
                "label_counts": dict(sorted(counts.items())),
                "label_count": len(labels),
                "head_capacity": capacity,
                "fits_head_capacity": fits,
            }
        if authority_rows:
            errors.append(f"authority rows present in {family}: {len(authority_rows)}")
        manifest_cards[family] = {
            "path": str(path.relative_to(ROOT)),
            "sha256": sha256(path),
            "rows": len(rows),
            "loss_counts": dict(sorted(loss_counts.items())),
            "fields": field_cards,
            "authority_rows": len(authority_rows),
        }

    global_cards = {}
    for field, counts in sorted(global_labels.items()):
        labels = sorted(counts)
        capacity = HEAD_CAPACITY.get(field, 0)
        fits = len(labels) <= capacity
        if not fits:
            errors.append(f"global head capacity exceeded for {field}: labels={len(labels)} capacity={capacity}")
        global_cards[field] = {
            "labels": {label: index for index, label in enumerate(labels)},
            "label_counts": dict(sorted(counts.items())),
            "label_count": len(labels),
            "head_capacity": capacity,
            "fits_head_capacity": fits,
        }

    card = {
        "stage": 8645,
        "stage_name": "stage8645_structured_label_vocab_and_hash_contract",
        "passed": not errors,
        "authority": AUTHORITY_CLOSED,
        "model_execution_authorized": False,
        "decoder_ce_training_authorized": False,
        "tokenizer_contract": {
            "pointer": str(TOKENIZER_POINTER.relative_to(ROOT)),
            "tokenizer_json_hash_ok": token_hash_ok,
            "vocab_size": token_pointer.get("vocab_size"),
            "tokenizer_kind": token_pointer.get("tokenizer_kind"),
        },
        "manifest_cards": manifest_cards,
        "global_label_vocabs": global_cards,
        "errors": errors,
        "next_best_step": "Add structured telemetry assertion audit for future executed probes, then restore denoise/repair objective contracts before any data recovery.",
    }
    CONFIG_OUT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "structured_label_vocab_contract.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
