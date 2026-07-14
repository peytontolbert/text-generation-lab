#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11233
NAME = "stage11233_grouped_evidence_item_fact_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "grouped_evidence_item_fact_package.json"
TRAIN_ROWS_JSONL = OUT_DIR / "grouped_evidence_item_fact_train_rows.jsonl"
DIAG_ROWS_JSONL = OUT_DIR / "grouped_evidence_item_fact_diagnostic_rows.jsonl"

SUPPORT_ROWS = ARTIFACTS / "stage11205_fresh_verifier_constraint_evidence_support/admitted_fresh_verifier_constraint_evidence_rows.jsonl"
RESIDUAL_ROWS = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"

ROLE_PREFIX_RE = re.compile(
    r"^(candidate_change_surface|verifier_and_test_constraint|symptom_or_call_path_analogue|nearby_definition_or_usage_context|external_analogue_reference|algorithmic_background_reference)\s*(?:\[[^\]]*\])?\s*:\s*",
    re.IGNORECASE,
)
ROLE_NAMES = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
    "external_analogue_reference",
    "algorithmic_background_reference",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("row_id") or "")


def prompt_without_options(row: dict[str, Any]) -> str:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "").strip()
    return prompt.split("\nOptions:\n", 1)[0].rstrip()


def evidence_fact(row: dict[str, Any], role: str) -> str:
    projection = row.get("standalone_projection_source") or {}
    facts = projection.get("evidence_facts") or {}
    if isinstance(facts, dict) and str(facts.get(role) or "").strip():
        return str(facts.get(role)).strip()
    lines = projection.get("visible_evidence_lines") or []
    if isinstance(lines, list):
        for line in lines:
            text = str(line).strip()
            if text.startswith(role):
                return text
    return ""


def strip_role_alias(text: str) -> str:
    stripped = ROLE_PREFIX_RE.sub("", str(text).strip())
    # Keep path/snippet content, but do not let the option value be the role name.
    return " ".join(stripped.split())


def option_permutation(row_id: str, options: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(options, key=lambda option: hashlib.sha256(f"{row_id}::{option['value']}".encode()).hexdigest())


def source_options(row: dict[str, Any]) -> list[dict[str, Any]]:
    projection = row.get("standalone_projection_source") or {}
    options = projection.get("opaque_options") or row.get("opaque_options") or []
    return [option for option in options if isinstance(option, dict) and str(option.get("value") or "").strip()]


def source_gold(row: dict[str, Any]) -> str:
    projection = row.get("standalone_projection_source") or {}
    return str(projection.get("gold_value") or row.get("gold_value") or "").strip()


def make_grouped_row(row: dict[str, Any], *, split: str, stage_prefix: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    options = source_options(row)
    gold = source_gold(row)
    if not options or not gold:
        return None, {"row_id": row.get("row_id"), "reason": "missing_options_or_gold"}
    roles = [str(option.get("value") or "").strip() for option in options]
    if gold not in roles:
        return None, {"row_id": row.get("row_id"), "reason": "gold_not_in_options", "gold_value": gold}
    row_id = f"{stage_prefix}::{row.get('row_id')}"
    fact_options: list[dict[str, str]] = []
    role_by_value: dict[str, str] = {}
    for idx, role in enumerate(roles, start=1):
        raw_fact = evidence_fact(row, role)
        fact = strip_role_alias(raw_fact)
        if not fact or fact == role or any(alias in fact for alias in ROLE_NAMES):
            return None, {"row_id": row.get("row_id"), "reason": "missing_or_alias_leaky_evidence_fact", "role": role}
        item_id = f"E{idx:02d}"
        value = f"{item_id}: {fact}"
        fact_options.append({"label": "", "value": value})
        role_by_value[value] = role
    fact_options = option_permutation(row_id, fact_options)
    labels = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    opaque_options = [{"label": labels[idx], "value": option["value"]} for idx, option in enumerate(fact_options)]
    gold_value = next(value for value, role in role_by_value.items() if role == gold)
    target_label = next(option["label"] for option in opaque_options if option["value"] == gold_value)
    ledger_lines = "\n".join(f"{option['label']}. {option['value']}" for option in opaque_options)
    prompt = (
        f"{prompt_without_options(row)}\n\n"
        "Evidence item candidates with role aliases removed:\n"
        f"{ledger_lines}\n\n"
        "Task: choose the evidence item whose visible fact is the most decisive support for the maintainer decision.\n"
        "Do not infer from role names; use the concrete source/test/evidence content.\n\n"
        "Options:\n"
        f"{ledger_lines}\n"
        "Answer:"
    )
    payload = {
        "row_id": row_id,
        "source_row_id": row.get("row_id"),
        "root_id": root_key(row),
        "source_root_id": row.get("source_root_id") or root_key(row),
        "repo_family": row.get("repo_family"),
        "language_family": row.get("language_family"),
        "task_type": "evidence_citation",
        "split": split,
        "package_split": split,
        "prompt_text": prompt,
        "input_text": prompt,
        "target_text": target_label,
        "decoder_text": target_label,
        "bounded_choice_target_label": target_label,
        "opaque_options": opaque_options,
        "expected_enabled_loss": "decoder_ce",
        "loss_mask": {"decoder_ce": True},
        "target_token_len": 1,
        "standalone_projection_source": {
            "projection_mode": "stage11233_grouped_evidence_item_fact",
            "source_row_id": row.get("row_id"),
            "source_gold_value": gold,
            "gold_value": gold_value,
            "gold_label": target_label,
            "role_by_option_value": role_by_value,
            "opaque_options": opaque_options,
        },
        "anti_cheat": {
            "grouped_evidence_item_fact_options": True,
            "role_aliases_removed_from_option_values": True,
            "deterministic_option_shuffle": True,
            "target_label_not_visible_pre_options": True,
            "same_surface_eval_admissible": split != "train",
            "train_support_only": split == "train",
        },
    }
    return payload, None


def main() -> None:
    support_source = [row for row in load_jsonl(SUPPORT_ROWS) if row.get("task_type") == "evidence_citation"]
    residual_source = [row for row in load_jsonl(RESIDUAL_ROWS) if row.get("task_type") == "evidence_citation"]
    train_rows: list[dict[str, Any]] = []
    diag_rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in support_source:
        converted, block = make_grouped_row(row, split="train", stage_prefix="stage11233_train")
        if converted:
            train_rows.append(converted)
        if block:
            blocked.append(block)
    for row in residual_source:
        converted, block = make_grouped_row(row, split="diagnostic_eval", stage_prefix="stage11233_diag")
        if converted:
            diag_rows.append(converted)
        if block:
            blocked.append(block)
    by_train_lang = Counter(str(row.get("language_family") or "unknown") for row in train_rows)
    by_diag_lang = Counter(str(row.get("language_family") or "unknown") for row in diag_rows)
    by_train_gold = Counter(str((row.get("standalone_projection_source") or {}).get("source_gold_value") or "") for row in train_rows)
    by_diag_gold = Counter(str((row.get("standalone_projection_source") or {}).get("source_gold_value") or "") for row in diag_rows)
    train_roots = {root_key(row) for row in train_rows}
    diag_roots = {root_key(row) for row in diag_rows}
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(train_rows) and bool(diag_rows) and not blocked and not (train_roots & diag_roots),
        "decision": "grouped_evidence_item_fact_package_built",
        "rationale": [
            "Prior evidence probes exposed scorer collapse around semantic role aliases.",
            "This package keeps the grouped-choice task but makes option values concrete evidence facts with role aliases removed.",
        ],
        "counts": {
            "train_rows": len(train_rows),
            "diagnostic_rows": len(diag_rows),
            "blocked_rows": len(blocked),
            "train_unique_roots": len(train_roots),
            "diagnostic_unique_roots": len(diag_roots),
            "train_diag_root_overlap": len(train_roots & diag_roots),
            "train_by_language": dict(sorted(by_train_lang.items())),
            "diag_by_language": dict(sorted(by_diag_lang.items())),
            "train_by_source_gold_role": dict(sorted(by_train_gold.items())),
            "diag_by_source_gold_role": dict(sorted(by_diag_gold.items())),
        },
        "quality_gates": {
            "role_aliases_removed_from_option_values": all(
                not any(role in str(option.get("value") or "") for role in ROLE_NAMES)
                for row in train_rows + diag_rows
                for option in row.get("opaque_options", [])
            ),
            "root_disjoint_train_diag": not (train_roots & diag_roots),
            "all_rows_have_grouped_options": all(len(row.get("opaque_options") or []) >= 4 for row in train_rows + diag_rows),
            "diagnostic_not_promotable": True,
        },
        "blocked": blocked,
        "source_artifacts": {"support_rows": rel(SUPPORT_ROWS), "residual_rows": rel(RESIDUAL_ROWS)},
        "outputs": {"summary_json": rel(SUMMARY_JSON), "train_rows_jsonl": rel(TRAIN_ROWS_JSONL), "diagnostic_rows_jsonl": rel(DIAG_ROWS_JSONL)},
    }
    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(DIAG_ROWS_JSONL, diag_rows)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
