#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11378
NAME = "stage11378_web_sourcebot_plus_abstention_preservation_package"
OUT = ART / NAME
SUMMARY = OUT / "web_sourcebot_plus_abstention_preservation_package.json"
ROWS_OUT = OUT / "web_sourcebot_plus_abstention_preservation_rows.jsonl"

WEB_SUPPORT = ART / "stage11374_web_sourcebot_combined_current_score/web_sourcebot_combined_support_rows.jsonl"
CANARY = ART / "stage11312_deleaked_fail_to_pass_transition_package"
PROTECTED = [
    CANARY / "deleaked_fail_to_pass_validation_rows.jsonl",
    CANARY / "deleaked_fail_to_pass_strict_rows.jsonl",
    ART / "stage11361_web_llama_stack_executed_heldout_rows/web_llama_stack_executed_heldout_rows.jsonl",
]

# Prefer row sources that were already used as train-support manifests and
# contain reviewed/compiled compact bounded rows. This is a preservation
# package, so the goal is not new headline data; it is preventing Web support
# from erasing the abstain-vs-singleton boundary.
CANDIDATE_SOURCES = [
    ART / "stage11213_evidence_fact_text_probe_request/evidence_fact_text_probe_manifest.jsonl",
    ART / "stage11142_evidence_item_plus_verifier_support_package/agentkernel_lite_encdec_train.jsonl",
    ART / "stage10801_python_plus_rust_competition_support_probe_request/python_plus_rust_competition_support_probe_manifest.jsonl",
    ART / "stage10791_larger_root_split_plus_python_overflow_support_package/agentkernel_lite_encdec_train.jsonl",
    ART / "stage10782_targeted_residual_support_probe_request/targeted_residual_support_probe_manifest.jsonl",
]

LANGUAGE_TARGETS = {
    "python": 8,
    "c_cpp": 6,
    "rust": 6,
    "web_js_ts_html": 2,
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def root_key(row: dict[str, Any]) -> str:
    return str(
        row.get("root_id")
        or row.get("source_root_id")
        or row.get("root_lineage_key")
        or (row.get("provenance") or {}).get("root_id")
        or row.get("row_id")
        or ""
    )


def target_value(row: dict[str, Any]) -> str:
    target = str(row.get("target_text") or row.get("target_label") or "")
    for option in row.get("opaque_options") or []:
        if isinstance(option, dict) and str(option.get("label")) == target:
            return str(option.get("value") or "")
    return str(row.get("semantic_target_value") or target)


def is_true_abstain_support(row: dict[str, Any]) -> bool:
    if row.get("task_type") != "abstention_insufficient_evidence":
        return False
    if row.get("train_support_only") is not True or row.get("strict_eval_eligible"):
        return False
    return target_value(row) == "ABSTAIN_INSUFFICIENT_EVIDENCE"


def normalize_support_row(row: dict[str, Any], source: Path, ordinal: int) -> dict[str, Any]:
    out = dict(row)
    out["split"] = "train"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["stage11378_source"] = rel(source)
    out["stage11378_role"] = "abstention_preservation_true_insufficient_evidence"
    out["stage11378_selected_ordinal"] = ordinal
    out.setdefault("anti_cheat", {})
    if isinstance(out["anti_cheat"], dict):
        out["anti_cheat"] = dict(out["anti_cheat"])
        out["anti_cheat"]["train_support_only"] = True
        out["anti_cheat"]["strict_eval_eligible"] = False
        out["anti_cheat"]["stage11378_preservation_anchor"] = True
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    web_rows = read_jsonl(WEB_SUPPORT)
    protected_rows = [row for path in PROTECTED for row in read_jsonl(path)]
    protected_roots = {root_key(row) for row in protected_rows}
    protected_row_ids = {str(row.get("row_id")) for row in protected_rows}

    candidates_by_lang: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    seen_row_ids: set[str] = set()
    skipped = Counter()
    for source in CANDIDATE_SOURCES:
        for row in read_jsonl(source):
            row_id = str(row.get("row_id") or "")
            if not row_id or row_id in seen_row_ids:
                skipped["duplicate_row_id"] += 1
                continue
            seen_row_ids.add(row_id)
            if row_id in protected_row_ids:
                skipped["protected_row_id"] += 1
                continue
            if root_key(row) in protected_roots:
                skipped["protected_root"] += 1
                continue
            if not is_true_abstain_support(row):
                skipped["not_true_abstain_support"] += 1
                continue
            lang = str(row.get("language_family") or "unknown")
            if lang not in LANGUAGE_TARGETS:
                skipped["unsupported_language"] += 1
                continue
            candidates_by_lang[lang].append((source, row))

    selected: list[dict[str, Any]] = []
    selection_shortfalls: dict[str, int] = {}
    selected_roots: set[str] = set()
    ordinal = 0
    for lang, target_count in LANGUAGE_TARGETS.items():
        added = 0
        for source, row in candidates_by_lang.get(lang, []):
            # Avoid letting many rows from one root dominate the preservation
            # signal unless there is no other supply.
            key = root_key(row)
            if key in selected_roots:
                continue
            ordinal += 1
            selected.append(normalize_support_row(row, source, ordinal))
            selected_roots.add(key)
            added += 1
            if added >= target_count:
                break
        if added < target_count:
            # Fill from remaining same-language rows if unique-root supply is thin.
            for source, row in candidates_by_lang.get(lang, []):
                if str(row.get("row_id")) in {str(r.get("row_id")) for r in selected}:
                    continue
                ordinal += 1
                selected.append(normalize_support_row(row, source, ordinal))
                added += 1
                if added >= target_count:
                    break
        if added < target_count:
            selection_shortfalls[lang] = target_count - added

    web_norm = []
    for row in web_rows:
        out = dict(row)
        out["split"] = "train"
        web_norm.append(out)

    combined = web_norm + selected
    overlaps = sorted({root_key(row) for row in combined} & protected_roots)
    non_support = [
        row.get("row_id")
        for row in combined
        if row.get("strict_eval_eligible") or row.get("train_support_only") is not True
    ]
    if overlaps:
        raise SystemExit(f"protected root overlap: {overlaps[:5]}")
    if non_support:
        raise SystemExit(f"non-support rows in training package: {non_support[:5]}")

    write_jsonl(ROWS_OUT, combined)
    counts = {
        "web_support_rows": len(web_norm),
        "abstention_preservation_rows": len(selected),
        "total_train_rows": len(combined),
        "protected_roots": len(protected_roots),
        "selected_languages": dict(Counter(str(row.get("language_family") or "unknown") for row in selected)),
        "combined_task_targets": dict(Counter(f"{str(row.get('task_type'))}::{target_value(row)}" for row in combined)),
        "selection_shortfalls": selection_shortfalls,
        "skipped": dict(skipped),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": len(selected) >= 12,
        "decision": "web_sourcebot_support_augmented_with_split_safe_true_abstention_preservation_valid_with_supply_shortfall",
        "counts": counts,
        "source_artifacts": {
            "web_support": rel(WEB_SUPPORT),
            "candidate_sources": [rel(path) for path in CANDIDATE_SOURCES],
            "protected": [rel(path) for path in PROTECTED],
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "rows": rel(ROWS_OUT),
        },
        "promotion_boundary": {
            "train_support_only": True,
            "uses_no_protected_eval_or_heldout_roots": True,
            "purpose": "diagnostic preservation of abstain-vs-singleton behavior while testing Web support transfer",
        },
        "supply_shortfall_warning": "No disjoint Web true-abstention support was found; package is valid for diagnostic preservation but not a complete Web abstention curriculum.",
        "recommended_next_action": "run a diagnostic probe from Stage11200 with this package; accept only if sourcebot/llama transfer improves and canary validation remains 20/23",
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"passed": summary["passed"], "counts": counts, "outputs": summary["outputs"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
