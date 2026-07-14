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
STAGE = 11243
NAME = "stage11243_balanced_evidence_role_grounding_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "balanced_evidence_role_grounding_package.json"
TRAIN_JSONL = OUT_DIR / "balanced_evidence_role_grounding_train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "balanced_evidence_role_grounding_validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "balanced_evidence_role_grounding_strict_rows.jsonl"
BLOCKED_JSONL = OUT_DIR / "balanced_evidence_role_grounding_blocked_rows.jsonl"

CANDIDATES = ARTIFACTS / "stage11237_multilingual_verifier_constraint_source_inventory/verifier_constraint_source_candidates.jsonl"
INVENTORY_SUMMARY = ARTIFACTS / "stage11237_multilingual_verifier_constraint_source_inventory/multilingual_verifier_constraint_source_inventory.json"
CURRENT_VALIDATION = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_validation.jsonl"
CURRENT_STRICT = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL_BANK = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"

ROLE_VALUES = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
    "external_analogue_reference",
    "algorithmic_background_reference",
]
TARGET_ROLES = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
]
ROLE_QUESTIONS = {
    "candidate_change_surface": "Which option identifies the concrete code, configuration, or implementation surface that changed?",
    "verifier_and_test_constraint": "Which option identifies the selected test, verifier, assertion, or execution constraint that decides whether the maintenance change is correct?",
    "symptom_or_call_path_analogue": "Which option identifies the failure symptom, call path, runtime observation, or user-visible behavior context?",
}
LABELS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("source_row_id") or row.get("row_id") or "")


def path_preview(paths: list[str], limit: int = 4) -> str:
    clean = [str(path) for path in paths if str(path).strip()]
    if not clean:
        return "not supplied"
    suffix = f" (+{len(clean) - limit} more)" if len(clean) > limit else ""
    return ", ".join(clean[:limit]) + suffix


def stable_options(seed: str) -> list[dict[str, str]]:
    values = sorted(ROLE_VALUES, key=lambda value: hashlib.sha256(f"{seed}::{value}".encode()).hexdigest())
    return [{"label": LABELS[idx], "value": value} for idx, value in enumerate(values)]


def evidence_facts(candidate: dict[str, Any]) -> dict[str, str]:
    candidate_paths = candidate.get("candidate_change_surface_paths") or []
    verifier_paths = candidate.get("verifier_and_test_constraint_paths") or []
    symptom_paths = candidate.get("symptom_or_call_path_analogue_paths") or []
    key_symbols = candidate.get("key_symbols") or []
    nearby_paths = list(dict.fromkeys([str(x) for x in key_symbols[:8]] + [str(x) for x in symptom_paths[:2]]))
    return {
        "candidate_change_surface": f"changed surface paths: {path_preview(candidate_paths)}",
        "verifier_and_test_constraint": f"selected verifier/test paths: {path_preview(verifier_paths)}; route={candidate.get('test_selection_route') or 'PASS_TARGETED_TEST_SELECTION'}",
        "symptom_or_call_path_analogue": f"symptom/call-path/runtime context paths: {path_preview(symptom_paths)}",
        "nearby_definition_or_usage_context": f"nearby definitions or symbol context: {path_preview(nearby_paths)}",
        "external_analogue_reference": "no external analogue evidence is supplied in this compact root packet",
        "algorithmic_background_reference": "no standalone algorithmic-background reference is supplied in this compact root packet",
    }


def visible_lines(facts: dict[str, str]) -> list[str]:
    # Keep the role key available for audit and fact-text scorer variants, while the product scorer still sees role-valued options.
    return [f"{role}: {facts[role]}" for role in ROLE_VALUES]


def make_row(candidate: dict[str, Any], *, split: str, target_role: str, ordinal: int) -> dict[str, Any]:
    source = str(candidate.get("source_row_id") or candidate.get("root_id") or "missing")
    row_id = f"stage11243::{split}::{source}::{target_role}::{ordinal:04d}"
    options = stable_options(row_id)
    label_by_value = {option["value"]: option["label"] for option in options}
    target_label = label_by_value[target_role]
    facts = evidence_facts(candidate)
    prompt = (
        f"Language: {candidate.get('language_family')}\n"
        "Perspective: evidence_citation\n"
        "Task: choose the option whose evidence role is requested by the maintainer question. Use the visible facts; do not use option order.\n"
        f"Maintainer question: {ROLE_QUESTIONS[target_role]}\n"
        f"Repository family: {candidate.get('repo_family')}\n"
        f"Execution route: {candidate.get('execution_route') or 'unknown'}\n\n"
        "Visible evidence ledger:\n"
        f"E01. {facts['candidate_change_surface']}\n"
        f"E02. {facts['verifier_and_test_constraint']}\n"
        f"E03. {facts['symptom_or_call_path_analogue']}\n"
        f"E04. {facts['nearby_definition_or_usage_context']}\n"
        f"E05. {facts['external_analogue_reference']}\n"
        f"E06. {facts['algorithmic_background_reference']}\n\n"
        "Options:\n"
        + "\n".join(f"{option['label']}. {option['value']}" for option in options)
        + "\nAnswer:"
    )
    row = {
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
        "evidence_role_grounding_target": target_role,
        "split": split,
        "package_split": split,
        "prompt_text": prompt,
        "input_text": prompt,
        "target": target_label,
        "target_label": target_label,
        "target_text": target_label,
        "decoder_text": target_label,
        "bounded_choice_target_label": target_label,
        "semantic_target_value": target_role,
        "gold_value": target_role,
        "opaque_options": options,
        "expected_enabled_loss": "decoder_ce",
        "loss_mask": {"decoder_ce": True},
        "target_token_len": 1,
        "standalone_projection_source": {
            "projection_mode": "stage11243_balanced_evidence_role_grounding",
            "source_row_id": candidate.get("source_row_id"),
            "source_root_id": candidate.get("source_root_id"),
            "gold_value": target_role,
            "gold_label": target_label,
            "opaque_options": options,
            "evidence_facts": facts,
            "visible_evidence_lines": visible_lines(facts),
            "candidate_change_surface_paths": candidate.get("candidate_change_surface_paths") or [],
            "verifier_and_test_constraint_paths": candidate.get("verifier_and_test_constraint_paths") or [],
            "symptom_or_call_path_analogue_paths": candidate.get("symptom_or_call_path_analogue_paths") or [],
        },
        "anti_cheat": {
            "fresh_root_disjoint_source": True,
            "explicit_selected_test_ledger": True,
            "deterministic_option_shuffle": True,
            "opaque_labels": True,
            "target_label_not_visible_pre_options": True,
            "candidate_verifier_path_overlap_rejected": True,
            "balanced_role_projection": True,
            "same_surface_eval_admissible": split != "train",
            "train_support_only": split == "train",
        },
    }
    return row


def split_candidates(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    protected = {root_key(row) for row in load_jsonl(CURRENT_VALIDATION) + load_jsonl(CURRENT_STRICT) + load_jsonl(RESIDUAL_BANK)}
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    repo_counts: Counter[str] = Counter()
    blocked: list[dict[str, Any]] = []
    for item in sorted(candidates, key=lambda x: (-float(x.get("quality_score") or 0.0), str(x.get("repo_family") or ""), str(x.get("source_row_id") or ""))):
        rk = root_key(item)
        if rk in protected:
            blocked.append({"source_row_id": item.get("source_row_id"), "reason": "protected_root_overlap", "root_id": rk})
            continue
        repo = str(item.get("repo_family") or "unknown")
        lang = str(item.get("language_family") or "unknown")
        cap = 6 if lang == "web_js_ts_html" else 2
        if repo_counts[repo] >= cap:
            continue
        repo_counts[repo] += 1
        by_lang[lang].append(item)

    quotas = {
        "python": {"strict": 8, "validation": 8, "train": 48},
        "rust": {"strict": 1, "validation": 0, "train": 1},
        "web_js_ts_html": {"strict": 2, "validation": 1, "train": 3},
    }
    train: list[dict[str, Any]] = []
    validation: list[dict[str, Any]] = []
    strict: list[dict[str, Any]] = []
    for lang, rows in sorted(by_lang.items()):
        q = quotas.get(lang, {"strict": 0, "validation": 0, "train": len(rows)})
        strict.extend(rows[: q["strict"]])
        validation.extend(rows[q["strict"] : q["strict"] + q["validation"]])
        train.extend(rows[q["strict"] + q["validation"] : q["strict"] + q["validation"] + q["train"]])
    return train, validation, strict, blocked


def root_set(rows: list[dict[str, Any]]) -> set[str]:
    return {root_key(row) for row in rows}


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def main() -> None:
    inventory = load_json(INVENTORY_SUMMARY)
    candidates = [row for row in load_jsonl(CANDIDATES) if row.get("admission_ready")]
    train_src, val_src, strict_src, blocked = split_candidates(candidates)

    train_rows: list[dict[str, Any]] = []
    val_rows: list[dict[str, Any]] = []
    strict_rows: list[dict[str, Any]] = []
    ordinal = 0
    for split, src_rows, out_rows in (("train", train_src, train_rows), ("validation", val_src, val_rows), ("strict_eval", strict_src, strict_rows)):
        for src in src_rows:
            for role in TARGET_ROLES:
                out_rows.append(make_row(src, split=split, target_role=role, ordinal=ordinal))
                ordinal += 1

    roots = {"train": root_set(train_rows), "validation": root_set(val_rows), "strict": root_set(strict_rows)}
    overlaps = {
        "train_validation": sorted(roots["train"] & roots["validation"]),
        "train_strict": sorted(roots["train"] & roots["strict"]),
        "validation_strict": sorted(roots["validation"] & roots["strict"]),
    }
    role_counts = {split: count_by(rows, "semantic_target_value") for split, rows in (("train", train_rows), ("validation", val_rows), ("strict", strict_rows))}
    lang_counts = {split: count_by(rows, "language_family") for split, rows in (("train", train_rows), ("validation", val_rows), ("strict", strict_rows))}
    repo_split: dict[str, set[str]] = defaultdict(set)
    for split, rows in (("train", train_rows), ("validation", val_rows), ("strict", strict_rows)):
        for row in rows:
            repo_split[str(row.get("repo_family") or "unknown")].add(split)
    repo_overlaps = {repo: sorted(splits) for repo, splits in sorted(repo_split.items()) if len(splits) > 1}
    c_cpp_gap = {
        "ready_c_cpp_candidates": int(((inventory.get("counts") or {}).get("ready_by_language") or {}).get("c_cpp", 0)),
        "blocked_c_cpp_reason": "inventory found no clean C/C++ candidates; available C/C++ rows are path-overlap or already-consumed cuembed roots",
    }
    quality_gates = {
        "root_split_disjoint": not any(overlaps.values()),
        "role_balanced_train": len(set(role_counts["train"].values())) == 1 and set(role_counts["train"]) == set(TARGET_ROLES),
        "role_balanced_validation": len(set(role_counts["validation"].values())) == 1 and set(role_counts["validation"]) == set(TARGET_ROLES),
        "role_balanced_strict": len(set(role_counts["strict"].values())) == 1 and set(role_counts["strict"]) == set(TARGET_ROLES),
        "all_rows_have_six_options": all(len(row.get("opaque_options") or []) == 6 for row in train_rows + val_rows + strict_rows),
        "all_rows_have_concrete_facts": all(bool((row.get("standalone_projection_source") or {}).get("evidence_facts")) for row in train_rows + val_rows + strict_rows),
        "c_cpp_supply_gap_recorded": c_cpp_gap["ready_c_cpp_candidates"] == 0,
    }
    passed = all(quality_gates.values()) and bool(train_rows) and bool(strict_rows)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": passed,
        "decision": "balanced_evidence_role_grounding_package_ready" if passed else "balanced_evidence_role_grounding_package_blocked",
        "counts": {
            "source_candidates": len(candidates),
            "train_rows": len(train_rows),
            "validation_rows": len(val_rows),
            "strict_rows": len(strict_rows),
            "train_roots": len(root_set(train_rows)),
            "validation_roots": len(root_set(val_rows)),
            "strict_roots": len(root_set(strict_rows)),
            "by_split_language": lang_counts,
            "by_split_role": role_counts,
            "root_overlaps": overlaps,
            "repo_family_split_overlaps": repo_overlaps,
            "c_cpp_gap": c_cpp_gap,
        },
        "quality_gates": quality_gates,
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
