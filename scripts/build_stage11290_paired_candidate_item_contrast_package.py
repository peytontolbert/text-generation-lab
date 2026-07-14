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
STAGE = 11290
NAME = "stage11290_paired_candidate_item_contrast_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "paired_candidate_item_contrast_package.json"
TRAIN_JSONL = OUT_DIR / "paired_candidate_item_contrast_train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "paired_candidate_item_contrast_validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "paired_candidate_item_contrast_strict_rows.jsonl"

SOURCE_DIR = ARTIFACTS / "stage11285_candidate_only_evidence_judgment_package"
SOURCE_ROWS = {
    "train": SOURCE_DIR / "candidate_only_evidence_judgment_train_rows.jsonl",
    "validation": SOURCE_DIR / "candidate_only_evidence_judgment_validation_rows.jsonl",
    "strict_eval": SOURCE_DIR / "candidate_only_evidence_judgment_strict_rows.jsonl",
}

CODE_EXTS = (".py", ".rs", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".cu", ".cuh", ".js", ".ts", ".tsx", ".jsx", ".html", ".css")
LOW_SIGNAL_PATH_PARTS = ("readme", "docs/", "doc/", "test", "tests/", "benchmark", "bench", "example", "examples/")
OPTION_VALUES = ["candidate_change_surface", "verifier_and_test_constraint", "symptom_or_call_path_analogue", "background_context"]


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def stable_hash(text: str, n: int = 10) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


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


def is_impl_changed(row: dict[str, Any]) -> bool:
    source = row.get("standalone_projection_source") or {}
    path = str(source.get("source_chunk_path") or "").lower()
    return path.endswith(CODE_EXTS) and not any(part in path for part in LOW_SIGNAL_PATH_PARTS)


def options_for(seed: str) -> list[dict[str, str]]:
    vals = list(OPTION_VALUES)
    vals.sort(key=lambda value: stable_hash(f"{seed}::{value}"))
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return [{"label": labels[idx], "value": value} for idx, value in enumerate(vals)]


def convert_text(source_text: str) -> str:
    return source_text.replace("Evidence note: materialized source excerpt from the root evidence ledger.", "Evidence note: source-derived candidate item.")


def make_prompt(row: dict[str, Any], options: list[dict[str, str]]) -> str:
    source = row.get("standalone_projection_source") or {}
    evidence_text = convert_text(str(source.get("candidate_evidence_text") or ""))
    return "\n".join([
        f"Language: {row.get('language_family')}",
        "Perspective: evidence_citation",
        "Decision objective: choose the semantic role of the candidate evidence item.",
        "Classify the item itself. Do not infer from option order or hidden source metadata.",
        "",
        "Candidate evidence item:",
        evidence_text,
        "",
        "Options:",
        *[f"{opt['label']}. {opt['value']}" for opt in options],
        "Answer:",
    ])


def convert_row(row: dict[str, Any], split: str) -> dict[str, Any] | None:
    source = row.get("standalone_projection_source") or {}
    kind = source.get("candidate_evidence_kind")
    if kind == "changed":
        if not is_impl_changed(row):
            return None
        target_value = "candidate_change_surface"
    elif kind == "verifier":
        target_value = "verifier_and_test_constraint"
    else:
        return None
    seed = f"{row.get('root_id')}::{kind}::stage11290"
    options = options_for(seed)
    target_label = next(opt["label"] for opt in options if opt["value"] == target_value)
    prompt = make_prompt(row, options)
    out = dict(row)
    out.update({
        "row_id": str(row["row_id"]).replace("stage11285::", "stage11290::").replace(
            "::candidate_only_evidence_judgment::",
            "::paired_candidate_item_contrast::",
        ),
        "task_type": "evidence_citation",
        "surface": "maintainer_paired_candidate_item_evidence_citation_contrast",
        "split": split,
        "package_split": split,
        "input_text": prompt,
        "prompt_text": prompt,
        "decoder_text": target_label,
        "target_text": target_label,
        "bounded_choice_target_label": target_label,
        "semantic_target_value": target_value,
        "opaque_options": options,
        "strict_eval_eligible": split == "strict_eval",
        "train_support_only": split == "train",
        "preservation_exempt": split == "train",
    })
    sps = dict(source)
    sps.update({
        "gold_label": target_label,
        "gold_value": target_value,
        "opaque_options": options,
        "source_inventory_stage": "stage11290_paired_candidate_item_contrast",
        "contrast_target_value": target_value,
        "contrast_family": "candidate_change_surface_vs_verifier_and_test_constraint",
    })
    out["standalone_projection_source"] = sps
    anti = dict(out.get("anti_cheat") or {})
    anti.update({
        "paired_same_root_contrast": True,
        "legacy_evidence_citation_contrast_values": True,
        "implementation_changed_positive_required": kind == "changed",
    })
    out["anti_cheat"] = anti
    return out


def build_split(rows: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    by_root: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        kind = (row.get("standalone_projection_source") or {}).get("candidate_evidence_kind")
        by_root[str(row.get("root_id"))][str(kind)] = row
    out: list[dict[str, Any]] = []
    for root_id, grouped in sorted(by_root.items()):
        changed = grouped.get("changed")
        verifier = grouped.get("verifier")
        if not changed or not verifier or not is_impl_changed(changed):
            continue
        for row in (changed, verifier):
            converted = convert_row(row, split)
            if converted:
                out.append(converted)
    return out


def audit(rows_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_rows = [row for rows in rows_by_split.values() for row in rows]
    leaks = Counter()
    for row in all_rows:
        before = str(row.get("input_text") or "").split("Options:", 1)[0]
        if str(row.get("semantic_target_value") or "") in before:
            leaks["semantic_target_before_options"] += 1
        target_label = str(row.get("bounded_choice_target_label") or "")
        if f"\n{target_label}." in before or f" {target_label}. " in before:
            leaks["target_label_before_options"] += 1
    root_sets = {split: {str(row.get("root_id")) for row in rows} for split, rows in rows_by_split.items()}
    root_balance = {}
    for split, rows in rows_by_split.items():
        by_root: dict[str, Counter[str]] = defaultdict(Counter)
        for row in rows:
            by_root[str(row.get("root_id"))][str((row.get("standalone_projection_source") or {}).get("candidate_evidence_kind"))] += 1
        root_balance[split] = {
            "roots": len(by_root),
            "unpaired_roots": sorted(root for root, counts in by_root.items() if counts.get("changed") != 1 or counts.get("verifier") != 1),
        }
    return {
        "duplicate_row_ids": len(all_rows) - len({str(row.get("row_id")) for row in all_rows}),
        "leaks": dict(leaks),
        "root_overlap": {
            "train_validation": sorted(root_sets["train"] & root_sets["validation"]),
            "train_strict": sorted(root_sets["train"] & root_sets["strict_eval"]),
            "validation_strict": sorted(root_sets["validation"] & root_sets["strict_eval"]),
        },
        "root_balance": root_balance,
    }


def counts(rows_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for split, rows in rows_by_split.items():
        out[split] = {
            "rows": len(rows),
            "roots": len({str(row.get("root_id")) for row in rows}),
            "by_language": dict(Counter(str(row.get("language_family")) for row in rows)),
            "by_target": dict(Counter(str(row.get("semantic_target_value")) for row in rows)),
            "by_candidate_kind": dict(Counter(str((row.get("standalone_projection_source") or {}).get("candidate_evidence_kind")) for row in rows)),
        }
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows_by_split = {split: build_split(load_jsonl(path), split) for split, path in SOURCE_ROWS.items()}
    audit_card = audit(rows_by_split)
    count_card = counts(rows_by_split)
    passed = (
        audit_card["duplicate_row_ids"] == 0
        and not audit_card["leaks"]
        and not any(audit_card["root_overlap"].values())
        and all(not card["unpaired_roots"] for card in audit_card["root_balance"].values())
        and count_card["train"]["roots"] >= 20
        and count_card["validation"]["roots"] > 0
        and count_card["strict_eval"]["roots"] > 0
    )
    write_jsonl(TRAIN_JSONL, rows_by_split["train"])
    write_jsonl(VALIDATION_JSONL, rows_by_split["validation"])
    write_jsonl(STRICT_JSONL, rows_by_split["strict_eval"])
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": passed,
        "decision": "paired_candidate_item_contrast_package_ready" if passed else "paired_candidate_item_contrast_package_blocked",
        "rationale": "Keep only same-root changed/verifier evidence pairs where changed-source is an implementation-like file, then express targets as legacy evidence_citation contrast values so bounded-choice margin loss applies.",
        "counts": count_card,
        "audit": audit_card,
        "outputs": {
            "train_jsonl": rel(TRAIN_JSONL),
            "validation_jsonl": rel(VALIDATION_JSONL),
            "strict_jsonl": rel(STRICT_JSONL),
            "summary_json": rel(SUMMARY_JSON),
        },
        "source_artifacts": {
            "stage11285_package": rel(SOURCE_DIR / "candidate_only_evidence_judgment_package.json"),
            "stage11289_decision": "runs/local/artifacts/stage11289_candidate_only_evidence_decision/candidate_only_evidence_decision.json",
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
