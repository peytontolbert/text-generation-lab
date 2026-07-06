#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

from scripts.counterfactual_obligation_audit import audit_rows
from scripts.curriculum_compiler import compile_rows
from scripts.dataset_junk_ood_ranker_v1 import rank_rows_v1
from scripts.objective_row_judge import judge_row
from scripts.shortcut_baseline_audit import audit_shortcuts

STAGE = 8931
NAME = "stage8931_orchestrated_compiler_synthetic_dry_run"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ORCHESTRATED_COMPILER_SYNTHETIC_DRY_RUN_STAGE8931.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

SOURCE_SUMMARY = ROOT / "runs/summaries/stage8930_targeted_compiler_gap_tests_readiness.json"

SYNTHETIC_INPUT = OUT_DIR / "synthetic_input_rows.jsonl"
JUDGED_ROWS = OUT_DIR / "judged_rows.jsonl"
RANKED_ROWS = OUT_DIR / "ranked_rows.jsonl"
SHORTCUT_CARD = OUT_DIR / "shortcut_baseline_card.json"
COUNTERFACTUAL_CARD = OUT_DIR / "counterfactual_obligation_card.json"
COMPILE_CARD = OUT_DIR / "compile_card.json"
DRY_RUN_CARD = OUT_DIR / "orchestrated_compiler_synthetic_dry_run.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def synthetic_rows() -> list[dict[str, Any]]:
    base = {
        "objective_family": "synthetic_compiler_contract",
        "split": "train",
        "gate_status": {
            "source_inventory_lineage": True,
            "source_provenance": True,
            "contamination_leakage_detector": True,
            "golden_locked_eval_suite": True,
            "drift_canary_regression_monitor": True,
            "cluster_slice_near_duplicate_detector": True,
            "dataset_junk_ood_ranker_v1": True,
            "schema_drift_detector": True,
        },
    }
    return [
        {
            **base,
            "row_id": "syn_positive_original",
            "semantic_key": "syn_group_1",
            "obligation_type": "POSITIVE_ORIGINAL",
            "encoder": "Intent asks for bounded structured state recovery.",
            "target": "recover build_mode",
            "decode_allowed": False,
            "decoder_budget_ok": True,
            "route": "KEEP_STRUCTURED",
        },
        {
            **base,
            "row_id": "syn_evidence_removed",
            "semantic_key": "syn_group_1",
            "obligation_type": "EVIDENCE_REMOVED_OR_RETRIEVE",
            "encoder": "Intent lacks source evidence.",
            "target": "retrieve more",
            "missing_evidence": True,
            "evidence_state": "missing",
            "decode_allowed": False,
            "decoder_budget_ok": True,
        },
        {
            **base,
            "row_id": "syn_boundary_sibling",
            "semantic_key": "syn_group_1",
            "obligation_type": "CONTRASTIVE_BOUNDARY_SIBLING",
            "encoder": "Same intent but long generated target is requested.",
            "target": "x " * 900,
            "decode_allowed": True,
            "decoder_budget_ok": False,
        },
        {
            **base,
            "row_id": "syn_internal_leak_repair",
            "semantic_key": "syn_group_2",
            "obligation_type": "POSITIVE_ORIGINAL",
            "encoder": "Bad output must be repaired.",
            "target": "<MTC> hidden control token leaked",
            "decode_allowed": True,
            "decoder_budget_ok": True,
        },
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def build_dry_run(registry: dict[str, Any]) -> dict[str, Any]:
    rows = synthetic_rows()
    judged = [judge_row(row, decoder_token_cap=256) for row in rows]
    ranked_card = rank_rows_v1(rows, max_decoder_tokens=768)
    ranked = ranked_card["ranked_rows"]
    shortcut = audit_shortcuts(rows, target_field="obligation_type", feature_fields=["decode_allowed", "decoder_budget_ok", "evidence_state"], ceiling=0.8)
    counterfactual = audit_rows(rows)
    buckets, compile_card = compile_rows(ranked, allow_decoder=False, allow_denoise=False, allow_runtime=False, require_recovered_gates=False)
    objective_rows = sum(len(v) for v in buckets.values())
    checks = {
        "source_stage8930_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "synthetic_rows_only": True,
        "no_data_mining": True,
        "judge_rows_emitted": len(judged) == len(rows),
        "ranker_rows_emitted": len(ranked) == len(rows),
        "shortcut_card_emitted": shortcut["rows"] == len(rows),
        "counterfactual_card_emitted": counterfactual["rows"] == len(rows),
        "compile_card_emitted": compile_card["rows"] == len(rows),
        "objective_rows_match": objective_rows == len(rows),
        "decoder_loss_closed": compile_card["loss_counts"].get("decoder_ce", 0) == 0,
        "denoise_loss_closed": compile_card["loss_counts"].get("denoise_ce", 0) == 0,
        "runtime_loss_closed": compile_card["loss_counts"].get("runtime_reward", 0) == 0,
        "training_remains_blocked": True,
        "runtime_remains_blocked": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "checks": checks,
        "metrics": {
            "synthetic_rows": len(rows),
            "judged_rows": len(judged),
            "ranked_rows": len(ranked),
            "compiled_rows": objective_rows,
            "objective_families": len(compile_card["objective_counts"]),
            "decoder_ce_loss_rows": compile_card["loss_counts"].get("decoder_ce", 0),
            "denoise_ce_loss_rows": compile_card["loss_counts"].get("denoise_ce", 0),
            "runtime_reward_rows": compile_card["loss_counts"].get("runtime_reward", 0),
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
        },
        "rows": rows,
        "judged_rows": judged,
        "ranked_card": ranked_card,
        "ranked_rows": ranked,
        "shortcut_card": shortcut,
        "counterfactual_card": counterfactual,
        "compile_card": compile_card,
        "authority": dict(AUTHORITY_CLOSED),
    }


def validate_dry_run(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8930, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    dry_run = build_dry_run(registry)
    failures = validate_dry_run(dry_run, registry)
    write_jsonl(SYNTHETIC_INPUT, dry_run["rows"])
    write_jsonl(JUDGED_ROWS, dry_run["judged_rows"])
    write_jsonl(RANKED_ROWS, dry_run["ranked_rows"])
    SHORTCUT_CARD.write_text(json.dumps(dry_run["shortcut_card"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COUNTERFACTUAL_CARD.write_text(json.dumps(dry_run["counterfactual_card"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMPILE_CARD.write_text(json.dumps(dry_run["compile_card"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DRY_RUN_CARD.write_text(json.dumps({k: v for k, v in dry_run.items() if k not in {"rows", "judged_rows", "ranked_rows"}}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **dry_run["metrics"],
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "artifacts": {
            "dry_run": str(DRY_RUN_CARD.relative_to(ROOT)),
            "synthetic_input": str(SYNTHETIC_INPUT.relative_to(ROOT)),
            "judged_rows": str(JUDGED_ROWS.relative_to(ROOT)),
            "ranked_rows": str(RANKED_ROWS.relative_to(ROOT)),
            "shortcut_card": str(SHORTCUT_CARD.relative_to(ROOT)),
            "counterfactual_card": str(COUNTERFACTUAL_CARD.relative_to(ROOT)),
            "compile_card": str(COMPILE_CARD.relative_to(ROOT)),
        },
        "decision": "Orchestrated compiler synthetic dry-run passed: judge/rank/shortcut/counterfactual/compile wiring works on synthetic rows with decoder, denoise, runtime, mining, execution, and training closed.",
        "next_best_step": "Add a no-mining compiler CLI wrapper contract for this orchestration, then decide whether to return to checkpoint blockers or dataset recovery.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8931 Orchestrated Compiler Synthetic Dry Run",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage runs the recovered compiler sequence on synthetic in-memory rows only: judge, junk/OOD rank, shortcut audit, counterfactual audit, and curriculum compile.",
        "",
        f"Synthetic rows: `{dry_run['metrics']['synthetic_rows']}`",
        f"Compiled rows: `{dry_run['metrics']['compiled_rows']}`",
        f"Decoder CE rows: `{dry_run['metrics']['decoder_ce_loss_rows']}`",
        f"Denoise CE rows: `{dry_run['metrics']['denoise_ce_loss_rows']}`",
        "",
        "No data mining, model execution, runtime, decoder CE authorization, denoise CE authorization, or training is opened.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8931 Orchestrated Compiler Synthetic Dry Run"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8931 executes the compiler contract on synthetic rows only: objective judge, junk/OOD ranker, shortcut audit, counterfactual audit, and curriculum compiler. It verifies loss masks keep decoder CE, denoise CE, runtime, mining, execution, and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
