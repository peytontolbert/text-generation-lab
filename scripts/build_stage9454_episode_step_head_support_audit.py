#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "legacy_src") not in sys.path:
    sys.path.insert(0, str(ROOT / "legacy_src"))
STAGE = 9454
NAME = "stage9454_episode_step_head_support_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9453_episode_step_head_vocab_design.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9446_episode_step_suffix_repair_manifest/episode_step_suffix_repair_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "episode_step_head_support_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_HEAD_SUPPORT_AUDIT_STAGE9454.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUIRED_MAP = {
    "episode_repair_outcome_ce": "episode_repair_outcome",
    "episode_failure_type_ce": "episode_failure_type",
    "episode_boundary_match_ce": "episode_boundary_match",
    "episode_target_prefix_match_ce": "episode_target_prefix_match",
    "episode_step_value_mse": "episode_step_value",
}
REQUIRED_DIMS = {
    "episode_repair_outcome": 4,
    "episode_failure_type": 12,
    "episode_boundary_match": 2,
    "episode_target_prefix_match": 2,
    "episode_step_value": 2,
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def literal_assignment(path: Path, name: str):
    import ast
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name and node.value is not None:
            return ast.literal_eval(node.value)
    raise KeyError(f"{name} not found in {path}")


def episode_value(row: dict, field: str) -> str | None:
    transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    observation = transition.get("observation_t") if isinstance(transition.get("observation_t"), dict) else {}
    verifier = transition.get("reward_or_verifier") if isinstance(transition.get("reward_or_verifier"), dict) else {}
    next_state = transition.get("state_t_plus_1") if isinstance(transition.get("state_t_plus_1"), dict) else {}
    if field == "episode_repair_outcome":
        value = next_state.get("repair_outcome")
    elif field == "episode_failure_type":
        value = verifier.get("failure_type")
        if not value:
            reasons = observation.get("residual_reasons")
            value = "none" if not reasons else ("compound_failure" if isinstance(reasons, list) and len(reasons) > 1 else str(reasons[0] if isinstance(reasons, list) else reasons))
    elif field == "episode_boundary_match":
        value = observation.get("boundary_next_token_match")
    elif field == "episode_target_prefix_match":
        value = observation.get("target_prefix_match")
    elif field == "episode_step_value":
        reward = verifier.get("reward")
        value = "1.0" if float(reward or 0.0) >= 0.5 else "0.0"
    else:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return None if value is None else str(value)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9453_not_passed")
    head_dims = literal_assignment(ROOT / "legacy_src/agentkernel_lite/modeling_transformer.py", "DEFAULT_STRUCTURED_HEAD_DIMS")
    loss_map = literal_assignment(ROOT / "legacy_src/agentkernel_lite/training_loop.py", "STRUCTURED_LOSS_TO_FIELD")
    trainer_modes = literal_assignment(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py", "STRUCTURED_MODE_ALLOWED_LOSSES")
    for loss_key, field in REQUIRED_MAP.items():
        if loss_map.get(loss_key) != field:
            failures.append(f"loss_map_missing:{loss_key}->{field}")
    for field, dim in REQUIRED_DIMS.items():
        if int(head_dims.get(field, 0)) < dim:
            failures.append(f"head_dim_missing:{field}")
    labels_by_field = {field: sorted({value for row in rows if (value := episode_value(row, field)) is not None}) for field in REQUIRED_DIMS}
    for field, labels in labels_by_field.items():
        if not labels:
            failures.append(f"no_labels_extracted:{field}")
        if len(labels) > REQUIRED_DIMS[field]:
            failures.append(f"labels_exceed_head_dim:{field}")
    if trainer_modes.get("episode_step_denoise_contract_only") != set():
        failures.append("contract_only_mode_allows_training_losses")
    if trainer_modes.get("denoise_repair_probe") != {"denoise_ce"}:
        failures.append("denoise_repair_probe_allowed_losses_changed")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9453_episode_step_head_vocab_design",
        "required_map": REQUIRED_MAP,
        "required_dims": REQUIRED_DIMS,
        "labels_by_field": labels_by_field,
        "rows_checked": len(rows),
        "contract_only_allowed_losses": sorted(trainer_modes.get("episode_step_denoise_contract_only", set())),
        "training_authorized_now": False,
        "model_execution_authorized_next": False,
        "decoder_ce_reopened": False,
        "denoise_ce_reopened": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Static episode-step head support exists, but training remains closed pending a manifest/loss-mask enablement audit.",
        "next_best_step": "Build an episode-step trainable manifest with only episode_* losses enabled, then audit shortcut leakage and decoder CE closure before any preexecution authorization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9454 Episode-Step Head Support Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows checked: `{len(rows)}`",
        f"Contract-only allowed losses: `{audit['contract_only_allowed_losses']}`",
        "",
        "The model/training-loop can represent episode-step structured heads, but no training mode has been opened. Decoder CE and denoise CE remain closed.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
