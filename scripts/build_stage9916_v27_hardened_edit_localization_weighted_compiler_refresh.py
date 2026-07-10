#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from curriculum_compiler import compile_rows
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
    from golden_locked_eval_suite import load_locked_source_ids_from_exclusions
except ModuleNotFoundError:
    from scripts.curriculum_compiler import compile_rows  # type: ignore
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from scripts.golden_locked_eval_suite import load_locked_source_ids_from_exclusions  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9916
NAME = "stage9916_v27_hardened_edit_localization_weighted_compiler_refresh"
LOCKED_EXCLUSIONS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_source_exclusions.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PREPARED = OUT_DIR / "hardened_edit_localization_weighted_prepared_rows.jsonl"
COMPILED_DIR = OUT_DIR / "compiled"
AUDIT = OUT_DIR / "hardened_edit_localization_weighted_compiler_refresh_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_HARDENED_EDIT_LOCALIZATION_WEIGHTED_COMPILER_REFRESH_STAGE9916.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TARGET_SKILL = "edit_localization"
EXTRA_TRAIN_DUPLICATES = 1

_stage9913_path = ROOT / "scripts/build_stage9913_v27_hardened_multisurface_compiler_refresh.py"
_stage9913_spec = importlib.util.spec_from_file_location("stage9913_for_9916", _stage9913_path)
_stage9913 = importlib.util.module_from_spec(_stage9913_spec)
assert _stage9913_spec and _stage9913_spec.loader
sys.modules["stage9913_for_9916"] = _stage9913
_stage9913_spec.loader.exec_module(_stage9913)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
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


def duplicate_weighted_train_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    weighted = [json.loads(json.dumps(row)) for row in rows]
    target_train_rows = [
        row for row in rows
        if str(row.get("source_skill_area") or "") == TARGET_SKILL and str(row.get("split") or "") == "train"
    ]
    for duplicate_index in range(1, EXTRA_TRAIN_DUPLICATES + 1):
        for row in target_train_rows:
            clone = json.loads(json.dumps(row))
            clone["row_id"] = f"{row['row_id']}::train_weight_dup{duplicate_index}"
            clone["source_row_id"] = row.get("source_row_id") or row.get("row_id")
            clone["duplication_role"] = "edit_localization_train_weight"
            clone["duplication_index"] = duplicate_index
            anti = clone.get("anti_cheat") if isinstance(clone.get("anti_cheat"), dict) else {}
            anti["stage9916_train_only_weighted_replay"] = True
            clone["anti_cheat"] = anti
            weighted.append(clone)
    return weighted


def build_prepared_rows() -> tuple[list[dict[str, Any]], list[str]]:
    base_rows, failures = _stage9913.build_prepared_rows()
    if failures:
        return base_rows, failures
    return duplicate_weighted_train_rows(base_rows), []


def audit_compiled(prepared: list[dict[str, Any]], compile_card: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    base_rows, _ = _stage9913.build_prepared_rows()
    base_split_counts = Counter(str(row.get("split") or "") for row in base_rows)
    expected_loss_counts = Counter(str(row.get("expected_enabled_loss") or "") for row in prepared)
    actual_loss_counts = Counter({key: count for key, count in (compile_card.get("loss_counts") or {}).items() if count})
    if dict(actual_loss_counts) != dict(expected_loss_counts):
        failures.append("loss_counts_do_not_match_expected_single_surface_masks")
    if compile_card.get("gate_rejected_rows") != 0:
        failures.append("gate_rejected_rows_nonzero")
    if compile_card.get("locked_source_exclusion_rows") != 0:
        failures.append("locked_source_exclusion_rows_nonzero")
    if (compile_card.get("loss_counts") or {}).get("denoise_ce", 0) != 0 or (compile_card.get("loss_counts") or {}).get("runtime_reward", 0) != 0:
        failures.append("forbidden_loss_enabled")
    skill_counts = Counter(str(row.get("source_skill_area") or "") for row in prepared)
    split_counts = Counter(str(row.get("split") or "") for row in prepared)
    language_counts = Counter(str(row.get("language_family") or "") for row in prepared)
    weighted_rows = [
        row for row in prepared
        if str(row.get("source_skill_area") or "") == TARGET_SKILL and str(row.get("split") or "") == "train"
    ]
    if len(weighted_rows) != 16 * (1 + EXTRA_TRAIN_DUPLICATES):
        failures.append(f"unexpected_weighted_edit_train_rows:{len(weighted_rows)}")
    if split_counts.get("eval", 0) != base_split_counts.get("eval", 0) or split_counts.get("strict_eval", 0) != base_split_counts.get("strict_eval", 0):
        failures.append("eval_splits_changed")
    if skill_counts.get(TARGET_SKILL, 0) != 48 + (16 * EXTRA_TRAIN_DUPLICATES):
        failures.append(f"unexpected_weighted_edit_total:{skill_counts.get(TARGET_SKILL, 0)}")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(prepared),
        "skill_counts": dict(sorted(skill_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "expected_loss_counts": dict(sorted(expected_loss_counts.items())),
        "actual_loss_counts": dict(sorted(actual_loss_counts.items())),
        "edit_train_rows_after_weighting": len(weighted_rows),
        "compiler_card": compile_card,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    prepared, failures = build_prepared_rows()
    write_jsonl(PREPARED, prepared)
    locked_source_ids = load_locked_source_ids_from_exclusions(LOCKED_EXCLUSIONS)
    buckets, compile_card = compile_rows(
        prepared,
        allow_decoder=True,
        allow_denoise=False,
        allow_runtime=False,
        require_recovered_gates=True,
        locked_source_ids=locked_source_ids,
    )
    COMPILED_DIR.mkdir(parents=True, exist_ok=True)
    for objective, rows in buckets.items():
        write_jsonl(COMPILED_DIR / f"{objective}.jsonl", rows)
    write_json(COMPILED_DIR / "compile_card.json", compile_card)
    audit = audit_compiled(prepared, compile_card)
    failures.extend(audit["failures"])
    audit["passed"] = not failures
    audit["failures"] = failures
    write_json(AUDIT, audit)
    next_step = "Run a schedule-aware structured review on this weighted hardened package: edit localization now has doubled train pressure from the anti-cheat-safe opaque-choice packet while eval and strict-eval remain unchanged."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "failures": failures,
            "rows": audit["rows"],
            "skill_counts": audit["skill_counts"],
            "split_counts": audit["split_counts"],
            "language_counts": audit["language_counts"],
            "loss_counts": audit["actual_loss_counts"],
            "edit_train_rows_after_weighting": audit["edit_train_rows_after_weighting"],
        },
        "artifacts": {
            "prepared_manifest": str(PREPARED.relative_to(ROOT)),
            "compiled_dir": str(COMPILED_DIR.relative_to(ROOT)),
            "compile_card": str((COMPILED_DIR / "compile_card.json").relative_to(ROOT)),
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Built a hardened weighted successor to Stage9913: only the edit-localization train rows are duplicated, so the honest opaque-choice packet gets the same integrated train budget as the other structured heads without changing eval or strict-eval slices.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text("\n".join([
        "# Stage9916 V2.7 Hardened Edit Localization Weighted Compiler Refresh",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Skill counts: `{audit['skill_counts']}`",
        f"Split counts: `{audit['split_counts']}`",
        "",
        "This stage keeps the hardened opaque-choice edit-localization source but duplicates only its train split so integrated training pressure can rise without modifying eval packaging or reintroducing label-list leakage.",
        "",
        f"Next: {next_step}",
        "",
    ]) + "\n", encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "rows": audit["rows"],
        "skill_counts": audit["skill_counts"],
        "split_counts": audit["split_counts"],
        "loss_counts": audit["actual_loss_counts"],
        "failures": failures,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
