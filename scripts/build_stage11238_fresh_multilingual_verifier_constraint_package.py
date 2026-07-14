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
STAGE = 11238
NAME = "stage11238_fresh_multilingual_verifier_constraint_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_multilingual_verifier_constraint_package.json"
TRAIN_JSONL = OUT_DIR / "fresh_verifier_constraint_train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "fresh_verifier_constraint_validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "fresh_verifier_constraint_strict_rows.jsonl"
BLOCKED_JSONL = OUT_DIR / "fresh_verifier_constraint_blocked_rows.jsonl"

CANDIDATES = ARTIFACTS / "stage11237_multilingual_verifier_constraint_source_inventory/verifier_constraint_source_candidates.jsonl"
INVENTORY_SUMMARY = ARTIFACTS / "stage11237_multilingual_verifier_constraint_source_inventory/multilingual_verifier_constraint_source_inventory.json"

ROLE_VALUES = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
]
LABELS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def path_preview(paths: list[str], limit: int = 4) -> str:
    clean = [str(path) for path in paths if str(path).strip()]
    if not clean:
        return "none"
    suffix = f" (+{len(clean) - limit} more)" if len(clean) > limit else ""
    return ", ".join(clean[:limit]) + suffix


def stable_options(seed: str) -> list[dict[str, str]]:
    values = sorted(ROLE_VALUES, key=lambda value: hashlib.sha256(f"{seed}::{value}".encode()).hexdigest())
    return [{"label": LABELS[idx], "value": value} for idx, value in enumerate(values)]


def make_row(candidate: dict[str, Any], *, split: str, ordinal: int) -> dict[str, Any]:
    row_id = f"stage11238::{split}::{candidate['source_row_id']}::{ordinal:03d}"
    options = stable_options(row_id)
    label_by_value = {option["value"]: option["label"] for option in options}
    target_label = label_by_value["verifier_and_test_constraint"]
    candidate_paths = candidate.get("candidate_change_surface_paths") or []
    verifier_paths = candidate.get("verifier_and_test_constraint_paths") or []
    symptom_paths = candidate.get("symptom_or_call_path_analogue_paths") or []
    nearby_paths = list(dict.fromkeys((candidate.get("key_symbols") or [])[:8] + symptom_paths[:2]))
    evidence_facts = {
        "candidate_change_surface": f"E01: changed implementation/configuration surfaces are visible at {path_preview(candidate_paths)}.",
        "verifier_and_test_constraint": f"E02: selected verifier/test targets are visible at {path_preview(verifier_paths)}; route={candidate.get('test_selection_route') or 'PASS_TARGETED_TEST_SELECTION'}.",
        "symptom_or_call_path_analogue": f"E03: symptom, call-path, or runtime-support context is visible at {path_preview(symptom_paths)}.",
        "nearby_definition_or_usage_context": f"E04: nearby definitions/symbol context is available: {path_preview(nearby_paths)}.",
    }
    prompt = (
        f"Language: {candidate.get('language_family')}\n"
        "Perspective: evidence_citation\n"
        "Task: choose which evidence role is the most decisive support for the maintainer decision. "
        "The correct answer must come from concrete visible facts, not option order or label prior.\n"
        f"Repository family: {candidate.get('repo_family')}\n"
        f"Execution route: {candidate.get('execution_route') or 'unknown'}\n\n"
        "Visible evidence ledger:\n"
        f"{evidence_facts['candidate_change_surface']}\n"
        f"{evidence_facts['verifier_and_test_constraint']}\n"
        f"{evidence_facts['symptom_or_call_path_analogue']}\n"
        f"{evidence_facts['nearby_definition_or_usage_context']}\n\n"
        "Options:\n"
        + "\n".join(f"{option['label']}. {option['value']}" for option in options)
        + "\nAnswer:"
    )
    return {
        "row_id": row_id,
        "source_row_id": candidate.get("source_row_id"),
        "root_id": candidate.get("root_id"),
        "source_root_id": candidate.get("source_root_id"),
        "root_lineage_key": candidate.get("root_lineage_key"),
        "repo_family": candidate.get("repo_family"),
        "repo_id": candidate.get("repo_id"),
        "language": candidate.get("language_family"),
        "language_family": candidate.get("language_family"),
        "task_type": "evidence_citation",
        "split": split,
        "package_split": split,
        "prompt_text": prompt,
        "input_text": prompt,
        "target": target_label,
        "target_label": target_label,
        "target_text": target_label,
        "decoder_text": target_label,
        "bounded_choice_target_label": target_label,
        "semantic_target_value": "verifier_and_test_constraint",
        "opaque_options": options,
        "expected_enabled_loss": "decoder_ce",
        "loss_mask": {"decoder_ce": True},
        "target_token_len": 1,
        "standalone_projection_source": {
            "projection_mode": "stage11238_fresh_multilingual_verifier_constraint",
            "source_row_id": candidate.get("source_row_id"),
            "source_root_id": candidate.get("source_root_id"),
            "gold_value": "verifier_and_test_constraint",
            "gold_label": target_label,
            "opaque_options": options,
            "evidence_facts": evidence_facts,
            "candidate_change_surface_paths": candidate_paths,
            "verifier_and_test_constraint_paths": verifier_paths,
            "symptom_or_call_path_analogue_paths": symptom_paths,
        },
        "anti_cheat": {
            "fresh_root_disjoint_source": True,
            "explicit_selected_test_ledger": True,
            "deterministic_option_shuffle": True,
            "opaque_labels": True,
            "target_label_not_visible_pre_options": True,
            "candidate_verifier_path_overlap_rejected": True,
            "same_surface_eval_admissible": split != "train",
            "train_support_only": split == "train",
        },
    }


def choose_splits(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_repos: set[str] = set()
    for item in sorted(candidates, key=lambda x: (-float(x.get("quality_score") or 0.0), str(x.get("repo_family") or ""), str(x.get("source_row_id") or ""))):
        repo = str(item.get("repo_family") or "")
        # Cap per repo so Python volume does not become repeated family memorization.
        if sum(1 for rows in by_lang.values() for row in rows if row.get("repo_family") == repo) >= 2:
            continue
        by_lang[str(item.get("language_family") or "unknown")].append(item)
        seen_repos.add(repo)
    train: list[dict[str, Any]] = []
    validation: list[dict[str, Any]] = []
    strict: list[dict[str, Any]] = []
    quotas = {
        "python": {"strict": 8, "validation": 8, "train": 64},
        "rust": {"strict": 1, "validation": 0, "train": 1},
        "web_js_ts_html": {"strict": 2, "validation": 1, "train": 4},
    }
    for lang, rows in by_lang.items():
        q = quotas.get(lang, {"strict": 0, "validation": 0, "train": len(rows)})
        strict.extend(rows[: q["strict"]])
        validation.extend(rows[q["strict"] : q["strict"] + q["validation"]])
        train.extend(rows[q["strict"] + q["validation"] : q["strict"] + q["validation"] + q["train"]])
    return train, validation, strict


def root_set(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("root_id") or row.get("source_root_id") or row.get("row_id") or "") for row in rows}


def main() -> None:
    inventory = load_json(INVENTORY_SUMMARY)
    source_candidates = [row for row in load_jsonl(CANDIDATES) if row.get("admission_ready")]
    train_src, val_src, strict_src = choose_splits(source_candidates)
    train_rows = [make_row(row, split="train", ordinal=i) for i, row in enumerate(train_src)]
    val_rows = [make_row(row, split="validation", ordinal=i) for i, row in enumerate(val_src)]
    strict_rows = [make_row(row, split="strict_eval", ordinal=i) for i, row in enumerate(strict_src)]
    blocked = []
    roots = {"train": root_set(train_rows), "validation": root_set(val_rows), "strict": root_set(strict_rows)}
    overlaps = {
        "train_validation": sorted(roots["train"] & roots["validation"]),
        "train_strict": sorted(roots["train"] & roots["strict"]),
        "validation_strict": sorted(roots["validation"] & roots["strict"]),
    }
    if any(overlaps.values()):
        blocked.append({"reason": "root_split_overlap", "overlaps": overlaps})
    counts_by_split_lang = {
        split: dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in rows).items()))
        for split, rows in [("train", train_rows), ("validation", val_rows), ("strict", strict_rows)]
    }
    c_cpp_gap = {
        "ready_c_cpp_candidates": (inventory.get("counts") or {}).get("ready_by_language", {}).get("c_cpp", 0),
        "blocked_c_cpp_reason": "inventory found no clean C/C++ candidates; available C/C++ rows are path-overlap or already-consumed cuembed roots",
    }
    passed = bool(train_rows) and bool(strict_rows) and not blocked
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": passed,
        "decision": "fresh_multilingual_verifier_constraint_package_ready" if passed else "fresh_multilingual_verifier_constraint_package_blocked",
        "counts": {
            "train_rows": len(train_rows),
            "validation_rows": len(val_rows),
            "strict_rows": len(strict_rows),
            "by_split_language": counts_by_split_lang,
            "source_candidates": len(source_candidates),
            "root_overlaps": overlaps,
            "c_cpp_gap": c_cpp_gap,
        },
        "quality_gates": {
            "root_split_disjoint": not any(overlaps.values()),
            "all_rows_gold_verifier_constraint": all((row.get("standalone_projection_source") or {}).get("gold_value") == "verifier_and_test_constraint" for row in train_rows + val_rows + strict_rows),
            "all_rows_have_four_options": all(len(row.get("opaque_options") or []) == 4 for row in train_rows + val_rows + strict_rows),
            "all_rows_have_concrete_facts": all(bool((row.get("standalone_projection_source") or {}).get("evidence_facts")) for row in train_rows + val_rows + strict_rows),
            "c_cpp_supply_gap_recorded": c_cpp_gap["ready_c_cpp_candidates"] == 0,
        },
        "blocked": blocked,
        "source_artifacts": {"candidates": rel(CANDIDATES), "inventory_summary": rel(INVENTORY_SUMMARY)},
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_jsonl": rel(TRAIN_JSONL),
            "validation_jsonl": rel(VALIDATION_JSONL),
            "strict_jsonl": rel(STRICT_JSONL),
            "blocked_jsonl": rel(BLOCKED_JSONL),
        },
    }
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, val_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(BLOCKED_JSONL, blocked)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
