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
STAGE = 11260
NAME = "stage11260_true_evidence_candidate_judgment_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "true_evidence_candidate_judgment_audit.json"
ROW_CARDS_JSONL = OUT_DIR / "true_evidence_candidate_judgment_audit_cards.jsonl"

PACKAGE = ARTIFACTS / "stage11259_true_evidence_candidate_judgment_package/true_evidence_candidate_judgment_package.json"
TRAIN = ARTIFACTS / "stage11259_true_evidence_candidate_judgment_package/true_evidence_candidate_judgment_train_rows.jsonl"
VALIDATION = ARTIFACTS / "stage11259_true_evidence_candidate_judgment_package/true_evidence_candidate_judgment_validation_rows.jsonl"
STRICT = ARTIFACTS / "stage11259_true_evidence_candidate_judgment_package/true_evidence_candidate_judgment_strict_rows.jsonl"

JUDGMENT_VALUES = {
    "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
    "SUPPORTING_SYMPTOM_OR_CALL_PATH",
    "DISTRACTOR_BACKGROUND_CONTEXT",
}
ROLE_ALIASES = {
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
}
HIGH_RISK_TARGET_CUES = {
    "DECISIVE_VERIFIER_TEST_CONSTRAINT": [r"selected verifier", r"test-selection route", r"verifier/test target"],
    "SUPPORTING_CANDIDATE_CHANGE_SURFACE": [r"changed source", r"changed surface", r"edit surface"],
    "SUPPORTING_SYMPTOM_OR_CALL_PATH": [r"symptom/call-path", r"execution route"],
    "DISTRACTOR_BACKGROUND_CONTEXT": [r"nearby context", r"background symbols", r"not the selected verifier"],
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def pre_options_text(row: dict[str, Any]) -> str:
    text = str(row.get("input_text") or row.get("prompt_text") or "")
    return text.split("\nOptions:\n", 1)[0] if "\nOptions:\n" in text else text


def option_values(row: dict[str, Any]) -> list[str]:
    return [str(opt.get("value") or "") for opt in ((row.get("standalone_projection_source") or {}).get("opaque_options") or row.get("opaque_options") or []) if isinstance(opt, dict)]


def option_labels(row: dict[str, Any]) -> list[str]:
    return [str(opt.get("label") or "") for opt in ((row.get("standalone_projection_source") or {}).get("opaque_options") or row.get("opaque_options") or []) if isinstance(opt, dict)]


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def row_card(row: dict[str, Any], split: str) -> dict[str, Any]:
    pre = pre_options_text(row)
    target = str(row.get("semantic_target_value") or (row.get("standalone_projection_source") or {}).get("gold_value") or "")
    target_label = str(row.get("bounded_choice_target_label") or row.get("target_text") or "")
    values = option_values(row)
    labels = option_labels(row)
    target_value_leaks = [value for value in JUDGMENT_VALUES if value in pre]
    role_alias_leaks = [alias for alias in ROLE_ALIASES if alias in pre]
    target_label_leak = bool(target_label and re.search(rf"(^|\W){re.escape(target_label)}($|\W)", pre))
    cue_hits = [cue for cue in HIGH_RISK_TARGET_CUES.get(target, []) if re.search(cue, pre, re.I)]
    sps = row.get("standalone_projection_source") or {}
    return {
        "row_id": row.get("row_id"),
        "split": split,
        "root_id": root_key(row),
        "source_row_id": row.get("source_row_id"),
        "language_family": row.get("language_family"),
        "repo_family": row.get("repo_family"),
        "target_value": target,
        "target_label": target_label,
        "option_values": values,
        "option_labels": labels,
        "option_count": len(values),
        "target_value_leaks_before_options": target_value_leaks,
        "role_alias_leaks_before_options": role_alias_leaks,
        "target_label_leak_before_options": target_label_leak,
        "target_specific_cue_hits": cue_hits,
        "candidate_evidence_kind_hidden": "Kind hint:" not in pre and not role_alias_leaks,
        "candidate_id_opaque_present": "Candidate ID: CE-" in pre,
        "has_candidate_text": bool(sps.get("candidate_evidence_text")),
        "contract_passed_row_level": bool(
            len(values) == 4
            and set(values) == JUDGMENT_VALUES
            and target in JUDGMENT_VALUES
            and not target_value_leaks
            and not role_alias_leaks
            and not target_label_leak
            and "Kind hint:" not in pre
            and "Candidate ID: CE-" in pre
            and bool(sps.get("candidate_evidence_text"))
        ),
    }


def summarize_cards(cards: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(cards),
        "contract_passed_rows": sum(1 for c in cards if c["contract_passed_row_level"]),
        "contract_failed_rows": sum(1 for c in cards if not c["contract_passed_row_level"]),
        "by_language": dict(sorted(Counter(str(c.get("language_family") or "unknown") for c in cards).items())),
        "by_target": dict(sorted(Counter(str(c.get("target_value") or "unknown") for c in cards).items())),
        "by_target_label": dict(sorted(Counter(str(c.get("target_label") or "unknown") for c in cards).items())),
        "role_alias_leak_rows": sum(1 for c in cards if c["role_alias_leaks_before_options"]),
        "target_value_leak_rows": sum(1 for c in cards if c["target_value_leaks_before_options"]),
        "target_label_leak_rows": sum(1 for c in cards if c["target_label_leak_before_options"]),
        "target_specific_cue_rows": sum(1 for c in cards if c["target_specific_cue_hits"]),
    }


def main() -> None:
    package = load_json(PACKAGE)
    split_rows = {
        "train": load_jsonl(TRAIN),
        "validation": load_jsonl(VALIDATION),
        "strict_eval": load_jsonl(STRICT),
    }
    cards: list[dict[str, Any]] = []
    for split, rows in split_rows.items():
        cards.extend(row_card(row, split) for row in rows)
    root_sets = {split: {root_key(row) for row in rows} for split, rows in split_rows.items()}
    root_overlap = {
        "train_validation": sorted(root_sets["train"] & root_sets["validation"]),
        "train_strict": sorted(root_sets["train"] & root_sets["strict_eval"]),
        "validation_strict": sorted(root_sets["validation"] & root_sets["strict_eval"]),
    }
    source_sets = {split: {str(row.get("source_row_id") or "") for row in rows if row.get("source_row_id")} for split, rows in split_rows.items()}
    source_overlap = {
        "train_validation": sorted(source_sets["train"] & source_sets["validation"]),
        "train_strict": sorted(source_sets["train"] & source_sets["strict_eval"]),
        "validation_strict": sorted(source_sets["validation"] & source_sets["strict_eval"]),
    }
    failures = [card for card in cards if not card["contract_passed_row_level"]]
    cue_rows = [card for card in cards if card["target_specific_cue_hits"]]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not failures and not any(root_overlap.values()) and not any(source_overlap.values()) and bool(package.get("passed")),
        "decision": "true_evidence_candidate_judgment_package_admitted_for_diagnostic_probe" if not failures and not any(root_overlap.values()) and not any(source_overlap.values()) and bool(package.get("passed")) else "true_evidence_candidate_judgment_package_blocked",
        "counts": {
            "all": summarize_cards(cards),
            "by_split": {split: summarize_cards([card for card in cards if card["split"] == split]) for split in split_rows},
            "unique_roots_by_split": {split: len(roots) for split, roots in root_sets.items()},
            "root_overlap": root_overlap,
            "source_row_overlap": source_overlap,
            "row_level_failures": len(failures),
            "target_specific_cue_rows": len(cue_rows),
        },
        "quality_gates": {
            "package_passed": bool(package.get("passed")),
            "all_rows_contract_passed": not failures,
            "root_split_disjoint": not any(root_overlap.values()),
            "source_row_split_disjoint": not any(source_overlap.values()),
            "no_target_value_leaks_before_options": not any(c["target_value_leaks_before_options"] for c in cards),
            "no_role_alias_leaks_before_options": not any(c["role_alias_leaks_before_options"] for c in cards),
            "no_target_label_leaks_before_options": not any(c["target_label_leak_before_options"] for c in cards),
            "candidate_ids_are_opaque": all(c["candidate_id_opaque_present"] for c in cards),
        },
        "risk_notes": [
            "Target-specific lexical cues are expected because the candidate item text must expose real evidence semantics; these rows are diagnostic training candidates, not promotable heldout proof by themselves.",
            "No C/C++ rows are present because Stage11237 found no clean C/C++ source candidates; this package cannot support the final multilingual claim alone.",
            "The package should be used to test scorer-objective alignment while preserving the Stage11200 clean canary and residual bank.",
        ],
        "sample_failures": failures[:20],
        "sample_target_specific_cues": cue_rows[:20],
        "source_artifacts": {
            "package": rel(PACKAGE),
            "train": rel(TRAIN),
            "validation": rel(VALIDATION),
            "strict": rel(STRICT),
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
