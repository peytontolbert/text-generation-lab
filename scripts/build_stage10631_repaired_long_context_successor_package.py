from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10631
NAME = "stage10631_repaired_long_context_successor_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

ROOTS_JSONL = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
DECISIVE_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10629_long_context_decisive_evidence_successor/long_context_decisive_evidence_successor_rows.jsonl"
DECISIVE_STRICT_JSONL = ROOT / "runs/local/artifacts/stage10629_long_context_decisive_evidence_successor/long_context_decisive_evidence_successor_strict_rows.jsonl"
DECISION_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10630_long_context_decision_head_successors/long_context_decision_head_successor_rows.jsonl"
DECISION_STRICT_JSONL = ROOT / "runs/local/artifacts/stage10630_long_context_decision_head_successors/long_context_decision_head_successor_strict_rows.jsonl"

PACKAGE_ROWS_JSONL = OUT_DIR / "repaired_long_context_successor_rows.jsonl"
TRAIN_ROWS_JSONL = OUT_DIR / "repaired_long_context_successor_train_rows.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "repaired_long_context_successor_strict_rows.jsonl"
PACKAGE_JSON = OUT_DIR / "repaired_long_context_successor_package.json"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def enrich(
    row: dict[str, Any],
    *,
    root_lookup: dict[str, dict[str, Any]],
    strict_ids: set[str],
) -> dict[str, Any]:
    root = root_lookup.get(row["root_id"], {})
    subtype = row.get("target_subtype", "unknown")
    label_counts_note = {
        "decisive_evidence_option": "nonconstant_visible_candidates",
        "verifier_outcome_option": "nonconstant_visible_candidates",
        "retrieve_answer_abstain_option": "single_class_constant_support_only",
    }.get(subtype, "unknown")

    strict = row["row_id"] in strict_ids
    promotable_strict_eligible = strict and subtype == "decisive_evidence_option"
    support_only = subtype != "decisive_evidence_option" or not strict
    if subtype == "verifier_outcome_option":
        support_only = True
    if subtype == "retrieve_answer_abstain_option":
        support_only = True

    lineage_role = {
        "decisive_evidence_option": "repaired_long_context_decisive_evidence",
        "verifier_outcome_option": "repaired_long_context_verifier_support",
        "retrieve_answer_abstain_option": "repaired_long_context_retrieve_support",
    }.get(subtype, "repaired_long_context_unknown")

    package_role = (
        "strict_eval_candidate"
        if promotable_strict_eligible
        else "train_support_only"
    )

    out = dict(row)
    out["language_family"] = root.get("language_family", row.get("language_family", "unknown"))
    out["repo_id"] = root.get("repo_id", row.get("repo_id", "unknown"))
    out["repo_family"] = root.get("repo_family", row.get("repo_family", out["repo_id"]))
    out["source_root_split_component"] = root.get("split_component", "unknown")
    out["package_role"] = package_role
    out["lineage_role"] = lineage_role
    out["promotable_strict_eligible"] = promotable_strict_eligible
    out["train_support_only"] = support_only
    out["class_diversity_note"] = label_counts_note
    out["repaired_long_context_stage"] = STAGE
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)

    roots = load_jsonl(ROOTS_JSONL)
    decisive_rows = load_jsonl(DECISIVE_ROWS_JSONL)
    decisive_strict = load_jsonl(DECISIVE_STRICT_JSONL)
    decision_rows = load_jsonl(DECISION_ROWS_JSONL)
    decision_strict = load_jsonl(DECISION_STRICT_JSONL)

    root_lookup = {row["root_id"]: row for row in roots}
    strict_ids = {row["row_id"] for row in decisive_strict} | {row["row_id"] for row in decision_strict}

    combined = [
        enrich(row, root_lookup=root_lookup, strict_ids=strict_ids)
        for row in decisive_rows + decision_rows
    ]
    strict_rows = [row for row in combined if row["promotable_strict_eligible"]]
    train_rows = [row for row in combined if row["train_support_only"]]

    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "claim_boundary": [
            "This package combines repaired long-context successor heads into one multilingual training/eval artifact.",
            "Only decisive_evidence_option rows are currently promotable strict candidates.",
            "verifier_outcome_option is repaired and nonconstant but has no strict heldout rows yet.",
            "retrieve_answer_abstain_option is repaired structurally but remains single-class support-only.",
        ],
        "inputs": {
            "compiled_roots": str(ROOTS_JSONL.relative_to(ROOT)),
            "decisive_rows": str(DECISIVE_ROWS_JSONL.relative_to(ROOT)),
            "decisive_strict_rows": str(DECISIVE_STRICT_JSONL.relative_to(ROOT)),
            "decision_rows": str(DECISION_ROWS_JSONL.relative_to(ROOT)),
            "decision_strict_rows": str(DECISION_STRICT_JSONL.relative_to(ROOT)),
        },
        "metrics": {
            "combined_rows": len(combined),
            "train_support_rows": len(train_rows),
            "promotable_strict_rows": len(strict_rows),
            "rows_by_language": dict(sorted(Counter(row["language_family"] for row in combined).items())),
            "strict_rows_by_language": dict(sorted(Counter(row["language_family"] for row in strict_rows).items())),
            "rows_by_subtype": dict(sorted(Counter(row["target_subtype"] for row in combined).items())),
            "rows_by_package_role": dict(sorted(Counter(row["package_role"] for row in combined).items())),
            "rows_by_lineage_role": dict(sorted(Counter(row["lineage_role"] for row in combined).items())),
        },
        "promotion_boundary": {
            "promotable_strict_target_subtypes": ["decisive_evidence_option"],
            "support_only_target_subtypes": ["verifier_outcome_option", "retrieve_answer_abstain_option"],
            "retrieve_answer_abstain_constant": True,
            "verifier_outcome_strict_rows_present": False,
        },
        "next_best_step": (
            "Use this package for the next long-context 100M support cycle, but only score strict claims on decisive_evidence_option. "
            "Replenish fresh verifier-outcome and retrieve/answer/abstain heldout roots before broadening the promotable path."
        ),
        "outputs": {
            "all_rows": str(PACKAGE_ROWS_JSONL.relative_to(ROOT)),
            "train_rows": str(TRAIN_ROWS_JSONL.relative_to(ROOT)),
            "strict_rows": str(STRICT_ROWS_JSONL.relative_to(ROOT)),
        },
    }

    write_jsonl(PACKAGE_ROWS_JSONL, combined)
    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(STRICT_ROWS_JSONL, strict_rows)
    write_json(PACKAGE_JSON, package)
    write_json(RUN_SUMMARY_JSON, package)


if __name__ == "__main__":
    main()
