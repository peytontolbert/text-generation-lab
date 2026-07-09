#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from curriculum_compiler import LOSS_KEYS, compile_rows
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
    from gate_status_contract import passed_gate_status
    from golden_locked_eval_suite import load_locked_source_ids_from_exclusions
except ModuleNotFoundError:
    from scripts.curriculum_compiler import LOSS_KEYS, compile_rows  # type: ignore
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from scripts.gate_status_contract import passed_gate_status  # type: ignore
    from scripts.golden_locked_eval_suite import load_locked_source_ids_from_exclusions  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9693
NAME = "stage9693_locked_guarded_source_backed_multisurface_compiler_refresh"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9692_v27_source_backed_multilingual_training_surface_reconciliation.json"
LOCKED_EXCLUSIONS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_source_exclusions.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PREPARED = OUT_DIR / "multisurface_prepared_rows.jsonl"
COMPILED_DIR = OUT_DIR / "compiled"
AUDIT = OUT_DIR / "multisurface_compiler_refresh_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LOCKED_GUARDED_SOURCE_BACKED_MULTISURFACE_COMPILER_REFRESH_STAGE9693.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCES = {
    "symbol_binding": {
        "path": ROOT / "runs/local/artifacts/stage8676_source_backed_symbol_binding_shortcut_repair_manifest/source_backed_symbol_binding_shortcut_repair_manifest.jsonl",
        "target_loss": "symbol_binding_ce",
        "source_audit": "runs/summaries/stage8677_source_backed_symbol_binding_shortcut_repair_manifest_audit.json",
    },
    "edit_localization": {
        "path": ROOT / "runs/local/artifacts/stage8765_source_backed_edit_localization_candidate_manifest/source_backed_edit_localization_candidate_manifest.jsonl",
        "target_loss": "edit_localization_ce",
        "source_audit": "runs/summaries/stage8766_source_backed_edit_localization_candidate_audit.json",
    },
    "patch_operator_selection": {
        "path": ROOT / "runs/local/artifacts/stage8774_source_backed_patch_operator_candidate_manifest/source_backed_patch_operator_candidate_manifest.jsonl",
        "target_loss": "patch_operator_ce",
        "source_audit": "runs/summaries/stage8775_source_backed_patch_operator_candidate_audit.json",
    },
    "verifier_failure_repair_or_abstain": {
        "path": ROOT / "runs/local/artifacts/stage8788_source_backed_verifier_repair_candidate_manifest/source_backed_verifier_repair_candidate_manifest.jsonl",
        "target_loss": "verifier_repair_ce",
        "source_audit": "runs/summaries/stage8789_source_backed_verifier_repair_candidate_audit.json",
    },
    "bounded_argument_rendering": {
        "path": ROOT / "runs/local/artifacts/stage9240_source_backed_multilang_bounded_decoder_tiny_package/source_backed_multilang_bounded_decoder_tiny_manifest.jsonl",
        "target_loss": "decoder_ce",
        "source_audit": "runs/summaries/stage9241_multilang_source_backed_target_100m_contract_only_preflight.json",
    },
}

STRUCTURED_LOSSES = [
    "surface_role_ce",
    "repair_surface_ce",
    "build_mode_ce",
    "allowed_import_policy_ce",
    "blocked_import_policy_ce",
    "repo_dependency_policy_ce",
    "action_sequence_ce",
    "file_plan_ce",
    "symbol_binding_ce",
    "edit_localization_ce",
    "patch_operator_ce",
    "verifier_repair_ce",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def split_name(value: Any) -> str:
    return "strict_eval" if str(value or "") == "strict" else str(value or "train")


def language_family(row: dict[str, Any]) -> str:
    value = row.get("language_family") or row.get("source_language")
    if not value:
        state = row.get("corrupted_state") if isinstance(row.get("corrupted_state"), dict) else {}
        value = state.get("language")
    mapping = {"typescript": "web_js_ts_html", "cpp": "c_cpp", "c_cpp": "c_cpp", "python": "python", "rust": "rust", "web_js_ts_html": "web_js_ts_html"}
    return mapping.get(str(value or "unknown"), str(value or "unknown"))


def normalize_row(row: dict[str, Any], skill: str, target_loss: str) -> dict[str, Any]:
    out = dict(row)
    out["row_id"] = f"stage9693_{skill}_{row.get('row_id')}"
    out["source_row_id"] = row.get("row_id")
    out["source_skill_area"] = skill
    out["split"] = split_name(row.get("split"))
    out["language_family"] = language_family(row)
    out["authority"] = dict(AUTHORITY_CLOSED)
    out["gate_status"] = passed_gate_status()
    out["gate_status_materialized_from"] = SOURCES[skill]["source_audit"]
    out["locked_guard_refresh_stage"] = NAME
    if target_loss == "decoder_ce":
        out["route"] = "KEEP_BOUNDED_DECODER"
        out["disable_losses"] = []
    else:
        out["route"] = "KEEP_STRUCTURED"
        out["disable_losses"] = [loss for loss in STRUCTURED_LOSSES if loss != target_loss]
    out["expected_enabled_loss"] = target_loss
    out.setdefault("anti_cheat", {})
    out["anti_cheat"] = {
        **(out.get("anti_cheat") if isinstance(out.get("anti_cheat"), dict) else {}),
        "stage9693_locked_source_guard_required": True,
        "stage9693_gate_status_materialized_from_audit": True,
        "stage9693_loss_mask_single_surface": True,
    }
    return out


def build_prepared_rows() -> tuple[list[dict[str, Any]], list[str]]:
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    source_summary = load_json(SOURCE_SUMMARY)
    if source_summary.get("passed") is not True:
        failures.append("stage9692_not_passed")
    for skill, spec in SOURCES.items():
        path = spec["path"]
        audit_path = ROOT / str(spec["source_audit"])
        audit = load_json(audit_path)
        if not path.exists():
            failures.append(f"missing_source_manifest:{skill}")
            continue
        if audit.get("passed") is not True:
            failures.append(f"source_audit_not_passed:{skill}")
            continue
        for row in read_jsonl(path):
            rows.append(normalize_row(row, skill, str(spec["target_loss"])))
    return rows, failures


def audit_compiled(prepared: list[dict[str, Any]], card: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    expected_loss_counts = Counter(row["expected_enabled_loss"] for row in prepared)
    actual_loss_counts = Counter({key: count for key, count in (card.get("loss_counts") or {}).items() if count})
    if dict(actual_loss_counts) != dict(expected_loss_counts):
        failures.append("loss_counts_do_not_match_expected_single_surface_masks")
    if card.get("gate_rejected_rows") != 0:
        failures.append("gate_rejected_rows_nonzero")
    if card.get("locked_source_exclusion_rows") != 0:
        failures.append("locked_source_exclusion_rows_nonzero")
    if (card.get("loss_counts") or {}).get("denoise_ce", 0) != 0 or (card.get("loss_counts") or {}).get("runtime_reward", 0) != 0:
        failures.append("forbidden_loss_enabled")
    route_counts = card.get("route_counts") or {}
    if route_counts.get("NEEDS_HUMAN_REVIEW", 0) != 0:
        failures.append("human_review_rows_after_refresh")
    authority_rows = sum(int(any((row.get("authority") or {}).values())) for row in prepared)
    if authority_rows:
        failures.append("authority_rows_present")
    split_counts = Counter(row.get("split") for row in prepared)
    language_counts = Counter(row.get("language_family") for row in prepared)
    skill_counts = Counter(row.get("source_skill_area") for row in prepared)
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(prepared),
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "skill_counts": dict(sorted(skill_counts.items())),
        "expected_loss_counts": dict(sorted(expected_loss_counts.items())),
        "actual_loss_counts": dict(sorted(actual_loss_counts.items())),
        "compiler_card": card,
        "authority_rows": authority_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


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
    (COMPILED_DIR / "compile_card.json").write_text(json.dumps(compile_card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit = audit_compiled(prepared, compile_card)
    failures.extend(audit["failures"])
    audit["passed"] = not failures
    audit["failures"] = failures
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Run Stage9694 target_100m contract-only preflight on the Stage9693 compiled multisurface package; do not execute training until it proves loss-mask enforcement and telemetry completeness."
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
            "language_counts": audit["language_counts"],
            "split_counts": audit["split_counts"],
            "loss_counts": audit["actual_loss_counts"],
            "gate_rejected_rows": compile_card.get("gate_rejected_rows"),
            "locked_source_exclusion_rows": compile_card.get("locked_source_exclusion_rows"),
            "training_execution_authorized_next": False,
            "model_execution_authorized_next": False,
        },
        "artifacts": {
            "prepared_manifest": str(PREPARED.relative_to(ROOT)),
            "compiled_dir": str(COMPILED_DIR.relative_to(ROOT)),
            "compile_card": str((COMPILED_DIR / "compile_card.json").relative_to(ROOT)),
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized a locked-guarded source-backed multisurface compiler refresh with single-surface loss masks. This authorizes contract-only preflight, not training execution.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9693 Locked-Guarded Source-Backed Multisurface Compiler Refresh",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Skill counts: `{audit['skill_counts']}`",
        f"Loss counts: `{audit['actual_loss_counts']}`",
        f"Gate rejected rows: `{compile_card.get('gate_rejected_rows')}`",
        f"Locked-source rejected rows: `{compile_card.get('locked_source_exclusion_rows')}`",
        "",
        "This stage refreshes recovered source-backed candidate surfaces under the locked eval exclusion guard and emits one intended loss family per row. It does not run the model or authorize training execution.",
        "",
        "No runtime, source/body emission, Gemma, harness, scoring, model execution, checkpoint export, denoise execution, or promotion is authorized.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "failures": failures,
        "rows": audit["rows"],
        "loss_counts": audit["actual_loss_counts"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
