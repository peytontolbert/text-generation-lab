#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9453
NAME = "stage9453_episode_step_head_vocab_design"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9452_episode_step_loss_key_registry_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "episode_step_head_vocab_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_HEAD_VOCAB_DESIGN_STAGE9453.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    failures = []
    if source.get("passed") is not True:
        failures.append("source_stage9452_not_passed")
    design = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9452_episode_step_loss_key_registry_audit",
        "head_contract": {
            "episode_repair_outcome": {
                "loss_key": "episode_repair_outcome_ce",
                "kind": "classification",
                "labels": ["successful_suffix_repair_step", "residual_suffix_repair_step"],
                "head_dim": 4,
            },
            "episode_failure_type": {
                "loss_key": "episode_failure_type_ce",
                "kind": "classification",
                "labels": [
                    "none",
                    "not_exact",
                    "target_prefix_miss",
                    "boundary_next_token_miss",
                    "degenerate_repetition",
                    "unterminated",
                    "not_contentful",
                    "compound_failure",
                ],
                "head_dim": 12,
            },
            "episode_boundary_match": {
                "loss_key": "episode_boundary_match_ce",
                "kind": "classification",
                "labels": ["false", "true"],
                "head_dim": 2,
            },
            "episode_target_prefix_match": {
                "loss_key": "episode_target_prefix_match_ce",
                "kind": "classification",
                "labels": ["false", "true"],
                "head_dim": 2,
            },
            "episode_step_value": {
                "loss_key": "episode_step_value_mse",
                "kind": "scalar_regression_or_two_class_proxy",
                "labels": ["0.0", "1.0"],
                "head_dim": 2,
                "implementation_note": "Use classification proxy first unless scalar regression plumbing is added separately.",
            },
        },
        "required_code_changes_next": [
            "add default structured head dims for episode_* fields",
            "map episode_* loss keys to fields in training_loop",
            "derive clean values from episode_transition for episode_* fields",
            "keep episode_step_denoise_contract_only no-loss mode unchanged",
            "add trainable mode only after leakage and baseline audits",
        ],
        "training_remains_closed": True,
        "decoder_ce_reopened": False,
        "denoise_ce_reopened": False,
        "runtime_reopened": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    DESIGN.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": design["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **design},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Designed episode-step structured heads/vocabs; no model execution or training authority opened.",
        "next_best_step": "Patch model/training-loop structured head support for episode_* fields, then run a static head-support audit and contract-only preflight.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9453 Episode-Step Head/Vocab Design",
        "",
        f"Passed: `{design['passed']}`",
        "",
        "Episode-step supervision should use structured heads for outcome, failure type, boundary match, prefix match, and value proxy. It must not reopen decoder CE from suffix-repair rows.",
        "",
        "Next: patch model/training-loop support, then audit statically before any training authorization.",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "next": summary["next_best_step"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
