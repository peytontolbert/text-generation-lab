#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9719
NAME = "stage9719_multilingual_comparison_evidence_bundle_contract"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage9684_v27_multilingual_eval_acceptance_contract/v27_multilingual_eval_acceptance_contract.json"
SOURCE_LEDGER = ROOT / "runs/local/artifacts/stage9718_locked_multilingual_acceptance_evidence_ledger/locked_multilingual_acceptance_evidence_ledger.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "multilingual_comparison_evidence_bundle_contract.json"
TEMPLATES = OUT_DIR / "multilingual_comparison_evidence_bundle_templates.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_MULTILINGUAL_COMPARISON_EVIDENCE_BUNDLE_CONTRACT_STAGE9719.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

RUBRIC_SUBSKILLS = [
    "understands_user_intent",
    "uses_allowed_imports_only",
    "rejects_blocked_imports",
    "retrieves_source_evidence_when_needed",
    "binds_symbols_correctly",
    "localizes_edit_scope",
    "chooses_minimal_edit_operator",
    "creates_or_updates_tests_when_appropriate",
    "predicts_verifier_command",
    "interprets_verifier_failure",
    "repairs_or_abstains_safely",
    "keeps_patch_minimal",
    "avoids_broad_rewrites",
    "avoids_hallucinated_symbols",
    "avoids_internal_tokens",
    "produces_contentful_final_answer",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def required_evidence_for_mode(contract: dict[str, Any], mode: str) -> list[str]:
    mapping = contract.get("required_evidence_by_mode") or {}
    values = mapping.get(mode) if isinstance(mapping, dict) else []
    return [str(value) for value in values or []]


def build_template(record: dict[str, Any]) -> dict[str, Any]:
    mode = str(record.get("mode") or "")
    return {
        "cell_key": record.get("cell_key"),
        "task_pack_id": record.get("task_pack_id"),
        "source_id": record.get("source_id"),
        "mode": mode,
        "language_family": record.get("language_family"),
        "skill_area": record.get("skill_area"),
        "same_surface_comparison": {
            "present": False,
            "prompt_surface_hash_100m": None,
            "prompt_surface_hash_gemma12b": None,
            "score_100m": None,
            "score_gemma12b": None,
            "scoring_constraints_hash": None,
            "same_surface_verified": False,
            "hundred_m_beats_gemma12b": False,
        },
        "expert_maintainer_rubric": {
            "present": False,
            "rubric_version": "expert_maintainer_v1",
            "passed": False,
            "subskills": {name: None for name in RUBRIC_SUBSKILLS},
            "failure_trace_refs": [],
        },
        "anti_cheat_attachment": {
            "present": False,
            "stage9717_gate_passed": False,
            "passed": False,
            "anti_cheat_card_paths": [],
        },
        "evidence_artifacts": {
            key: None for key in record.get("required_evidence", [])
        },
        "closed_authority_confirmed": True,
        "claim_ready_candidate": False,
        "notes": ["template_only_do_not_mark_claim_ready_without_real_evidence"],
    }


def validate_bundle(bundle: dict[str, Any], record: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if bundle.get("cell_key") != record.get("cell_key"):
        failures.append("cell_key_mismatch")
    for key in ["task_pack_id", "source_id", "mode", "language_family", "skill_area"]:
        if bundle.get(key) != record.get(key):
            failures.append(f"record_identity_mismatch:{key}")
    same_surface = bundle.get("same_surface_comparison") if isinstance(bundle.get("same_surface_comparison"), dict) else {}
    rubric = bundle.get("expert_maintainer_rubric") if isinstance(bundle.get("expert_maintainer_rubric"), dict) else {}
    anti = bundle.get("anti_cheat_attachment") if isinstance(bundle.get("anti_cheat_attachment"), dict) else {}
    artifacts = bundle.get("evidence_artifacts") if isinstance(bundle.get("evidence_artifacts"), dict) else {}
    if same_surface.get("present") is not True:
        failures.append("same_surface_comparison_missing")
    if same_surface.get("prompt_surface_hash_100m") != same_surface.get("prompt_surface_hash_gemma12b"):
        failures.append("prompt_surface_hash_mismatch")
    if same_surface.get("same_surface_verified") is not True:
        failures.append("same_surface_not_verified")
    score_100m = same_surface.get("score_100m")
    score_gemma = same_surface.get("score_gemma12b")
    if not isinstance(score_100m, (int, float)) or not isinstance(score_gemma, (int, float)):
        failures.append("scores_missing")
    elif float(score_100m) <= float(score_gemma):
        failures.append("hundred_m_does_not_beat_gemma12b")
    if same_surface.get("hundred_m_beats_gemma12b") is not True:
        failures.append("bundle_not_marked_hundred_m_beats_gemma12b")
    if anti.get("present") is not True or anti.get("stage9717_gate_passed") is not True or anti.get("passed") is not True:
        failures.append("anti_cheat_attachment_not_passed")
    if not anti.get("anti_cheat_card_paths"):
        failures.append("anti_cheat_card_paths_missing")
    if rubric.get("present") is not True or rubric.get("passed") is not True:
        failures.append("expert_maintainer_rubric_not_passed")
    subskills = rubric.get("subskills") if isinstance(rubric.get("subskills"), dict) else {}
    missing_subskills = [name for name in RUBRIC_SUBSKILLS if subskills.get(name) is not True]
    if missing_subskills:
        failures.append("rubric_subskills_missing_or_failed")
    required = set(required_evidence_for_mode(contract, str(record.get("mode") or "")))
    provided = {key for key, value in artifacts.items() if value}
    missing_artifacts = sorted(required - provided)
    if missing_artifacts:
        failures.extend(f"missing_required_artifact:{key}" for key in missing_artifacts)
    if bundle.get("closed_authority_confirmed") is not True:
        failures.append("closed_authority_not_confirmed")
    return failures


def merge_bundle_into_record(bundle: dict[str, Any], record: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    failures = validate_bundle(bundle, record, contract)
    merged = dict(record)
    evidence = list(record.get("attached_evidence") or [])
    evidence.append({
        "kind": "comparison_evidence_bundle",
        "stage": STAGE,
        "bundle": bundle,
        "claim_sufficient": not failures,
    })
    merged["attached_evidence"] = evidence
    merged["claim_ready"] = not failures
    merged["claim_status"] = "claim_ready" if not failures else "blocked_missing_final_evidence"
    merged["missing_required_evidence"] = [] if not failures else list(record.get("missing_required_evidence") or [])
    if not failures:
        merged["blockers"] = []
    else:
        merged["blockers"] = sorted(set(list(record.get("blockers") or []) + failures))
    return merged


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
    contract = load_json(SOURCE_CONTRACT)
    ledger = load_json(SOURCE_LEDGER)
    records = ledger.get("records") if isinstance(ledger, dict) else []
    if not isinstance(records, list):
        records = []
    templates = [build_template(record) for record in records]
    write_jsonl(TEMPLATES, templates)
    contract_doc = {
        "stage": STAGE,
        "name": NAME,
        "required_identity_fields": ["cell_key", "task_pack_id", "source_id", "mode", "language_family", "skill_area"],
        "same_surface_required": True,
        "expert_rubric_subskills": RUBRIC_SUBSKILLS,
        "merge_rule": "claim_ready only if same-surface 100M>Gemma12B, expert rubric passed, anti-cheat attached and passed, required evidence artifacts present, and authority remains closed.",
        "required_evidence_by_mode": contract.get("required_evidence_by_mode"),
        "authority": dict(AUTHORITY_CLOSED),
    }
    CONTRACT.write_text(json.dumps(contract_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures: list[str] = []
    if len(templates) != 72:
        failures.append("template_count_not_72")
    mode_counts = Counter(str(row.get("mode") or "") for row in templates)
    language_counts = Counter(str(row.get("language_family") or "") for row in templates)
    skill_counts = Counter(str(row.get("skill_area") or "") for row in templates)
    if any(row.get("claim_ready_candidate") is not False for row in templates):
        failures.append("template_claim_ready_candidate_open")
    next_step = (
        "Populate Stage9719 bundles with real same-surface 100M-vs-Gemma results and expert-rubric outcomes, then "
        "merge them into Stage9718 records to advance cells from blocked to claim-ready."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "templates": len(templates),
            "mode_counts": dict(sorted(mode_counts.items())),
            "language_counts": dict(sorted(language_counts.items())),
            "skill_counts": dict(sorted(skill_counts.items())),
            "rubric_subskills": len(RUBRIC_SUBSKILLS),
            "failures": failures,
        },
        "artifacts": {
            "contract": str(CONTRACT.relative_to(ROOT)),
            "templates": str(TEMPLATES.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized the strict comparison evidence bundle contract and templates for all locked multilingual acceptance cells.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9719 Multilingual Comparison Evidence Bundle Contract",
        "",
        f"Passed: `{summary['passed']}`",
        f"Templates: `{summary['metrics']['templates']}`",
        f"Modes: `{summary['metrics']['mode_counts']}`",
        f"Languages: `{summary['metrics']['language_counts']}`",
        f"Skills: `{summary['metrics']['skill_counts']}`",
        "",
        "This stage defines the per-cell bundle required to move a Stage9718 acceptance record to claim-ready. The bundle must prove same-surface parity, 100M > Gemma-12B, expert maintainer rubric pass, anti-cheat pass, and required evidence artifact coverage.",
        "",
        "No Gemma, harness, runtime, scoring, training, source/body emission, checkpoint export, or promotion is authorized.",
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
        "templates": len(templates),
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
