#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9472
NAME = "stage9472_episode_obs_diag_balanced_order_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9471_episode_obs_diag_checkpoint_selection_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9461_episode_step_observation_diagnosis_manifest/episode_step_observation_diagnosis_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "episode_obs_diag_balanced_order_manifest.jsonl"
CARD = OUT_DIR / "episode_obs_diag_balanced_order_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_BALANCED_ORDER_MANIFEST_STAGE9472.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LOSSES = {"episode_failure_type_ce", "episode_repair_outcome_ce", "episode_step_value_mse"}
FORBIDDEN = {"decoder_ce", "denoise_ce", "runtime_reward"}
ALL_LOSSES = [
    "surface_role_ce", "repair_surface_ce", "build_mode_ce", "allowed_import_policy_ce",
    "blocked_import_policy_ce", "repo_dependency_policy_ce", "action_sequence_ce", "file_plan_ce",
    "symbol_binding_ce", "edit_localization_ce", "patch_operator_ce", "verifier_repair_ce",
    "suffix_choice_ce", "episode_repair_outcome_ce", "episode_failure_type_ce",
    "episode_boundary_match_ce", "episode_target_prefix_match_ce", "episode_step_value_mse",
    "decoder_ce", "denoise_ce", "runtime_reward",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def cell(row: dict) -> str:
    state = row.get("state") if isinstance(row.get("state"), dict) else {}
    outcome = row.get("episode_transition", {}).get("state_t_plus_1", {}).get("repair_outcome")
    return f"prefix={state.get('raw_prefix_alignment_passed')}|outcome={outcome}"


def clone_row(base: dict, *, row_id: str, split: str) -> dict:
    row = json.loads(json.dumps(base))
    row["row_id"] = row_id
    row["source_stage9461_row_id"] = base.get("row_id")
    row["split"] = split
    row["objective_family"] = "episode_step_observation_diagnosis_balanced_order"
    row["route"] = "KEEP_EPISODE_OBS_DIAG_BALANCED_ORDER"
    row["loss_mask"] = {key: False for key in ALL_LOSSES}
    for key in LOSSES:
        row["loss_mask"][key] = True
    row["authority"] = dict(AUTHORITY_CLOSED)
    row["training_candidate"] = {
        "episode_obs_diag_balanced_order": True,
        "decoder_ce_closed": True,
        "denoise_ce_closed": True,
        "runtime_reward_closed": True,
    }
    return row


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    base_rows = load_jsonl(SOURCE_MANIFEST)
    train = [row for row in base_rows if row.get("split") == "train"]
    success = [row for row in train if cell(row) == "prefix=True|outcome=successful_suffix_repair_step"]
    residual = [row for row in train if cell(row) == "prefix=False|outcome=residual_suffix_repair_step"]
    eval_success = next(row for row in base_rows if row.get("split") == "eval")
    strict_residual = next(row for row in base_rows if row.get("split") == "strict_eval")
    rows: list[dict] = []
    for idx in range(28):
        rows.append(clone_row(success[idx % len(success)], row_id=f"stage9472_bal_success_train_{idx:02d}", split="train"))
        rows.append(clone_row(residual[idx % len(residual)], row_id=f"stage9472_bal_residual_train_{idx:02d}", split="train"))
    rows.append(clone_row(eval_success, row_id="stage9472_bal_eval_success", split="eval"))
    rows.append(clone_row(strict_residual, row_id="stage9472_bal_strict_residual", split="strict_eval"))
    split_counts = Counter(str(row.get("split")) for row in rows)
    cell_counts = Counter(cell(row) for row in rows)
    loss_counts = Counter()
    authority_rows = 0
    forbidden_rows = 0
    for row in rows:
        for key, value in row["loss_mask"].items():
            loss_counts[key] += int(bool(value))
        authority_rows += int(any(bool(v) for v in row["authority"].values()))
        forbidden_rows += int(any(bool(row["loss_mask"].get(key)) for key in FORBIDDEN))
    failures: list[str] = []
    if source.get("passed") is not False or source.get("metrics", {}).get("safety_passed") is not True:
        failures.append("source_stage9471_expected_safe_quality_failure_not_present")
    if not success or not residual:
        failures.append("missing_success_or_residual_pool")
    if split_counts != Counter({"train": 56, "eval": 1, "strict_eval": 1}):
        failures.append("unexpected_split_counts")
    if cell_counts.get("prefix=True|outcome=successful_suffix_repair_step") != 29 or cell_counts.get("prefix=False|outcome=residual_suffix_repair_step") != 29:
        failures.append("unexpected_cell_counts")
    if authority_rows:
        failures.append("authority_rows_present")
    if forbidden_rows:
        failures.append("forbidden_loss_rows_present")
    for key in LOSSES:
        if loss_counts.get(key) != len(rows):
            failures.append(f"loss_count_mismatch:{key}")
    write_jsonl(MANIFEST, rows)
    card = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9471_episode_obs_diag_checkpoint_selection_probe_audit",
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "cell_counts": dict(sorted(cell_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "train_order_contract": "Rows alternate success/residual so deterministic two-row batches see both cells every step.",
        "authority_rows": authority_rows,
        "forbidden_loss_rows": forbidden_rows,
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **card},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built a balanced-order observation diagnosis manifest to remove deterministic minibatch oscillation between success and residual cells.",
        "next_best_step": "Run target-100M contract-only preflight for the balanced-order manifest before execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9472 Episode Observation Diagnosis Balanced-Order Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{len(rows)}`",
        f"Splits: `{dict(sorted(split_counts.items()))}`",
        f"Cells: `{dict(sorted(cell_counts.items()))}`",
        "",
        card["train_order_contract"],
        "",
        "Only episode diagnosis losses are enabled. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows)}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "rows": len(rows), "cell_counts": dict(sorted(cell_counts.items()))}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
