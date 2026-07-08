#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9452
NAME = "stage9452_episode_step_loss_key_registry_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9451_episode_step_denoise_objective_design.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "episode_step_loss_key_registry_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_LOSS_KEY_REGISTRY_AUDIT_STAGE9452.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

EPISODE_KEYS = {
    "episode_repair_outcome_ce",
    "episode_failure_type_ce",
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
    "episode_step_value_mse",
}
REQUIRED_KEYS = EPISODE_KEYS | {"suffix_choice_ce", "decoder_ce", "denoise_ce", "runtime_reward"}
FORBIDDEN = {"decoder_ce", "denoise_ce", "runtime_reward"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def literal_assignment(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise KeyError(f"{name} not found in {path}")


def as_key_set(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(str(key) for key in value)
    return set(str(item) for item in value)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9451_not_passed")

    files = {
        "loss_mask_card": ROOT / "scripts/loss_mask_card.py",
        "curriculum_compiler": ROOT / "scripts/curriculum_compiler.py",
        "objective_row_judge": ROOT / "scripts/objective_row_judge.py",
        "dataset_junk_ood_ranker_v1": ROOT / "scripts/dataset_junk_ood_ranker_v1.py",
    }
    loss_key_sets = {name: as_key_set(literal_assignment(path, "LOSS_KEYS")) for name, path in files.items()}
    schema = load_json(ROOT / "configs/schema/loss_mask.schema.json")
    schema_keys = set((schema.get("properties") or {}).keys())
    trainer_modes = literal_assignment(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py", "STRUCTURED_MODE_ALLOWED_LOSSES")
    compiler_routes = literal_assignment(ROOT / "scripts/curriculum_compiler.py", "ROUTE_TO_LOSSES")
    judge_routes = literal_assignment(ROOT / "scripts/objective_row_judge.py", "ROUTE_TO_LOSSES")

    for name, keys in loss_key_sets.items():
        missing = sorted(REQUIRED_KEYS - keys)
        if missing:
            failures.append(f"{name}_missing_keys:{','.join(missing)}")
    missing_schema = sorted(REQUIRED_KEYS - schema_keys)
    if missing_schema:
        failures.append(f"schema_missing_keys:{','.join(missing_schema)}")
    forbidden_default = set(literal_assignment(ROOT / "scripts/loss_mask_card.py", "FORBIDDEN_BY_DEFAULT"))
    if forbidden_default != FORBIDDEN:
        failures.append("forbidden_by_default_changed")

    # Episode keys are registered, but must not be enabled by legacy/default routes yet.
    compiler_keep = set(compiler_routes.get("KEEP_STRUCTURED", []))
    judge_keep = set(judge_routes.get("KEEP_STRUCTURED", []))
    if compiler_keep & EPISODE_KEYS:
        failures.append("compiler_keep_structured_enables_episode_losses")
    if judge_keep & EPISODE_KEYS:
        failures.append("judge_keep_structured_enables_episode_losses")
    trainer_episode_allowed = set(trainer_modes.get("episode_step_denoise_contract_only", []))
    if trainer_episode_allowed:
        failures.append("contract_only_mode_allows_losses")
    if set(trainer_modes.get("denoise_repair_probe", [])) != {"denoise_ce"}:
        failures.append("denoise_repair_allowed_losses_changed")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9451_episode_step_denoise_objective_design",
        "episode_keys": sorted(EPISODE_KEYS),
        "required_keys": sorted(REQUIRED_KEYS),
        "loss_key_counts": {name: len(keys) for name, keys in sorted(loss_key_sets.items())},
        "schema_key_count": len(schema_keys),
        "forbidden_by_default": sorted(forbidden_default),
        "compiler_keep_structured_episode_overlap": sorted(compiler_keep & EPISODE_KEYS),
        "judge_keep_structured_episode_overlap": sorted(judge_keep & EPISODE_KEYS),
        "trainer_episode_contract_only_allowed_losses": sorted(trainer_episode_allowed),
        "model_heads_implemented_now": False,
        "training_authorized_now": False,
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
        "decision": "Registered episode-step loss keys across schema/compiler/judge/ranker without enabling training or reopening decoder CE.",
        "next_best_step": "Design episode-step structured heads/vocabs for repair outcome, failure type, boundary match, prefix match, and value; keep execution closed until head audit passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9452 Episode-Step Loss Key Registry Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Episode keys: `{sorted(EPISODE_KEYS)}`",
        f"Compiler KEEP_STRUCTURED overlap: `{audit['compiler_keep_structured_episode_overlap']}`",
        f"Trainer contract-only allowed losses: `{audit['trainer_episode_contract_only_allowed_losses']}`",
        "",
        "The keys are registered but not enabled for default routes. Decoder CE and denoise CE remain closed.",
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
