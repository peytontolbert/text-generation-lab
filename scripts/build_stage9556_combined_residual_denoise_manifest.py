#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9556
NAME = "stage9556_combined_residual_denoise_manifest"
REAL = ROOT / "runs/local/artifacts/stage9545_residual_repair_route_manifest/residual_repair_route_manifest.jsonl"
DESIGN = ROOT / "runs/local/artifacts/stage9549_residual_denoise_design_examples/residual_denoise_design_examples.jsonl"
SOURCE_AUDIT = ROOT / "runs/summaries/stage9555_residual_denoise_one_run_ticket_preflight_design_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "combined_residual_denoise_manifest.jsonl"
CARD = OUT_DIR / "combined_residual_denoise_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COMBINED_RESIDUAL_DENOISE_MANIFEST_STAGE9556.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

TARGET_BUCKETS = {"REPAIR_PREFIX_ONLY", "REPAIR_PREFIX_AND_BOUNDARY"}
ALL_LOSSES = {
    "decoder_ce", "denoise_ce", "runtime_reward", "structured_aux", "episode_failure_type_ce", "episode_repair_outcome_ce", "episode_step_value_mse", "suffix_choice_ce", "verifier_repair_ce", "patch_operator_ce", "edit_localization_ce", "action_sequence_ce"
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def update_registry(summary: dict) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")


def closed_loss_mask(row: dict) -> dict[str, bool]:
    mask = dict(row.get("loss_mask") or {})
    for loss in ALL_LOSSES:
        mask[loss] = False
    return mask


def real_target(row: dict) -> dict:
    rr = row.get("residual_repair_route") if isinstance(row.get("residual_repair_route"), dict) else {}
    return {"repair_bucket": rr.get("repair_bucket"), "failure_type": rr.get("failure_type"), "target_authority": "stage9545_effective_verifier_route"}


def design_target(row: dict) -> dict:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    return {"repair_bucket": target.get("repair_bucket"), "failure_type": target.get("failure_type"), "target_authority": "stage9549_design_counterbalance"}


def normalize(row: dict, source_kind: str, idx: int) -> dict:
    target = real_target(row) if source_kind == "real" else design_target(row)
    bucket = str(target.get("repair_bucket"))
    candidate = bucket in TARGET_BUCKETS
    out = copy.deepcopy(row)
    out["row_id"] = f"stage9556_combined_residual_denoise_{idx:04d}"
    out["source_row_id"] = row.get("row_id")
    out["source_kind"] = source_kind
    out["objective_family"] = "combined_residual_denoise_closed_manifest"
    out["route"] = "RESIDUAL_DENOISE_CANDIDATE_CLOSED" if candidate else "RARE_RESIDUAL_DENOISE_HOLDOUT_CLOSED"
    out["target"] = target
    out["residual_denoise_contract"] = {
        "stage": 9556,
        "candidate_for_future_denoise_ce": candidate,
        "rare_holdout": not candidate,
        "denoise_ce_authorized_now": False,
        "decoder_ce_authorized_now": False,
        "runtime_authorized_now": False,
        "target_bucket_visible_to_loss_only_after_future_authorization": True,
    }
    out["authority"] = dict(AUTHORITY_CLOSED)
    out["loss_mask"] = closed_loss_mask(out)
    training_candidate = dict(out.get("training_candidate") or {})
    training_candidate.update({
        "stage9556_combined_residual_denoise_manifest": True,
        "candidate_for_future_denoise_ce": candidate,
        "rare_holdout": not candidate,
        "training_authorized_now": False,
        "model_execution_authorized_now": False,
        "decoder_ce_closed": True,
        "denoise_ce_closed": True,
        "runtime_reward_closed": True,
    })
    out["training_candidate"] = training_candidate
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source_audit = load_json(SOURCE_AUDIT)
    real = load_jsonl(REAL)
    design = load_jsonl(DESIGN)
    failures: list[str] = []
    if source_audit.get("passed") is not True:
        failures.append("stage9555_audit_not_passed")
    if len(real) != 29:
        failures.append("real_row_count_mismatch")
    if len(design) != 15:
        failures.append("design_row_count_mismatch")

    rows = [normalize(row, "real", idx) for idx, row in enumerate(real)]
    rows.extend(normalize(row, "design", len(rows)) for row in design)
    bucket_counts = Counter(str((row.get("target") or {}).get("repair_bucket")) for row in rows)
    route_counts = Counter(row.get("route") for row in rows)
    split_counts = Counter(row.get("split") for row in rows)
    source_counts = Counter(row.get("source_kind") for row in rows)
    candidate_rows = [row for row in rows if (row.get("residual_denoise_contract") or {}).get("candidate_for_future_denoise_ce")]
    holdout_rows = [row for row in rows if (row.get("residual_denoise_contract") or {}).get("rare_holdout")]
    enabled_losses = Counter(loss for row in rows for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)
    authority_rows = [row.get("row_id") for row in rows if any((row.get("authority") or {}).values())]
    leakage_rows = [row.get("row_id") for row in rows if any(key in (row.get("model_input") or {}) for key in ["target", "repair_bucket", "target_repair_bucket", "failure_type", "effective_failure_type", "residual_denoise_contract"])]

    if len(rows) != 44:
        failures.append("combined_row_count_mismatch")
    if len(candidate_rows) != 41 or len(holdout_rows) != 3:
        failures.append("candidate_or_holdout_count_mismatch")
    if enabled_losses:
        failures.append("enabled_losses_present")
    if authority_rows:
        failures.append("authority_rows_present")
    if leakage_rows:
        failures.append("target_or_contract_leaked_into_model_input")

    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    card = {
        "passed": not failures,
        "failures": failures,
        "real_source": str(REAL.relative_to(ROOT)),
        "design_source": str(DESIGN.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "candidate_rows": len(candidate_rows),
        "rare_holdout_rows": len(holdout_rows),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "enabled_losses": dict(sorted(enabled_losses.items())),
        "authority_rows": authority_rows,
        "leakage_rows": leakage_rows,
        "contract": {"all_losses_closed": not enabled_losses, "denoise_ce_closed_until_explicit_authorization": True, "candidate_rows_not_authorized": True, "rare_holdout_rows_excluded_from_future_probe": True},
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "promotion_ready": False,
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": card["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **card}, "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))}, "decision": "Materialized a combined residual-denoise manifest with all losses closed: 41 future candidates and 3 rare holdout rows.", "next_best_step": "Audit Stage9556, then run contract-only manifest preflight with denoise CE still closed until explicit authorization.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join(["# Stage9556 Combined Residual Denoise Manifest", "", f"Passed: `{card['passed']}`", f"Rows: `{len(rows)}`", f"Candidate rows: `{len(candidate_rows)}`", f"Rare holdout rows: `{len(holdout_rows)}`", "", "All losses are closed. This manifest is not an execution ticket.", ""]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(rows), "candidate_rows": len(candidate_rows), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
