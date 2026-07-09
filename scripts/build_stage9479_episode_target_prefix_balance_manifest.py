#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9479
NAME = "stage9479_episode_target_prefix_balance_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9455_episode_step_trainable_manifest/episode_step_trainable_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts/stage9479_episode_target_prefix_balance_manifest"
MANIFEST = OUT_DIR / "episode_target_prefix_balance_manifest.jsonl"
CARD = OUT_DIR / "episode_target_prefix_balance_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_TARGET_PREFIX_BALANCE_MANIFEST_STAGE9479.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LOSS_KEYS = [
    "action_sequence_ce",
    "allowed_import_policy_ce",
    "blocked_import_policy_ce",
    "build_mode_ce",
    "decoder_ce",
    "denoise_ce",
    "edit_localization_ce",
    "episode_boundary_match_ce",
    "episode_failure_type_ce",
    "episode_repair_outcome_ce",
    "episode_step_value_mse",
    "episode_target_prefix_match_ce",
    "file_plan_ce",
    "patch_operator_ce",
    "repair_surface_ce",
    "repo_dependency_policy_ce",
    "runtime_reward",
    "suffix_choice_ce",
    "surface_role_ce",
    "symbol_binding_ce",
    "verifier_repair_ce",
]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def label(row: dict) -> bool:
    return bool(row["episode_transition"]["observation_t"].get("target_prefix_match"))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source_rows = read_jsonl(SOURCE)
    by_id = {row["row_id"]: row for row in source_rows}
    eval_ids = ["stage9455_episode_step_trainable_0004", "stage9455_episode_step_trainable_0005"]
    strict_ids = ["stage9455_episode_step_trainable_0025", "stage9455_episode_step_trainable_0006"]
    heldout = set(eval_ids + strict_ids)
    rows: list[dict] = []
    for index, source in enumerate(source_rows):
        row = copy.deepcopy(source)
        source_id = str(row["row_id"])
        row["row_id"] = f"stage9479_target_prefix_balance_{index:04d}"
        row["source_stage9455_row_id"] = source_id
        row["objective_family"] = "episode_target_prefix_balance_repair"
        row["route"] = "KEEP_EPISODE_TARGET_PREFIX_BALANCE"
        row["split"] = "eval" if source_id in eval_ids else "strict_eval" if source_id in strict_ids else "train"
        row["target_prefix_balance_card"] = {
            "target_prefix_match": label(source),
            "source_split": source.get("split"),
            "source_row_id": source_id,
            "focused_loss": "episode_target_prefix_match_ce",
        }
        row["loss_mask"] = {key: False for key in LOSS_KEYS}
        row["loss_mask"]["episode_target_prefix_match_ce"] = True
        row["authority"] = dict(AUTHORITY_CLOSED)
        row.setdefault("anti_cheat", {})["observation_hidden_from_encoder"] = True
        row["anti_cheat"]["reward_hidden_from_encoder"] = True
        row["anti_cheat"]["state_t_plus_1_hidden_from_encoder"] = True
        rows.append(row)
    write_jsonl(MANIFEST, rows)

    split_counts: dict[str, int] = {}
    split_label_counts: dict[str, dict[str, int]] = {}
    split_lang_counts: dict[str, dict[str, int]] = {}
    for row in rows:
        split = row["split"]
        split_counts[split] = split_counts.get(split, 0) + 1
        lab = str(label(row)).lower()
        split_label_counts.setdefault(split, {})[lab] = split_label_counts.setdefault(split, {}).get(lab, 0) + 1
        lang_key = f"{row.get('language_family')}::{lab}"
        split_lang_counts.setdefault(split, {})[lang_key] = split_lang_counts.setdefault(split, {}).get(lang_key, 0) + 1
    loss_counts = {key: sum(1 for row in rows if row["loss_mask"].get(key)) for key in LOSS_KEYS}
    authority_rows = [row["row_id"] for row in rows if any(bool(v) for v in row.get("authority", {}).values())]
    failures = []
    if split_counts != {"eval": 2, "strict_eval": 2, "train": 46}:
        failures.append("unexpected_split_counts")
    if split_label_counts.get("eval") != {"false": 1, "true": 1}:
        failures.append("eval_not_label_balanced")
    if split_label_counts.get("strict_eval") != {"false": 1, "true": 1}:
        failures.append("strict_not_label_balanced")
    if loss_counts.get("episode_target_prefix_match_ce") != 50:
        failures.append("target_prefix_loss_not_enabled_all_rows")
    for key, count in loss_counts.items():
        if key != "episode_target_prefix_match_ce" and count:
            failures.append(f"forbidden_loss_enabled:{key}")
    if authority_rows:
        failures.append("authority_rows_present")
    passed = not failures
    card = {
        "passed": passed,
        "failures": failures,
        "rows": len(rows),
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "split_counts": split_counts,
        "split_label_counts": split_label_counts,
        "split_language_label_counts": split_lang_counts,
        "loss_counts": loss_counts,
        "authority_rows": len(authority_rows),
        "eval_source_ids": eval_ids,
        "strict_source_ids": strict_ids,
        "design_note": "Focused target-prefix repair manifest: only episode_target_prefix_match_ce is enabled, with eval/strict each containing one positive and one negative target-prefix example.",
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    authority = dict(AUTHORITY_CLOSED)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": passed,
        "authority": authority,
        "metrics": {**authority, **card},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built a target-prefix focused balance manifest after Stage9478 isolated episode_target_prefix_match as the residual field.",
        "next_best_step": "Run Stage9480 contract-only preflight for the target-prefix focused target-100M structured probe; do not execute until the preflight passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9479 Episode Target-Prefix Balance Manifest",
        "",
        f"Passed: `{passed}`",
        f"Rows: `{len(rows)}`",
        f"Splits: `{split_counts}`",
        f"Split label counts: `{split_label_counts}`",
        f"Enabled loss: `episode_target_prefix_match_ce`",
        "",
        "This manifest isolates the Stage9478 residual target-prefix field. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": passed, "path": str(SUMMARY), "authority": authority, "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = bool(reg_rows)
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows)}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": passed, "failures": failures, "split_label_counts": split_label_counts}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
