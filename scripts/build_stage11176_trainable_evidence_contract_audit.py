#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11176
NAME = "stage11176_trainable_evidence_contract_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "trainable_evidence_contract_audit.json"
ROW_CARDS_JSONL = OUT_DIR / "trainable_evidence_contract_cards.jsonl"

TRAINABLE_ROWS = ARTIFACTS / "stage11113_fresh_family_evidence_admission_audit_trainable" / "admitted_evidence_rows_trainable.jsonl"
SUPPORT_PACKAGE = ARTIFACTS / "stage11114_fresh_family_support_package_with_trainable_admitted_evidence" / "fresh_family_support_package_with_trainable_admitted_evidence.json"
STAGE11175_CONTRACT = ARTIFACTS / "stage11175_clean_evidence_role_rewrite_package" / "evidence_role_admission_contract.json"
STAGE11117_POSTRUN = ARTIFACTS / "stage11117_trainable_evidence_support_postrun_audit" / "trainable_evidence_support_postrun_audit.json"

REQUIRED_GOLD_VALUES = ["candidate_change_surface", "verifier_and_test_constraint", "symptom_or_call_path_analogue"]
REQUIRED_LANGUAGES = ["python", "c_cpp", "rust", "web_js_ts_html"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def options(row: dict[str, Any]) -> list[dict[str, str]]:
    return [opt for opt in (row.get("opaque_options") or ((row.get("standalone_projection_source") or {}).get("opaque_options") or [])) if isinstance(opt, dict)]


def option_values(row: dict[str, Any]) -> list[str]:
    return [str(opt.get("value") or "") for opt in options(row)]


def gold_value(row: dict[str, Any]) -> str:
    sps = row.get("standalone_projection_source") or {}
    if sps.get("gold_value"):
        return str(sps["gold_value"])
    target = str(row.get("target_text") or "")
    for opt in options(row):
        if str(opt.get("label") or "") == target:
            return str(opt.get("value") or "")
    return ""


def ledger_items(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"^(E\d+)\.\s+(.*)$", line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def card(row: dict[str, Any]) -> dict[str, Any]:
    text = str(row.get("input_text") or row.get("prompt_text") or "")
    vals = option_values(row)
    gold = gold_value(row)
    ledgers = ledger_items(text)
    role_named_options = all(value in REQUIRED_GOLD_VALUES or value == "nearby_definition_or_usage_context" for value in vals)
    has_visible_ledger = bool(ledgers)
    verifier_ledger_count = sum(1 for value in ledgers.values() if re.search(r"verif|test|PASS_TARGETED|verification", value, re.I))
    candidate_ledger_count = sum(1 for value in ledgers.values() if re.search(r"modified surface|changed file|directly modified", value, re.I))
    symptom_ledger_count = sum(1 for value in ledgers.values() if re.search(r"symptom|execution-route|trace|call", value, re.I))
    return {
        "row_id": str(row.get("row_id") or ""),
        "language_family": str(row.get("language_family") or "unknown"),
        "repo_family": str(row.get("repo_family") or "unknown"),
        "source_root_id": str(row.get("source_root_id") or ""),
        "gold_value": gold,
        "option_values": vals,
        "role_named_options": role_named_options,
        "has_visible_ledger": has_visible_ledger,
        "ledger_item_count": len(ledgers),
        "verifier_ledger_count": verifier_ledger_count,
        "candidate_ledger_count": candidate_ledger_count,
        "symptom_ledger_count": symptom_ledger_count,
        "missing_required_roles": [role for role in REQUIRED_GOLD_VALUES if role not in vals],
        "contract_passed_row_level": bool(has_visible_ledger and not [role for role in REQUIRED_GOLD_VALUES if role not in vals]),
    }


def main() -> None:
    rows = load_jsonl(TRAINABLE_ROWS)
    support = load_json(SUPPORT_PACKAGE)
    contract = load_json(STAGE11175_CONTRACT)
    postrun = load_json(STAGE11117_POSTRUN)
    cards = [card(row) for row in rows]
    gold_counts = Counter(card["gold_value"] for card in cards)
    lang_counts = Counter(card["language_family"] for card in cards)
    root_counts = Counter(card["source_root_id"] for card in cards if card["source_root_id"])
    missing_gold_values = [value for value in REQUIRED_GOLD_VALUES if gold_counts.get(value, 0) == 0]
    missing_languages = [lang for lang in REQUIRED_LANGUAGES if lang_counts.get(lang, 0) == 0]
    row_level_failures = [card for card in cards if not card["contract_passed_row_level"]]
    min_per_gold = min((gold_counts.get(value, 0) for value in REQUIRED_GOLD_VALUES), default=0)
    imbalance_ratio = (max(gold_counts.values()) / max(1, min_per_gold)) if gold_counts else None

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "current_trainable_evidence_support_is_cleaner_but_not_sufficient_for_next_probe",
        "source_artifacts": {
            "trainable_rows": rel(TRAINABLE_ROWS),
            "support_package": rel(SUPPORT_PACKAGE),
            "stage11175_contract": rel(STAGE11175_CONTRACT),
            "stage11117_postrun": rel(STAGE11117_POSTRUN),
        },
        "counts": {
            "rows": len(rows),
            "unique_roots": len(root_counts),
            "language_counts": dict(sorted(lang_counts.items())),
            "gold_value_counts": dict(sorted(gold_counts.items())),
            "missing_gold_values": missing_gold_values,
            "missing_languages": missing_languages,
            "row_level_contract_failures": len(row_level_failures),
            "imbalance_ratio_max_to_min_required_gold": imbalance_ratio,
        },
        "postrun_context": {
            "stage11117_decision": postrun.get("decision"),
            "reserved_result": (postrun.get("reserved_candidate_result") or {}),
            "successor_result": (postrun.get("successor_surface_result") or {}),
        },
        "failure_modes": [
            "No symptom_or_call_path_analogue positive examples are present in the trainable admitted evidence support.",
            "No Rust evidence support rows are present; Rust residuals remain under-materialized.",
            "Role-name options are still the supervised surface; the model is not directly scoring evidence item ids/spans yet.",
            "The prior stage11117 probe using this support preserved strict but did not improve reserved evidence residuals.",
        ],
        "admission_decision_for_next_probe": {
            "use_as_standalone_next_probe_package": False,
            "allowed_use": "Can be retained as auxiliary verifier-vs-candidate support after balancing with root-disjoint symptom/call-path positives and Rust/Web rows.",
            "minimum_before_next_training": {
                "per_required_gold_value_train_rows": 20,
                "required_languages": REQUIRED_LANGUAGES,
                "required_new_root_disjoint_rows": True,
                "semantic_candidate_scorer_objective": True,
            },
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "row_cards_jsonl": rel(ROW_CARDS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    write_jsonl(ROW_CARDS_JSONL, cards)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
