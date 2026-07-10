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
STAGE = 9717
NAME = "stage9717_locked_multilingual_eval_hacking_audit"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage9684_v27_multilingual_eval_acceptance_contract/v27_multilingual_eval_acceptance_contract.json"
SOURCE_PACKS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_multilingual_task_pack_skeleton.json"
SOURCE_EXCLUSIONS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_source_exclusions.jsonl"
SOURCE_VALIDATION = ROOT / "runs/local/artifacts/stage9686_golden_locked_eval_suite_validation/v27_golden_locked_eval_suite_validation.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "locked_multilingual_eval_hacking_audit.json"
CHALLENGE_MATRIX = OUT_DIR / "locked_multilingual_eval_hacking_challenge_matrix.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_LOCKED_MULTILINGUAL_EVAL_HACKING_AUDIT_STAGE9717.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

CHALLENGE_REQUIREMENTS = {
    "hidden_reference_materialization": [
        "hidden_reference_never_train_eligible",
        "split_semantic_overlap_zero_or_quarantined",
        "duplicate_semantic_key_zero_or_quarantined",
    ],
    "target_and_teacher_leakage": [
        "target_text_absent_from_model_input",
        "runtime_and_gemma_outputs_not_ground_truth_without_authority",
    ],
    "label_proxy_shortcuts": [
        "label_coded_ids_rejected",
        "surface_marker_shortcut_baseline_below_ceiling",
        "requested_output_type_shortcut_baseline_below_ceiling",
    ],
    "metadata_and_graph_shortcuts": [
        "metadata_only_baseline_below_ceiling",
        "graph_degree_baseline_below_ceiling",
        "query_node_id_baseline_below_ceiling",
    ],
    "generation_quality_collapse": [
        "internal_token_leak_zero",
        "short_junk_zero",
        "repetition_guard_passed",
        "long_target_budget_gate_enforced",
    ],
    "cross_model_surface_fairness": [
        "same_harness_prompt_surface_for_100m_and_gemma",
    ],
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def expected_cell_keys(contract: dict[str, Any]) -> set[str]:
    modes = [str(value) for value in contract.get("eval_modes_required") or []]
    languages = [str(value) for value in contract.get("languages_required") or []]
    skills = [str(value) for value in contract.get("maintainer_skill_areas_required") or []]
    return {f"{mode}::{language}::{skill}" for mode in modes for language in languages for skill in skills}


def pack_cell_key(pack: dict[str, Any]) -> str:
    return "::".join([
        str(pack.get("mode") or ""),
        str(pack.get("language_family") or ""),
        str(pack.get("skill_area") or ""),
    ])


def expected_mode_evidence(contract: dict[str, Any], mode: str) -> list[str]:
    required = contract.get("required_evidence_by_mode") or {}
    values = required.get(mode) if isinstance(required, dict) else []
    return [str(value) for value in values or []]


def challenge_matrix(requirements: list[str]) -> dict[str, Any]:
    reqs = set(str(value) for value in requirements)
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    for challenge, needed in CHALLENGE_REQUIREMENTS.items():
        missing = sorted(req for req in needed if req not in reqs)
        passed = not missing
        if not passed:
            failures.append(f"missing_challenge_requirements:{challenge}")
        records.append({
            "challenge_family": challenge,
            "required_requirements": needed,
            "missing_requirements": missing,
            "passed": passed,
        })
    return {
        "passed": not failures,
        "failures": failures,
        "records": records,
        "covered_challenge_families": sum(int(record["passed"]) for record in records),
        "total_challenge_families": len(records),
    }


def audit_suite(
    contract: dict[str, Any],
    packs: list[dict[str, Any]],
    exclusions: list[dict[str, Any]],
    validation: dict[str, Any],
) -> dict[str, Any]:
    failures: list[str] = []
    anti_cheat_requirements = [str(value) for value in contract.get("anti_cheat_requirements") or []]
    expected_cells = expected_cell_keys(contract)
    pack_cells = [pack_cell_key(pack) for pack in packs]
    pack_cell_counts = Counter(pack_cells)
    missing_cells = sorted(expected_cells - set(pack_cells))
    duplicate_cells = sorted(cell for cell, count in pack_cell_counts.items() if count > 1)
    unexpected_cells = sorted(set(pack_cells) - expected_cells)
    if missing_cells:
        failures.append("missing_acceptance_cells")
    if duplicate_cells:
        failures.append("duplicate_acceptance_cells")
    if unexpected_cells:
        failures.append("unexpected_acceptance_cells")

    pack_ids = [str(pack.get("task_pack_id") or "") for pack in packs]
    source_ids = [str(pack.get("source_id") or "") for pack in packs]
    lineage_hashes = [str(pack.get("lineage_hash") or "") for pack in packs]
    if len(set(pack_ids)) != len(pack_ids):
        failures.append("duplicate_task_pack_ids")
    if len(set(source_ids)) != len(source_ids):
        failures.append("duplicate_source_ids")
    if len(set(lineage_hashes)) != len(lineage_hashes):
        failures.append("duplicate_lineage_hashes")

    required_reqs = set(anti_cheat_requirements)
    bad_req_packs: list[str] = []
    bad_evidence_packs: list[str] = []
    bad_tag_packs: list[str] = []
    bad_threshold_packs: list[str] = []
    bad_train_flags: list[str] = []
    authority_rows: list[str] = []
    for pack in packs:
        pack_id = str(pack.get("task_pack_id") or pack.get("source_id") or "unknown")
        pack_reqs = set(str(value) for value in pack.get("anti_cheat_requirements") or [])
        if pack_reqs != required_reqs:
            bad_req_packs.append(pack_id)
        if [str(value) for value in pack.get("required_evidence") or []] != expected_mode_evidence(contract, str(pack.get("mode") or "")):
            bad_evidence_packs.append(pack_id)
        tags = {str(value) for value in pack.get("slice_tags") or []}
        expected_tags = {
            "v27",
            "expert_maintainer",
            str(pack.get("mode") or ""),
            str(pack.get("language_family") or ""),
            str(pack.get("skill_area") or ""),
        }
        if not expected_tags.issubset(tags):
            bad_tag_packs.append(pack_id)
        thresholds = pack.get("thresholds") if isinstance(pack.get("thresholds"), dict) else {}
        if thresholds.get("must_beat_gemma12b_same_surface") is not True or thresholds.get("anti_cheat_must_pass") is not True or thresholds.get("expert_rubric_must_pass") is not True:
            bad_threshold_packs.append(pack_id)
        if pack.get("train_eligible") is not False or pack.get("promotion_only") is not True or pack.get("blocked_training_reason") != "v27_locked_eval_pack_never_train_eligible":
            bad_train_flags.append(pack_id)
        if any((pack.get("authority") or {}).values()):
            authority_rows.append(pack_id)
    if bad_req_packs:
        failures.append("pack_missing_anti_cheat_requirements")
    if bad_evidence_packs:
        failures.append("pack_required_evidence_mismatch")
    if bad_tag_packs:
        failures.append("pack_slice_tags_incomplete")
    if bad_threshold_packs:
        failures.append("pack_thresholds_incomplete")
    if bad_train_flags:
        failures.append("pack_train_flags_invalid")
    if authority_rows:
        failures.append("authority_rows_present")

    exclusion_source_ids = [str(row.get("source_id") or "") for row in exclusions if row.get("blocked_from_training") is True]
    if set(exclusion_source_ids) != set(source_ids):
        failures.append("locked_exclusion_source_ids_do_not_match_packs")
    bad_exclusions = [
        row for row in exclusions
        if row.get("blocked_from_training") is not True
        or row.get("reason") != "locked_eval_source_never_mined_into_training"
        or not row.get("task_pack_id")
        or not row.get("source_id")
        or not row.get("lineage_hash")
    ]
    if bad_exclusions:
        failures.append("bad_exclusion_rows")

    mode_counts = Counter(str(pack.get("mode") or "" ) for pack in packs)
    language_counts = Counter(str(pack.get("language_family") or "" ) for pack in packs)
    skill_counts = Counter(str(pack.get("skill_area") or "" ) for pack in packs)
    expected_mode_count = len(contract.get("languages_required") or []) * len(contract.get("maintainer_skill_areas_required") or [])
    expected_language_count = len(contract.get("eval_modes_required") or []) * len(contract.get("maintainer_skill_areas_required") or [])
    expected_skill_count = len(contract.get("eval_modes_required") or []) * len(contract.get("languages_required") or [])
    if any(count != expected_mode_count for count in mode_counts.values()):
        failures.append("mode_counts_unbalanced")
    if any(count != expected_language_count for count in language_counts.values()):
        failures.append("language_counts_unbalanced")
    if any(count != expected_skill_count for count in skill_counts.values()):
        failures.append("skill_counts_unbalanced")

    validation_metrics = validation.get("metrics") if isinstance(validation.get("metrics"), dict) else {}
    if validation.get("passed") is not True:
        failures.append("stage9686_validation_not_passed")
    if validation_metrics.get("packs") != len(packs):
        failures.append("validation_pack_count_mismatch")
    if validation_metrics.get("train_eligible_packs") != 0:
        failures.append("validation_train_eligible_nonzero")

    challenge = challenge_matrix(anti_cheat_requirements)
    failures.extend(challenge["failures"])
    return {
        "passed": not failures,
        "failures": failures,
        "packs": len(packs),
        "expected_cells": len(expected_cells),
        "missing_cells": missing_cells,
        "duplicate_cells": duplicate_cells,
        "unexpected_cells": unexpected_cells,
        "mode_counts": dict(sorted(mode_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "skill_counts": dict(sorted(skill_counts.items())),
        "bad_requirement_packs": bad_req_packs,
        "bad_evidence_packs": bad_evidence_packs,
        "bad_tag_packs": bad_tag_packs,
        "bad_threshold_packs": bad_threshold_packs,
        "bad_train_flag_packs": bad_train_flags,
        "authority_rows": authority_rows,
        "bad_exclusion_rows": bad_exclusions,
        "challenge_matrix": challenge,
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

    contract = load_json(SOURCE_CONTRACT)
    suite = load_json(SOURCE_PACKS)
    exclusions = load_jsonl(SOURCE_EXCLUSIONS)
    validation = load_json(SOURCE_VALIDATION)
    packs = suite.get("benchmark_packs") if isinstance(suite, dict) else []
    if not isinstance(packs, list):
        packs = []

    audit = audit_suite(contract, packs, exclusions, validation)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    CHALLENGE_MATRIX.write_text(json.dumps(audit["challenge_matrix"], indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = (
        "Use the Stage9717 locked anti-eval-hacking matrix as the required acceptance gate for any future "
        "Gemma-vs-100M standalone or harness comparison, and attach per-cell evidence only after keeping "
        "these packs excluded from training."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "packs": audit["packs"],
            "expected_cells": audit["expected_cells"],
            "missing_cells": len(audit["missing_cells"]),
            "duplicate_cells": len(audit["duplicate_cells"]),
            "unexpected_cells": len(audit["unexpected_cells"]),
            "challenge_families_covered": audit["challenge_matrix"]["covered_challenge_families"],
            "challenge_families_total": audit["challenge_matrix"]["total_challenge_families"],
            "authority_rows": len(audit["authority_rows"]),
            "bad_requirement_packs": len(audit["bad_requirement_packs"]),
            "bad_evidence_packs": len(audit["bad_evidence_packs"]),
            "bad_train_flag_packs": len(audit["bad_train_flag_packs"]),
            "bad_exclusion_rows": len(audit["bad_exclusion_rows"]),
        },
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "challenge_matrix": str(CHALLENGE_MATRIX.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Audited the locked multilingual expert-maintainer eval packs for coverage, train exclusion, and anti-eval-hacking challenge completeness.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9717 Locked Multilingual Eval Hacking Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Packs: `{audit['packs']}`",
        f"Expected cells: `{audit['expected_cells']}`",
        f"Mode counts: `{audit['mode_counts']}`",
        f"Language counts: `{audit['language_counts']}`",
        f"Skill counts: `{audit['skill_counts']}`",
        f"Challenge families covered: `{audit['challenge_matrix']['covered_challenge_families']}` / `{audit['challenge_matrix']['total_challenge_families']}`",
        "",
        "This stage checks that locked multilingual expert-maintainer packs cover the full language x mode x skill grid, stay excluded from training, and carry explicit anti-eval-hacking challenge coverage.",
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
        "failures": audit["failures"],
        "packs": audit["packs"],
        "challenge_families_covered": audit["challenge_matrix"]["covered_challenge_families"],
        "challenge_families_total": audit["challenge_matrix"]["total_challenge_families"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
