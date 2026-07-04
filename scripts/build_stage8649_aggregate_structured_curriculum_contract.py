#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8649_aggregate_structured_curriculum_contract"
SUMMARY = ROOT / "runs" / "summaries" / "stage8649_aggregate_structured_curriculum_contract.json"
CONFIG_OUT = ROOT / "configs" / "software_maintainer" / "aggregate_structured_curriculum_contract_stage8649.json"
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
    "action_sequence": 64,
    "file_plan": 64,
    "symbol_binding": 6,
    "edit_localization": 7,
    "patch_operator": 12,
    "verifier_repair": 9,
}
ALIASES = {
    "symbol_binding": "binding_action",
    "edit_localization": "edit_localization_target",
    "patch_operator": "patch_operator",
    "verifier_repair": "verifier_repair_action",
    "repair_surface": "output_repair_action",
}
MANIFESTS = {
    "intent_to_build_strategy": ROOT / "runs/local/artifacts/stage8630_intent_to_build_neutral_manifest/intent_to_build_neutral_manifest.jsonl",
    "edit_localization": ROOT / "runs/local/artifacts/stage8636_edit_localization_neutral_manifest/edit_localization_neutral_manifest.jsonl",
    "patch_operator": ROOT / "runs/local/artifacts/stage8638_patch_operator_neutral_manifest/patch_operator_neutral_manifest.jsonl",
    "verifier_repair": ROOT / "runs/local/artifacts/stage8643_verifier_repair_neutral_manifest/verifier_repair_neutral_manifest.jsonl",
    "bounded_decoder_arguments": ROOT / "runs/local/artifacts/stage8645_bounded_decoder_arguments_neutral_manifest/bounded_decoder_arguments_neutral_manifest.jsonl",
    "output_repair_denoise": ROOT / "runs/local/artifacts/stage8647_output_repair_denoise_neutral_manifest/output_repair_denoise_neutral_manifest.jsonl",
}
SHORTCUT_SUMMARIES = {
    "intent_to_build_strategy": ROOT / "runs/summaries/stage8631_intent_to_build_shortcut_baseline.json",
    "edit_localization": ROOT / "runs/summaries/stage8637_edit_localization_shortcut_baseline.json",
    "patch_operator": ROOT / "runs/summaries/stage8639_patch_operator_shortcut_baseline.json",
    "verifier_repair": ROOT / "runs/summaries/stage8644_verifier_repair_shortcut_baseline.json",
    "bounded_decoder_arguments": ROOT / "runs/summaries/stage8646_bounded_decoder_arguments_shortcut_baseline.json",
    "output_repair_denoise": ROOT / "runs/summaries/stage8648_output_repair_denoise_shortcut_baseline.json",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def label_value(row: dict[str, Any], field: str) -> str | None:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    keys = [field]
    if field in ALIASES:
        keys.append(ALIASES[field])
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
        return " > ".join(str(v) for v in value)
    return str(value)


def enabled_fields(row: dict[str, Any]) -> list[str]:
    mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
    return [field for loss, field in LOSS_TO_FIELD.items() if mask.get(loss)]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_OUT.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    family_cards: dict[str, Any] = {}
    global_counts: dict[str, Counter[str]] = {}
    total_rows = 0
    total_decoder_ce = 0
    total_denoise_ce = 0
    total_runtime_reward = 0
    for family, path in MANIFESTS.items():
        if not path.is_file():
            errors.append(f"missing manifest: {family}")
            continue
        rows = read_rows(path)
        total_rows += len(rows)
        field_counts: dict[str, Counter[str]] = {}
        split_counts = Counter()
        loss_counts = Counter()
        authority_rows = 0
        missing_labels = []
        for row in rows:
            split = "strict_eval" if str(row.get("split")) == "strict" else str(row.get("split"))
            split_counts[split] += 1
            authority_rows += int(any(bool(v) for v in (row.get("authority") or {}).values()))
            for loss, enabled in (row.get("loss_mask") or {}).items():
                loss_counts[loss] += int(bool(enabled))
            for field in enabled_fields(row):
                value = label_value(row, field)
                if value is None:
                    missing_labels.append(f"{row.get('row_id')}:{field}")
                    continue
                field_counts.setdefault(field, Counter())[value] += 1
                global_counts.setdefault(field, Counter())[value] += 1
        total_decoder_ce += loss_counts.get("decoder_ce", 0)
        total_denoise_ce += loss_counts.get("denoise_ce", 0)
        total_runtime_reward += loss_counts.get("runtime_reward", 0)
        if authority_rows:
            errors.append(f"authority rows in {family}: {authority_rows}")
        if missing_labels:
            errors.append(f"missing labels in {family}: {len(missing_labels)}")
        shortcut = json.loads(SHORTCUT_SUMMARIES[family].read_text(encoding="utf-8")) if SHORTCUT_SUMMARIES[family].is_file() else {"passed": False}
        if not shortcut.get("passed"):
            errors.append(f"shortcut audit missing/failed for {family}")
        family_cards[family] = {
            "path": str(path.relative_to(ROOT)),
            "sha256": sha256(path),
            "rows": len(rows),
            "split_counts": dict(sorted(split_counts.items())),
            "loss_counts": dict(sorted(loss_counts.items())),
            "authority_rows": authority_rows,
            "missing_label_examples": missing_labels[:20],
            "shortcut_audit_passed": bool(shortcut.get("passed")),
            "fields": {field: {"label_count": len(counts), "labels": dict(sorted(counts.items()))} for field, counts in sorted(field_counts.items())},
        }
    global_cards = {}
    for field, counts in sorted(global_counts.items()):
        label_count = len(counts)
        capacity = HEAD_CAPACITY.get(field, 0)
        fits = label_count <= capacity
        if not fits:
            errors.append(f"global head capacity exceeded for {field}: {label_count}>{capacity}")
        global_cards[field] = {
            "label_count": label_count,
            "head_capacity": capacity,
            "fits_head_capacity": fits,
            "labels": {label: index for index, label in enumerate(sorted(counts))},
            "label_counts": dict(sorted(counts.items())),
        }
    if total_decoder_ce:
        errors.append(f"decoder_ce rows present in structured aggregate: {total_decoder_ce}")
    if total_denoise_ce:
        errors.append(f"denoise_ce rows present before denoise authorization: {total_denoise_ce}")
    if total_runtime_reward:
        errors.append(f"runtime_reward rows present before runtime authorization: {total_runtime_reward}")
    card = {
        "stage": 8649,
        "stage_name": "stage8649_aggregate_structured_curriculum_contract",
        "passed": not errors,
        "authority": AUTHORITY_CLOSED,
        "model_execution_authorized": False,
        "decoder_ce_training_authorized": False,
        "total_rows": total_rows,
        "family_cards": family_cards,
        "global_label_vocabs": global_cards,
        "decoder_ce_rows": total_decoder_ce,
        "denoise_ce_rows": total_denoise_ce,
        "runtime_reward_rows": total_runtime_reward,
        "errors": errors,
        "next_best_step": "Add target-config compatibility and full-size non-instantiating parameter/tokenizer/head audit; still do not recover or mine data.",
    }
    CONFIG_OUT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "aggregate_structured_curriculum_contract.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: card[k] for k in ["stage", "stage_name", "passed", "total_rows", "decoder_ce_rows", "denoise_ce_rows", "runtime_reward_rows", "errors", "next_best_step"]}, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
