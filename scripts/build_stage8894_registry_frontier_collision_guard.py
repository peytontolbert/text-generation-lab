#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8894
NAME = "stage8894_registry_frontier_collision_guard"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_FRONTIER_COLLISION_GUARD_STAGE8894.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
PROTECTED_STAGE_MIN = 8880
RESERVED_UNRUN_STAGES = {8890}

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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def frontier_collision_audit(registry: dict[str, Any], *, current_stage: int = STAGE) -> dict[str, Any]:
    rows = list(registry.get("rows") or [])
    protected_rows = [row for row in rows if int(row.get("stage", -1)) >= PROTECTED_STAGE_MIN]
    by_stage: dict[int, list[str]] = defaultdict(list)
    by_name: dict[str, list[int]] = defaultdict(list)
    for row in protected_rows:
        stage = int(row.get("stage", -1))
        name = str(row.get("stage_name") or "")
        by_stage[stage].append(name)
        by_name[name].append(stage)
    duplicate_stage_numbers = {
        str(stage): names
        for stage, names in sorted(by_stage.items())
        if len(set(names)) > 1 or len(names) > 1
    }
    duplicate_stage_names = {
        name: stages
        for name, stages in sorted(by_name.items())
        if name and len(stages) > 1
    }
    reserved_stage_rows = {
        str(stage): by_stage.get(stage, [])
        for stage in RESERVED_UNRUN_STAGES
        if by_stage.get(stage)
    }
    latest_stage = int((registry.get("metrics") or {}).get("latest_stage", -1))
    max_seen_stage = max([int(row.get("stage", -1)) for row in rows] or [-1])
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    failures: list[str] = []
    if duplicate_stage_numbers:
        failures.append("duplicate_protected_stage_numbers")
    if duplicate_stage_names:
        failures.append("duplicate_protected_stage_names")
    if reserved_stage_rows:
        failures.append("reserved_unrun_stage_materialized")
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    if latest_stage not in {current_stage - 1, current_stage}:
        failures.append(f"unexpected_registry_frontier:{latest_stage}")
    if max_seen_stage not in {current_stage - 1, current_stage}:
        failures.append(f"unexpected_registry_max_stage:{max_seen_stage}")
    return {
        "passed": not failures,
        "failures": failures,
        "protected_stage_min": PROTECTED_STAGE_MIN,
        "protected_rows": len(protected_rows),
        "duplicate_stage_numbers": duplicate_stage_numbers,
        "duplicate_stage_names": duplicate_stage_names,
        "reserved_stage_rows": reserved_stage_rows,
        "latest_stage_before_update": latest_stage,
        "max_seen_stage_before_update": max_seen_stage,
        "registry_authority_counts_zero": not any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED),
    }


def main() -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = frontier_collision_audit(registry)
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            **audit,
            "authority_rows": 0,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
        },
        "decision": "Registry frontier collision guard passed. Protected recent stages are unique and reserved Stage8890 remains unmaterialized." if audit["passed"] else "Registry frontier collision guard failed.",
        "next_best_step": "Use this guard before adding future no-execution stages. Stage8890 remains reserved for explicit one-run authorization only.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8894 Registry Frontier Collision Guard",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This no-execution guard prevents duplicate stage-number collisions in the protected frontier band after Stage8880.",
        "",
        "Rules:",
        "",
        f"- stages `>= {PROTECTED_STAGE_MIN}` must not duplicate stage numbers or stage names",
        "- reserved Stage8890 must remain unmaterialized until explicit one-run authorization",
        "- registry authority counts must remain zero",
        "",
        "This opens no training, execution, decoder CE, denoise CE, runtime, mining, source/body emission, Gemma, harness, scoring, controller merge, checkpoint export, or promotion.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": card["passed"],
        "path": str(SUMMARY),
        "authority": AUTHORITY_CLOSED,
        "next_best_step": card["next_best_step"],
    })
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {
        **registry.get("metrics", {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": card["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8894 Registry Frontier Collision Guard"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8894 adds a collision guard for the protected frontier band. It prevents duplicate stage numbers/names, keeps reserved Stage8890 unmaterialized, and preserves zero authority counts before adding future no-execution stages.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
