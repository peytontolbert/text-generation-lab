#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11436
NAME = "stage11436_full_coverage_semantic_candidate_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "full_coverage_semantic_candidate_package.json"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

BASE = ARTIFACTS / "stage11429_selected_test_rust_support_package"
RESIDUAL = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
INPUTS = {
    "train": BASE / "agentkernel_lite_encdec_train.jsonl",
    "validation": BASE / "agentkernel_lite_encdec_validation.jsonl",
    "strict_eval": BASE / "agentkernel_lite_encdec_strict_eval.jsonl",
    "stress_eval": BASE / "agentkernel_lite_encdec_stress_eval.jsonl",
    "residual_bank": RESIDUAL,
}
OUTPUTS = {
    "train": OUT_DIR / "agentkernel_lite_encdec_train.jsonl",
    "validation": OUT_DIR / "agentkernel_lite_encdec_validation.jsonl",
    "strict_eval": OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl",
    "stress_eval": OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl",
    "residual_bank": OUT_DIR / "semantic_candidate_residual_bank.jsonl",
    "row_audit": OUT_DIR / "semantic_candidate_row_audit.jsonl",
}

EVIDENCE_ROLES = {
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
    "external_analogue_reference",
    "algorithmic_background_reference",
    "background_context",
}
ROLE_ALIASES = {
    "candidate": "candidate_change_surface",
    "candidate surface": "candidate_change_surface",
    "changed file": "candidate_change_surface",
    "changed-file": "candidate_change_surface",
    "verifier": "verifier_and_test_constraint",
    "selected test": "verifier_and_test_constraint",
    "test constraint": "verifier_and_test_constraint",
    "symptom": "symptom_or_call_path_analogue",
    "call path": "symptom_or_call_path_analogue",
    "trace": "symptom_or_call_path_analogue",
    "usage": "nearby_definition_or_usage_context",
    "definition": "nearby_definition_or_usage_context",
    "external": "external_analogue_reference",
    "analogue": "external_analogue_reference",
    "background": "algorithmic_background_reference",
}
TRANSITIONS = ("FAIL_TO_PASS", "PASS_TO_PASS", "FAIL_TO_FAIL", "NOT_EXERCISED", "INSUFFICIENT_EVIDENCE", "NEEDS_VERIFIER")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def root_key(row: dict[str, Any]) -> str:
    for key in ("root_id", "source_root_id", "root_lineage_key", "source_bundle_id"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(row.get("row_id") or "")


def task_type(row: dict[str, Any]) -> str:
    value = row.get("task_type") or row.get("perspective")
    if isinstance(value, str) and value.strip():
        return value.strip()
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    marker = "Perspective:"
    if marker in prompt:
        return prompt.split(marker, 1)[1].splitlines()[0].strip()
    return "unknown"


def target_label(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    for value in (
        row.get("bounded_choice_target_label"),
        target.get("bounded_choice_target_label"),
        row.get("target_text"),
        target.get("target_text"),
        row.get("decoder_text"),
        target.get("decoder_text"),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def gold_value(row: dict[str, Any]) -> str:
    sps = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    for value in (
        sps.get("gold_value"),
        row.get("semantic_target_value"),
        row.get("gold_value"),
        target.get("semantic_target_value"),
        target.get("gold_value"),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    label = target_label(row)
    for option in sps.get("opaque_options") or []:
        if isinstance(option, dict) and str(option.get("label") or "").strip() == label:
            return str(option.get("value") or "").strip()
    return ""


def transition_from_value(value: str) -> str:
    upper = str(value).upper()
    for transition in TRANSITIONS:
        if transition in upper:
            return transition
    return "NONE"


def evidence_role_from_value(value: str, task: str, option: dict[str, Any] | None = None) -> str:
    metadata = option.get("semantic_candidate") if isinstance(option, dict) and isinstance(option.get("semantic_candidate"), dict) else {}
    explicit = str(metadata.get("evidence_role") or "").strip()
    if explicit:
        return explicit
    raw = str(value or "").strip()
    prefix = raw.split("|", 1)[0].strip()
    if prefix in EVIDENCE_ROLES:
        return prefix
    lowered = re.sub(r"[_\-]+", " ", raw.lower())
    for needle, role in ROLE_ALIASES.items():
        if needle in lowered:
            return role
    if "evidence" in task or task == "evidence_citation":
        return "candidate_value_surface"
    if "verifier" in task or transition_from_value(raw) != "NONE":
        return "verifier_and_test_constraint"
    if "abstain" in raw.upper() or "INSUFFICIENT" in raw.upper():
        return "insufficient_evidence_option"
    return "candidate_value_surface"


def test_id_from_value(value: str) -> str:
    raw = str(value or "").strip()
    if "|" in raw:
        return raw.split("|", 1)[0].strip()
    match = re.search(r"(?:test|tests?)[A-Za-z0-9_./:-]+", raw)
    return match.group(0) if match else ""


def candidate_value_family(role: str, transition: str, task: str) -> str:
    if transition != "NONE" or "verifier" in task:
        return "verifier_transition"
    if role in EVIDENCE_ROLES or "evidence" in task:
        return "evidence_role_or_item"
    if role == "insufficient_evidence_option":
        return "abstention_option"
    return "generic_candidate"


def normalize_option(row: dict[str, Any], option: dict[str, Any], idx: int) -> dict[str, Any]:
    out = dict(option)
    value = str(out.get("value") or out.get("label") or "").strip()
    task = task_type(row)
    transition = transition_from_value(value)
    role = evidence_role_from_value(value, task, option)
    existing = out.get("semantic_candidate") if isinstance(out.get("semantic_candidate"), dict) else {}
    semantic = dict(existing)
    semantic.update(
        {
            "schema_version": "stage11436_full_coverage_semantic_candidate_v1",
            "option_index": idx,
            "candidate_label": str(out.get("label") or "").strip(),
            "candidate_value_family": candidate_value_family(role, transition, task),
            "task_type": task,
            "evidence_role": role,
            "verifier_transition": transition,
            "test_id": str(existing.get("test_id") or test_id_from_value(value)),
            "value_token_count_proxy": len(value.replace("|", " ").split()),
        }
    )
    out["semantic_candidate"] = semantic
    return out


def normalize_row(row: dict[str, Any], split: str) -> tuple[dict[str, Any], dict[str, Any]]:
    out = dict(row)
    out["semantic_candidate_schema_version"] = "stage11436_full_coverage_semantic_candidate_v1"
    out["source_split_before_stage11436"] = split
    sps = dict(out.get("standalone_projection_source") or {})
    options = [opt for opt in (sps.get("opaque_options") or []) if isinstance(opt, dict)]
    normalized = [normalize_option(out, option, idx) for idx, option in enumerate(options)]
    sps["opaque_options"] = normalized
    sps["option_semantic_schema_version"] = "stage11436_full_coverage_semantic_candidate_v1"
    sps["option_semantic_records"] = [opt.get("semantic_candidate") for opt in normalized]
    out["standalone_projection_source"] = sps

    label = target_label(out)
    option_labels = [str(opt.get("label") or "").strip() for opt in normalized]
    option_values = [str(opt.get("value") or "").strip() for opt in normalized]
    gold = gold_value(out)
    roles = [str((opt.get("semantic_candidate") or {}).get("evidence_role") or "") for opt in normalized]
    transitions = [str((opt.get("semantic_candidate") or {}).get("verifier_transition") or "") for opt in normalized]
    blockers: list[str] = []
    if not normalized:
        blockers.append("missing_opaque_options")
    if len(normalized) <= 1:
        blockers.append("singleton_or_empty_options")
    if not label:
        blockers.append("missing_target_label")
    if label and label not in option_labels:
        blockers.append("target_label_not_in_options")
    if normalized and not all(isinstance(opt.get("semantic_candidate"), dict) for opt in normalized):
        blockers.append("semantic_metadata_incomplete")
    if task_type(out) == "evidence_citation" and len(set(roles)) < min(2, len(roles)):
        blockers.append("evidence_role_not_contrastive")
    audit = {
        "row_id": out.get("row_id"),
        "split": split,
        "language_family": out.get("language_family") or out.get("language"),
        "repo_family": out.get("repo_family"),
        "root_id": root_key(out),
        "task_type": task_type(out),
        "target_label": label,
        "gold_value": gold,
        "option_count": len(normalized),
        "target_in_options": bool(label and label in option_labels),
        "gold_value_in_options": bool(gold and gold in option_values),
        "semantic_metadata_complete": bool(normalized) and all(isinstance(opt.get("semantic_candidate"), dict) for opt in normalized),
        "evidence_roles": sorted(set(role for role in roles if role)),
        "verifier_transitions": sorted(set(t for t in transitions if t and t != "NONE")),
        "blockers": blockers,
        "admitted_for_semantic_candidate_probe": not blockers,
    }
    return out, audit


def count(rows: list[dict[str, Any]], audits: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "roots": len({root_key(row) for row in rows}),
        "by_language": dict(sorted(Counter(str(row.get("language_family") or row.get("language") or "unknown") for row in rows).items())),
        "by_task": dict(sorted(Counter(task_type(row) for row in rows).items())),
        "blocked_rows": sum(1 for audit in audits if audit["blockers"]),
        "blockers": dict(sorted(Counter(blocker for audit in audits for blocker in audit["blockers"]).items())),
        "singleton_rows": sum(1 for audit in audits if "singleton_or_empty_options" in audit["blockers"]),
        "semantic_metadata_complete_rows": sum(1 for audit in audits if audit["semantic_metadata_complete"]),
    }


def main() -> None:
    all_audits: list[dict[str, Any]] = []
    outputs: dict[str, str] = {}
    split_counts: dict[str, Any] = {}
    normalized_by_split: dict[str, list[dict[str, Any]]] = {}
    audits_by_split: dict[str, list[dict[str, Any]]] = {}
    for split, path in INPUTS.items():
        rows = load_jsonl(path)
        normalized_rows: list[dict[str, Any]] = []
        split_audits: list[dict[str, Any]] = []
        for row in rows:
            normalized, audit = normalize_row(row, split)
            normalized_rows.append(normalized)
            split_audits.append(audit)
        normalized_by_split[split] = normalized_rows
        audits_by_split[split] = split_audits
        all_audits.extend(split_audits)
        write_jsonl(OUTPUTS[split], normalized_rows)
        outputs[split] = rel(OUTPUTS[split])
        split_counts[split] = count(normalized_rows, split_audits)
    write_jsonl(OUTPUTS["row_audit"], all_audits)
    outputs["row_audit"] = rel(OUTPUTS["row_audit"])

    strict_blockers = [audit for audit in audits_by_split.get("strict_eval", []) if audit["blockers"]]
    residual_blockers = [audit for audit in audits_by_split.get("residual_bank", []) if audit["blockers"]]
    train_blockers = [audit for audit in audits_by_split.get("train", []) if audit["blockers"]]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "semantic_candidate_schema_materialized_but_probe_requires_blocker_cleanup",
        "claim_scope": "schema/objective readiness only; no model score or promotion claim",
        "inputs": {key: rel(value) for key, value in INPUTS.items()},
        "outputs": outputs,
        "split_counts": split_counts,
        "gates": {
            "all_optioned_rows_have_semantic_metadata": all(audit["semantic_metadata_complete"] or "missing_opaque_options" in audit["blockers"] for audit in all_audits),
            "strict_has_no_blocked_rows": len(strict_blockers) == 0,
            "residual_has_no_blocked_rows": len(residual_blockers) == 0,
            "train_has_no_blocked_rows": len(train_blockers) == 0,
            "semantic_candidate_probe_ready": len(strict_blockers) == 0 and len(residual_blockers) == 0 and len(train_blockers) == 0,
        },
        "blocked_examples": {
            "strict_eval": strict_blockers[:20],
            "residual_bank": residual_blockers[:20],
            "train": train_blockers[:20],
        },
        "decision_basis": [
            "Stage11434 showed scorer promotion must require full row coverage, not scored-row-only accuracy.",
            "This package adds per-option semantic_candidate metadata to current Stage11429 rows and the residual bank.",
            "A real semantic candidate scorer probe should not run until blocked train/strict/residual rows are cleaned or quarantined.",
        ],
        "recommended_next_action": "quarantine singleton/missing-option rows from strict/residual and build the semantic-candidate-head probe only on full-coverage rows, while separately reporting removed-row impact",
    }
    write_json(SUMMARY_JSON, summary)
    write_json(RUN_SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
