#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11259
NAME = "stage11259_true_evidence_candidate_judgment_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "true_evidence_candidate_judgment_package.json"
TRAIN_JSONL = OUT_DIR / "true_evidence_candidate_judgment_train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "true_evidence_candidate_judgment_validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "true_evidence_candidate_judgment_strict_rows.jsonl"
BLOCKED_JSONL = OUT_DIR / "true_evidence_candidate_judgment_blocked_roots.jsonl"
ROOT_SPLITS_JSONL = OUT_DIR / "true_evidence_candidate_judgment_root_splits.jsonl"

SOURCE_CANDIDATES = ARTIFACTS / "stage11237_multilingual_verifier_constraint_source_inventory/verifier_constraint_source_candidates.jsonl"
SOURCE_SUMMARY = ARTIFACTS / "stage11237_multilingual_verifier_constraint_source_inventory/multilingual_verifier_constraint_source_inventory.json"
CURRENT_TRAIN = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_train.jsonl"
CURRENT_VALIDATION = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_validation.jsonl"
CURRENT_STRICT = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL_BANK = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"

LABELS = list("ABCDEFGHIJ")
JUDGMENT_VALUES = [
    "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
    "SUPPORTING_SYMPTOM_OR_CALL_PATH",
    "DISTRACTOR_BACKGROUND_CONTEXT",
]
OLD_EVAL_REPOS = {
    "agentkernel",
    "bddy_website",
    "candle",
    "code_assist",
    "parametergolf",
    "repository_library",
    "tokenizers",
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


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def short_list(values: list[str], limit: int = 4) -> str:
    vals = [str(v) for v in values if str(v).strip()]
    if not vals:
        return "none recorded"
    suffix = "" if len(vals) <= limit else f" (+{len(vals) - limit} more)"
    return ", ".join(vals[:limit]) + suffix


def deterministic_options(seed: str) -> list[dict[str, str]]:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    keyed = sorted((digest[idx % len(digest)], value) for idx, value in enumerate(JUDGMENT_VALUES))
    return [{"label": LABELS[idx], "value": value} for idx, (_, value) in enumerate(keyed)]


def source_overlap_keys() -> dict[str, set[str]]:
    rows: list[dict[str, Any]] = []
    for path in [CURRENT_TRAIN, CURRENT_VALIDATION, CURRENT_STRICT, RESIDUAL_BANK]:
        rows.extend(load_jsonl(path))
    roots = {root_key(row) for row in rows if root_key(row)}
    source_rows = {
        str((row.get("standalone_projection_source") or {}).get("source_row_id") or row.get("source_row_id") or "")
        for row in rows
    }
    repos = {str(row.get("repo_family") or "") for row in rows if row.get("repo_family")}
    return {"roots": roots, "source_rows": {x for x in source_rows if x}, "repos": repos}


def split_roots(candidates: list[dict[str, Any]]) -> dict[str, str]:
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        by_lang[str(item.get("language_family") or "unknown")].append(item)
    root_to_split: dict[str, str] = {}
    for lang, items in sorted(by_lang.items()):
        items = sorted(items, key=lambda item: (-float(item.get("quality_score") or 0.0), str(item.get("root_id") or "")))
        n = len(items)
        if n <= 1:
            val_n, strict_n = 0, 0
        elif n == 2:
            val_n, strict_n = 0, 1
        elif n < 8:
            val_n, strict_n = 1, 1
        else:
            val_n = max(1, int(round(n * 0.10)))
            strict_n = max(1, int(round(n * 0.10)))
        for idx, item in enumerate(items):
            root = str(item.get("root_id") or item.get("source_root_id"))
            if idx < strict_n:
                split = "strict_eval"
            elif idx < strict_n + val_n:
                split = "validation"
            else:
                split = "train"
            root_to_split[root] = split
    return root_to_split


def evidence_items(item: dict[str, Any]) -> list[dict[str, str]]:
    candidate_paths = [str(x) for x in item.get("candidate_change_surface_paths") or [] if str(x).strip()]
    verifier_paths = [str(x) for x in item.get("verifier_and_test_constraint_paths") or [] if str(x).strip()]
    symptom_paths = [str(x) for x in item.get("symptom_or_call_path_analogue_paths") or [] if str(x).strip()]
    key_symbols = [str(x) for x in item.get("key_symbols") or [] if str(x).strip()]
    route = str(item.get("execution_route") or "UNKNOWN")
    test_route = str(item.get("test_selection_route") or "PASS_TARGETED_TEST_SELECTION")
    return [
        {
            "candidate_kind": "verifier_and_test_constraint",
            "candidate_text": f"Selected verifier/test target(s): {short_list(verifier_paths)}; test-selection route={test_route}.",
            "target_value": "DECISIVE_VERIFIER_TEST_CONSTRAINT",
        },
        {
            "candidate_kind": "candidate_change_surface",
            "candidate_text": f"Changed source/edit surface path(s): {short_list(candidate_paths)}.",
            "target_value": "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
        },
        {
            "candidate_kind": "symptom_or_call_path_analogue",
            "candidate_text": f"Symptom/call-path analogue evidence: route={route}; path or symbol preview={short_list(symptom_paths or key_symbols)}.",
            "target_value": "SUPPORTING_SYMPTOM_OR_CALL_PATH",
        },
        {
            "candidate_kind": "nearby_definition_or_usage_context",
            "candidate_text": f"Nearby context/background symbols: {short_list(key_symbols)}. This may help orientation but is not the selected verifier constraint.",
            "target_value": "DISTRACTOR_BACKGROUND_CONTEXT",
        },
    ]


def prompt_for(item: dict[str, Any], evidence: dict[str, str], options: list[dict[str, str]]) -> str:
    lines = [
        f"Language: {item.get('language_family')}",
        "Perspective: evidence_candidate_judgment",
        "Decision objective: identify whether the single candidate evidence item is the decisive verifier/test constraint, a supporting changed-surface fact, a supporting symptom/call-path fact, or only background context.",
        "Do not infer from option order. Use only the visible candidate evidence item and root context.",
        f"Repository family: {item.get('repo_family')}",
        f"Execution route: {item.get('execution_route') or 'UNKNOWN'}",
        f"Test-selection route: {item.get('test_selection_route') or 'UNKNOWN'}",
        f"Known changed surface preview: {short_list([str(x) for x in item.get('candidate_change_surface_paths') or []])}",
        f"Known verifier/test preview: {short_list([str(x) for x in item.get('verifier_and_test_constraint_paths') or []])}",
        "",
        "Candidate evidence item under judgment:",
        f"Candidate ID: CE-{hashlib.sha256((str(item.get('root_id')) + evidence['candidate_text']).encode('utf-8')).hexdigest()[:8]}",
        f"Text: {evidence['candidate_text']}",
        "",
        "Options:",
    ]
    lines.extend(f"{opt['label']}. {opt['value']}" for opt in options)
    lines.append("Answer:")
    return "\n".join(lines)


def build_rows_for_root(item: dict[str, Any], split: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[str] = []
    if item.get("language_family") not in {"python", "rust", "c_cpp", "web_js_ts_html"}:
        blockers.append("unsupported_language")
    if not item.get("candidate_change_surface_paths"):
        blockers.append("missing_candidate_paths")
    if not item.get("verifier_and_test_constraint_paths"):
        blockers.append("missing_verifier_paths")
    if not (item.get("symptom_or_call_path_analogue_paths") or item.get("key_symbols")):
        blockers.append("missing_symptom_or_symbol_context")
    if set(item.get("candidate_change_surface_paths") or []) & set(item.get("verifier_and_test_constraint_paths") or []):
        blockers.append("candidate_verifier_path_overlap")
    if blockers:
        return [], [{"root_id": item.get("root_id"), "source_row_id": item.get("source_row_id"), "blockers": sorted(set(blockers))}]

    rows: list[dict[str, Any]] = []
    for idx, evidence in enumerate(evidence_items(item)):
        seed = f"{item.get('root_id')}::{evidence['candidate_kind']}::{idx}"
        options = deterministic_options(seed)
        target = evidence["target_value"]
        target_label = next(opt["label"] for opt in options if opt["value"] == target)
        row_id = f"stage11259::{item.get('source_root_id')}::evidence_candidate_judgment::{evidence['candidate_kind']}"
        prompt = prompt_for(item, evidence, options)
        row = {
            "row_id": row_id,
            "root_id": item.get("root_id"),
            "source_root_id": item.get("source_root_id"),
            "root_lineage_key": item.get("root_lineage_key"),
            "source_row_id": item.get("source_row_id"),
            "source_family_id": item.get("source_family_id"),
            "repo_family": item.get("repo_family"),
            "repo_id": item.get("repo_id"),
            "language_family": item.get("language_family"),
            "task_type": "evidence_candidate_judgment",
            "surface": "maintainer_evidence_candidate_judgment_bounded_choice",
            "split": split,
            "package_split": split,
            "input_text": prompt,
            "prompt_text": prompt,
            "decoder_text": target_label,
            "target_text": target_label,
            "bounded_choice_target_label": target_label,
            "semantic_target_value": target,
            "opaque_options": options,
            "expected_enabled_loss": "decoder_ce",
            "loss_mask": {"decoder_ce": True},
            "strict_eval_eligible": split == "strict_eval",
            "train_support_only": split == "train",
            "anti_cheat": {
                "deterministic_option_shuffle": True,
                "root_split_isolation_required": True,
                "single_candidate_item_judgment": True,
                "target_label_not_visible_before_options": True,
                "role_alias_not_visible_before_options": True,
                "candidate_and_verifier_paths_distinct": True,
            },
            "standalone_projection_source": {
                "gold_label": target_label,
                "gold_value": target,
                "opaque_options": options,
                "candidate_evidence_kind": evidence["candidate_kind"],
                "candidate_evidence_text": evidence["candidate_text"],
                "candidate_change_surface_paths": item.get("candidate_change_surface_paths") or [],
                "verifier_and_test_constraint_paths": item.get("verifier_and_test_constraint_paths") or [],
                "symptom_or_call_path_analogue_paths": item.get("symptom_or_call_path_analogue_paths") or [],
                "key_symbols": item.get("key_symbols") or [],
                "source_row_id": item.get("source_row_id"),
                "source_inventory_stage": "stage11237",
                "objective": "candidate_evidence_decisive_supporting_or_distractor_judgment",
            },
        }
        rows.append(row)
    return rows, []


def count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field) or "unknown") for row in rows).items()))


def main() -> None:
    source_summary = load_json(SOURCE_SUMMARY)
    candidates = load_jsonl(SOURCE_CANDIDATES)
    overlaps = source_overlap_keys()
    filtered: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for item in candidates:
        reasons = []
        if item.get("repo_family") in OLD_EVAL_REPOS or item.get("repo_family") in overlaps["repos"]:
            reasons.append("repo_family_overlaps_existing_train_eval")
        if item.get("root_id") in overlaps["roots"] or item.get("source_root_id") in overlaps["roots"]:
            reasons.append("root_overlaps_existing_train_eval")
        if item.get("source_row_id") in overlaps["source_rows"]:
            reasons.append("source_row_overlaps_existing_train_eval")
        if reasons:
            blocked.append({"root_id": item.get("root_id"), "source_row_id": item.get("source_row_id"), "repo_family": item.get("repo_family"), "language_family": item.get("language_family"), "blockers": reasons})
        else:
            filtered.append(item)

    root_to_split = split_roots(filtered)
    rows_by_split: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "strict_eval": []}
    root_split_rows: list[dict[str, Any]] = []
    for item in filtered:
        split = root_to_split[str(item.get("root_id") or item.get("source_root_id"))]
        built, blocks = build_rows_for_root(item, split)
        if blocks:
            blocked.extend(blocks)
            continue
        rows_by_split[split].extend(built)
        root_split_rows.append({
            "root_id": item.get("root_id"),
            "source_root_id": item.get("source_root_id"),
            "source_row_id": item.get("source_row_id"),
            "repo_family": item.get("repo_family"),
            "language_family": item.get("language_family"),
            "split": split,
            "rows": len(built),
        })

    train, validation, strict = rows_by_split["train"], rows_by_split["validation"], rows_by_split["strict_eval"]
    root_sets = {split: {str(row.get("root_id")) for row in rows} for split, rows in rows_by_split.items()}
    root_overlap = {
        "train_validation": sorted(root_sets["train"] & root_sets["validation"]),
        "train_strict": sorted(root_sets["train"] & root_sets["strict_eval"]),
        "validation_strict": sorted(root_sets["validation"] & root_sets["strict_eval"]),
    }
    row_ids = [row["row_id"] for rows in rows_by_split.values() for row in rows]
    all_rows = train + validation + strict
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(train and validation and strict) and not any(root_overlap.values()) and len(row_ids) == len(set(row_ids)),
        "decision": "true_evidence_candidate_judgment_package_ready" if bool(train and validation and strict) and not any(root_overlap.values()) and len(row_ids) == len(set(row_ids)) else "true_evidence_candidate_judgment_package_blocked",
        "counts": {
            "source_ready_candidates": len(candidates),
            "filtered_roots": len(filtered),
            "blocked_roots": len(blocked),
            "train_rows": len(train),
            "validation_rows": len(validation),
            "strict_rows": len(strict),
            "train_roots": len(root_sets["train"]),
            "validation_roots": len(root_sets["validation"]),
            "strict_roots": len(root_sets["strict_eval"]),
            "by_split_language": {split: count_by(rows, "language_family") for split, rows in rows_by_split.items()},
            "by_split_target": {split: count_by(rows, "semantic_target_value") for split, rows in rows_by_split.items()},
            "root_overlap": root_overlap,
            "duplicate_row_ids": len(row_ids) - len(set(row_ids)),
            "c_cpp_gap": {
                "ready_c_cpp_roots": sum(1 for item in filtered if item.get("language_family") == "c_cpp"),
                "stage11237_ready_c_cpp_candidates": (source_summary.get("counts") or {}).get("ready_by_language", {}).get("c_cpp", 0),
                "reason": "stage11237 found no clean C/C++ verifier-constraint source candidates under current filters",
            },
        },
        "quality_gates": {
            "root_split_disjoint": not any(root_overlap.values()),
            "unique_row_ids": len(row_ids) == len(set(row_ids)),
            "all_rows_have_four_options": all(len((row.get("standalone_projection_source") or {}).get("opaque_options") or []) == 4 for row in all_rows),
            "all_rows_are_single_candidate_judgments": all((row.get("anti_cheat") or {}).get("single_candidate_item_judgment") is True for row in all_rows),
            "all_strict_rows_not_train_support_only": all(not row.get("train_support_only") for row in strict),
            "target_distribution_balanced_by_root_projection": all(len(set(count_by(rows, "semantic_target_value").values())) <= 1 for rows in rows_by_split.values() if rows),
        },
        "interpretation": {
            "why_this_differs_from_stage11249": "Stage11249 asked multiple role targets over the same root-level prompt. Stage11259 asks one candidate-evidence judgment per row, so the label is a property of the visible candidate item rather than a different desired answer over identical evidence.",
            "promotion_status": "diagnostic_training_candidate_not_multilingual_promotion_ready",
            "claim_limit": "No C/C++ source supply is present; Rust/Web supply is small. This package can test scorer-objective alignment, not satisfy the final multilingual Gemma claim alone.",
        },
        "source_artifacts": {
            "stage11237_summary": rel(SOURCE_SUMMARY),
            "stage11237_candidates": rel(SOURCE_CANDIDATES),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_jsonl": rel(TRAIN_JSONL),
            "validation_jsonl": rel(VALIDATION_JSONL),
            "strict_jsonl": rel(STRICT_JSONL),
            "blocked_jsonl": rel(BLOCKED_JSONL),
            "root_splits_jsonl": rel(ROOT_SPLITS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    write_jsonl(TRAIN_JSONL, train)
    write_jsonl(VALIDATION_JSONL, validation)
    write_jsonl(STRICT_JSONL, strict)
    write_jsonl(BLOCKED_JSONL, blocked)
    write_jsonl(ROOT_SPLITS_JSONL, root_split_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
