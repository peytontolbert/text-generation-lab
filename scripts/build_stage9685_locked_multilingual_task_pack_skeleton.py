#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9685
NAME = "stage9685_locked_multilingual_task_pack_skeleton"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9684_v27_multilingual_eval_acceptance_contract.json"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage9684_v27_multilingual_eval_acceptance_contract/v27_multilingual_eval_acceptance_contract.json"
SOURCE_GAP = ROOT / "runs/local/artifacts/stage9684_v27_multilingual_eval_acceptance_contract/v27_completion_gap_matrix.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKS = OUT_DIR / "v27_locked_multilingual_task_pack_skeleton.json"
EXCLUSIONS = OUT_DIR / "v27_locked_source_exclusions.jsonl"
AUDIT = OUT_DIR / "v27_locked_multilingual_task_pack_skeleton_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_LOCKED_MULTILINGUAL_TASK_PACK_SKELETON_STAGE9685.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def stable_id(*parts: str) -> str:
    raw = "::".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_summary = load_json(SOURCE_SUMMARY)
    contract = load_json(SOURCE_CONTRACT)
    gap = load_json(SOURCE_GAP)
    anti_cheat = list(contract.get("anti_cheat_requirements") or [])
    cells = gap.get("acceptance_cells") if isinstance(gap.get("acceptance_cells"), list) else []
    packs: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for index, cell in enumerate(cells):
        mode = str(cell.get("mode"))
        language = str(cell.get("language_family"))
        skill = str(cell.get("skill_area"))
        digest = stable_id(mode, language, skill)
        pack_id = f"stage9685_v27_locked_{digest}"
        source_id = f"locked_eval_source::{digest}"
        lineage_hash = hashlib.sha256(json.dumps(cell, sort_keys=True).encode("utf-8")).hexdigest()
        pack = {
            "task_pack_id": pack_id,
            "source_id": source_id,
            "lineage_hash": lineage_hash,
            "split_role": "locked_regression",
            "hidden_final": False,
            "promotion_only": True,
            "train_eligible": False,
            "blocked_training_reason": "v27_locked_eval_pack_never_train_eligible",
            "mode": mode,
            "language_family": language,
            "skill_area": skill,
            "slice_tags": [
                "v27",
                "expert_maintainer",
                mode,
                language,
                skill,
            ],
            "thresholds": {
                "must_beat_gemma12b_same_surface": True,
                "anti_cheat_must_pass": True,
                "expert_rubric_must_pass": True,
            },
            "required_evidence": cell.get("required_evidence") or [],
            "anti_cheat_requirements": anti_cheat,
            "authority": dict(AUTHORITY_CLOSED),
        }
        packs.append(pack)
        exclusions.append({
            "task_pack_id": pack_id,
            "source_id": source_id,
            "lineage_hash": lineage_hash,
            "blocked_from_training": True,
            "reason": "locked_eval_source_never_mined_into_training",
        })
    suite = {
        "suite_name": "v27_locked_multilingual_expert_maintainer_eval_skeleton",
        "source_stage": 9684,
        "benchmark_packs": packs,
        "authority": dict(AUTHORITY_CLOSED),
    }
    PACKS.write_text(json.dumps(suite, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(EXCLUSIONS, exclusions)

    failures: list[str] = []
    if source_summary.get("passed") is not True or contract.get("passed") is not True:
        failures.append("stage9684_not_passed")
    if len(packs) != 72:
        failures.append("pack_count_not_72")
    if len({pack["task_pack_id"] for pack in packs}) != len(packs):
        failures.append("duplicate_task_pack_ids")
    if len({pack["source_id"] for pack in packs}) != len(packs):
        failures.append("duplicate_source_ids")
    bad_train = [pack["task_pack_id"] for pack in packs if pack.get("train_eligible") is not False or pack.get("promotion_only") is not True]
    if bad_train:
        failures.append("locked_pack_train_or_promotion_flags_bad")
    missing_thresholds = [pack["task_pack_id"] for pack in packs if not pack.get("thresholds")]
    if missing_thresholds:
        failures.append("missing_thresholds")
    authority_rows = [pack["task_pack_id"] for pack in packs if any((pack.get("authority") or {}).values())]
    if authority_rows:
        failures.append("authority_rows_present")
    mode_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    skill_counts: dict[str, int] = {}
    for pack in packs:
        mode_counts[pack["mode"]] = mode_counts.get(pack["mode"], 0) + 1
        language_counts[pack["language_family"]] = language_counts.get(pack["language_family"], 0) + 1
        skill_counts[pack["skill_area"]] = skill_counts.get(pack["skill_area"], 0) + 1

    audit = {
        "passed": not failures,
        "failures": failures,
        "packs": len(packs),
        "exclusions": len(exclusions),
        "mode_counts": dict(sorted(mode_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "skill_counts": dict(sorted(skill_counts.items())),
        "bad_train_flags": bad_train,
        "missing_thresholds": missing_thresholds,
        "authority_rows": authority_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Run Stage9686 golden locked eval-suite validation over the skeleton and add train-exclusion enforcement before any Gemma/harness execution."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "exclusions": str(EXCLUSIONS.relative_to(ROOT)),
            "packs": str(PACKS.relative_to(ROOT)),
        },
        "decision": "Materialized locked multilingual expert-maintainer eval pack skeletons for all 72 v2.7 acceptance cells.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9685 Locked Multilingual Task Pack Skeleton",
        "",
        f"Passed: `{audit['passed']}`",
        f"Packs: `{audit['packs']}`",
        f"Modes: `{audit['mode_counts']}`",
        f"Languages: `{audit['language_counts']}`",
        f"Skills: `{audit['skill_counts']}`",
        "",
        "These packs are locked regression / promotion-only skeletons. They are not train eligible and must never be mined into training.",
        "",
        "No Gemma, harness, runtime, model execution, scoring, source/body emission, training, checkpoint export, or promotion is authorized.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": audit["passed"],
        "failures": failures,
        "packs": len(packs),
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
