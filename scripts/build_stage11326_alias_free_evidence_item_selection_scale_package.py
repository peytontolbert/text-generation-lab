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
ART = ROOT / "runs/local/artifacts"
STAGE = 11326
NAME = "stage11326_alias_free_evidence_item_selection_scale_package"
OUT = ART / NAME
SUMMARY = OUT / "alias_free_evidence_item_selection_scale_package.json"

SOURCE_FILES = {
    "stage11275_train": (
        "train",
        ART
        / "stage11275_direct_retrieval_multilingual_evidence_materialization"
        / "direct_retrieval_multilingual_evidence_train_rows.jsonl",
    ),
    "stage11275_validation": (
        "validation",
        ART
        / "stage11275_direct_retrieval_multilingual_evidence_materialization"
        / "direct_retrieval_multilingual_evidence_validation_rows.jsonl",
    ),
    "stage11275_strict": (
        "strict",
        ART
        / "stage11275_direct_retrieval_multilingual_evidence_materialization"
        / "direct_retrieval_multilingual_evidence_strict_rows.jsonl",
    ),
    "stage11259_train": (
        "train",
        ART
        / "stage11259_true_evidence_candidate_judgment_package"
        / "true_evidence_candidate_judgment_train_rows.jsonl",
    ),
    "stage11269_train": (
        "train",
        ART
        / "stage11269_source_specific_evidence_item_materialization"
        / "source_specific_evidence_item_train_rows.jsonl",
    ),
    "stage11269_validation": (
        "validation",
        ART
        / "stage11269_source_specific_evidence_item_materialization"
        / "source_specific_evidence_item_validation_rows.jsonl",
    ),
    "stage11269_strict": (
        "strict",
        ART
        / "stage11269_source_specific_evidence_item_materialization"
        / "source_specific_evidence_item_strict_rows.jsonl",
    ),
}

PROTECTED_FILES = [
    ART
    / "stage11320_alias_free_evidence_item_selection_package"
    / "alias_free_evidence_item_selection_validation_rows.jsonl",
    ART
    / "stage11320_alias_free_evidence_item_selection_package"
    / "alias_free_evidence_item_selection_strict_rows.jsonl",
    ART
    / "stage11320_alias_free_evidence_item_selection_package"
    / "alias_free_residual_diagnostic_rows.jsonl",
    ART / "stage11312_deleaked_fail_to_pass_transition_package" / "deleaked_fail_to_pass_validation_rows.jsonl",
    ART / "stage11312_deleaked_fail_to_pass_transition_package" / "deleaked_fail_to_pass_strict_rows.jsonl",
    ART / "stage11312_deleaked_fail_to_pass_transition_package" / "deleaked_fail_to_pass_residual_rows.jsonl",
]

DIAGNOSTIC = (
    ART
    / "stage11318_alias_free_residual_evidence_item_materialization"
    / "alias_free_residual_evidence_item_rows.jsonl"
)

OUTPUTS = {
    "train": OUT / "alias_free_evidence_item_selection_scale_train_rows.jsonl",
    "validation": OUT / "alias_free_evidence_item_selection_scale_validation_rows.jsonl",
    "strict": OUT / "alias_free_evidence_item_selection_scale_strict_rows.jsonl",
    "diagnostic": OUT / "alias_free_evidence_item_selection_scale_diagnostic_rows.jsonl",
}

LABELS = list("ABCDEFGH")
SPLIT_PRIORITY = {"strict": 3, "validation": 2, "train": 1}
TARGET_MAP = {
    "DECISIVE_VERIFIER_TEST_CONSTRAINT": "verifier_and_test_constraint",
    "SUPPORTING_CANDIDATE_CHANGE_SURFACE": "candidate_change_surface",
    "SUPPORTING_SYMPTOM_OR_CALL_PATH": "symptom_or_call_path_analogue",
    "DISTRACTOR_BACKGROUND_CONTEXT": "background_context",
}
TASK_TEXT = {
    "DECISIVE_VERIFIER_TEST_CONSTRAINT": "Task: Choose the evidence item that contains concrete selected-test, verifier, command-result, assertion, or expected-outcome evidence.",
    "SUPPORTING_CANDIDATE_CHANGE_SURFACE": "Task: Choose the evidence item that contains the modified source, configuration, implementation, or changed artifact surface.",
    "SUPPORTING_SYMPTOM_OR_CALL_PATH": "Task: Choose the evidence item that contains symptom, call-path, runtime behavior, or failure analogue evidence.",
    "DISTRACTOR_BACKGROUND_CONTEXT": "Task: Choose the item that is only broad background context rather than direct maintainer evidence.",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def root_id(row: dict[str, Any]) -> str:
    return str(
        row.get("root_id")
        or row.get("source_root_id")
        or row.get("root_lineage_key")
        or row.get("row_id")
        or ""
    )


def gold_class(row: dict[str, Any]) -> str:
    source = row.get("standalone_projection_source") or {}
    raw = str(source.get("source_target_class") or source.get("gold_value") or row.get("semantic_target_value") or "")
    for canonical, semantic in TARGET_MAP.items():
        if raw == canonical or raw == semantic:
            return canonical
    return ""


def role_for_target(target: str) -> str:
    return TARGET_MAP[target]


def extract_candidate_text(row: dict[str, Any]) -> str:
    text = str(row.get("prompt_text") or row.get("input_text") or "")
    markers = [
        "Candidate evidence item under judgment:",
        "Candidate evidence item:",
        "Candidate item:",
    ]
    for marker in markers:
        if marker in text:
            text = text.split(marker, 1)[1]
            break
    text = text.split("\nOptions:", 1)[0]
    text = text.split("\nAnswer:", 1)[0]
    text = re.sub(r"\s+", " ", text).strip()
    return text[:900]


def protected_roots() -> set[str]:
    roots: set[str] = set()
    for path in PROTECTED_FILES:
        for row in read_jsonl(path):
            roots.add(root_id(row))
    return roots


def load_source_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_summary: dict[str, Any] = {}
    protected = protected_roots()
    for source_name, (source_split, path) in SOURCE_FILES.items():
        raw_rows = read_jsonl(path)
        usable = []
        for row in raw_rows:
            target = gold_class(row)
            if not target:
                continue
            entry = dict(row)
            entry["_source_name"] = source_name
            entry["_source_split"] = source_split
            entry["_gold_class"] = target
            entry["_candidate_text"] = extract_candidate_text(row)
            entry["_protected_overlap"] = root_id(row) in protected
            if entry["_candidate_text"] and not entry["_protected_overlap"]:
                usable.append(entry)
        source_summary[source_name] = {
            "path": rel(path),
            "source_split": source_split,
            "raw_rows": len(raw_rows),
            "usable_rows": len(usable),
            "protected_overlap_rows": sum(1 for row in raw_rows if root_id(row) in protected),
            "usable_by_language": dict(
                sorted(Counter(str(row.get("language_family") or "unknown") for row in usable).items())
            ),
            "usable_by_gold": dict(sorted(Counter(role_for_target(row["_gold_class"]) for row in usable).items())),
        }
        rows.extend(usable)
    return rows, source_summary


def choose_root_splits(rows: list[dict[str, Any]]) -> dict[str, str]:
    by_root: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        by_root[root_id(row)].add(row["_source_split"])
    assignments = {}
    for rid, splits in by_root.items():
        assignments[rid] = max(splits, key=lambda split: SPLIT_PRIORITY[split])
    return assignments


def build_selection_rows(rows: list[dict[str, Any]], root_splits: dict[str, str]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    blocked: list[dict[str, Any]] = []
    for row in rows:
        rid = root_id(row)
        assigned = root_splits[rid]
        if row["_source_split"] == assigned:
            grouped[(assigned, rid)].append(row)

    built: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "strict": []}
    for (split, rid), root_rows in grouped.items():
        candidates = []
        seen = set()
        for row in root_rows:
            key = (row["_gold_class"], row["_candidate_text"][:220])
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "target_class": row["_gold_class"],
                    "role": role_for_target(row["_gold_class"]),
                    "item": row["_candidate_text"],
                    "source_row_id": row.get("row_id"),
                    "language_family": row.get("language_family"),
                    "repo_family": row.get("repo_family"),
                    "repo_id": row.get("repo_id"),
                    "source_name": row["_source_name"],
                }
            )
        if len(candidates) < 2:
            blocked.append({"root_id": rid, "split": split, "blockers": ["fewer_than_two_candidates"], "candidate_count": len(candidates)})
            continue
        by_target = defaultdict(list)
        for index, candidate in enumerate(candidates):
            by_target[candidate["target_class"]].append(index)
        for desired, matches in sorted(by_target.items()):
            if len(matches) != 1:
                blocked.append(
                    {
                        "root_id": rid,
                        "split": split,
                        "blockers": [f"desired_class_{desired}_match_count_{len(matches)}"],
                        "candidate_count": len(candidates),
                    }
                )
                continue
            records = []
            evidence_lines = []
            for index, candidate in enumerate(candidates):
                evidence_id = f"E{index + 1:02d}"
                evidence_value = f"{evidence_id}. {candidate['item']}"
                evidence_lines.append(evidence_value)
                records.append((index, evidence_id, candidate, evidence_value))
            seed = hashlib.sha256(f"{STAGE}:{rid}:{desired}".encode()).hexdigest()
            records = sorted(records, key=lambda rec: hashlib.sha256((seed + rec[1]).encode()).hexdigest())
            options = []
            target_label = ""
            for option_index, (original_index, evidence_id, candidate, evidence_value) in enumerate(records):
                label = LABELS[option_index]
                options.append(
                    {
                        "label": label,
                        "value": evidence_value,
                        "semantic_candidate": {
                            "schema_version": "stage11326_alias_free_evidence_item_selection_scale_v1",
                            "option_index": option_index,
                            "candidate_label": label,
                            "candidate_value_family": "alias_free_evidence_item_text",
                            "task_type": "evidence_citation",
                            "evidence_role": candidate["role"],
                            "verifier_transition": "NONE",
                            "test_id": evidence_id,
                            "value_token_count_proxy": len(evidence_value.split()),
                        },
                    }
                )
                if original_index == matches[0]:
                    target_label = label
            base = root_rows[0]
            input_text = "\n".join(
                [
                    f"Language: {base.get('language_family')}",
                    "Perspective: evidence_citation",
                    TASK_TEXT[desired],
                    f"Repository family: {base.get('repo_family')}",
                    "Visible evidence items:",
                    *evidence_lines,
                    "Options:",
                    *[f"{option['label']}. {option['value']}" for option in options],
                    "Answer:",
                ]
            )
            package_split = split
            output_split = "strict_eval" if split == "strict" else ("eval" if split == "validation" else "train")
            built[split].append(
                {
                    "row_id": f"stage11326::{rid}::{desired}",
                    "root_id": rid,
                    "source_root_id": rid,
                    "root_lineage_key": rid,
                    "language_family": base.get("language_family"),
                    "repo_family": base.get("repo_family"),
                    "repo_id": base.get("repo_id"),
                    "task_type": "evidence_citation",
                    "split": output_split,
                    "package_split": package_split,
                    "strict_eval_eligible": split == "strict",
                    "train_support_only": split == "train",
                    "input_text": input_text,
                    "prompt_text": input_text,
                    "decoder_text": target_label,
                    "target_text": target_label,
                    "bounded_choice_target_label": target_label,
                    "semantic_target_value": role_for_target(desired),
                    "opaque_options": options,
                    "standalone_projection_source": {
                        "projection_mode": "alias_free_evidence_item_selection_scale",
                        "gold_value": role_for_target(desired),
                        "source_target_class": desired,
                        "opaque_options": options,
                        "source_rows": [candidate["source_row_id"] for candidate in candidates],
                        "evidence_items_hidden_role_metadata": candidates,
                    },
                    "expected_enabled_loss": "decoder_ce",
                    "loss_mask": {"decoder_ce": True},
                }
            )
    return built, blocked


def counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "roots": len({root_id(row) for row in rows}),
        "by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in rows).items())),
        "by_gold": dict(sorted(Counter(str(row.get("semantic_target_value")) for row in rows).items())),
        "by_target_label": dict(sorted(Counter(str(row.get("target_text")) for row in rows).items())),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_rows, source_summary = load_source_rows()
    root_splits = choose_root_splits(source_rows)
    built, blocked = build_selection_rows(source_rows, root_splits)
    diagnostic = read_jsonl(DIAGNOSTIC)

    for split, rows in built.items():
        write_jsonl(OUTPUTS[split], rows)
    write_jsonl(OUTPUTS["diagnostic"], diagnostic)

    split_roots = {split: {root_id(row) for row in rows} for split, rows in built.items()}
    overlaps = {
        "train_validation": sorted(split_roots["train"] & split_roots["validation"]),
        "train_strict": sorted(split_roots["train"] & split_roots["strict"]),
        "validation_strict": sorted(split_roots["validation"] & split_roots["strict"]),
    }
    train_counts = counts(built["train"])
    passed = bool(built["train"]) and bool(built["validation"]) and bool(built["strict"]) and not any(overlaps.values())
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": passed,
        "decision": "python_heavy_alias_free_evidence_scale_package_ready_diagnostic_only"
        if passed
        else "alias_free_evidence_scale_package_blocked",
        "counts": {split: counts(rows) for split, rows in built.items()},
        "diagnostic_counts": counts(diagnostic),
        "source_summaries": source_summary,
        "audit": {
            "root_overlap": overlaps,
            "blocked_rows": len(blocked),
            "blocked_examples": blocked[:40],
            "target_position_distribution": {
                split: dict(sorted(Counter(row.get("target_text") for row in rows).items()))
                for split, rows in built.items()
            },
        },
        "readiness": {
            "diagnostic_package": True,
            "promotable_multilingual_package": False,
            "reason_not_promotable": "train supply remains heavily Python-skewed with too little Rust/Web evidence root coverage",
            "rust_train_rows": train_counts["by_language"].get("rust", 0),
            "web_train_rows": train_counts["by_language"].get("web_js_ts_html", 0),
        },
        "source_artifacts": {name: rel(path) for name, (_, path) in SOURCE_FILES.items()},
        "outputs": {split: rel(path) for split, path in OUTPUTS.items()},
        "recommended_next_action": "run only as diagnostic if desired; do not promote unless alias-free heldout improves and canary remains intact",
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
