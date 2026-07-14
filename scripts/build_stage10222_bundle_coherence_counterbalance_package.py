#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10222
NAME = "stage10222_bundle_coherence_counterbalance_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
EVAL_JSONL = OUT_DIR / "agentkernel_lite_encdec_eval.jsonl"
PACKAGE_JSON = OUT_DIR / "bundle_coherence_counterbalance_package.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
BASE_PACKAGE = ROOT / "runs/local/artifacts/stage10213_python_contrast_counterbalance_package/python_contrast_counterbalance_package.json"
CHOICE_LABELS = list("ABCDEFGHJKLMNOPQRSTUVWXYZ")

CONTRAST_SPECS = [
    {
        "name": "c_cpp_abstain_vs_singletons",
        "language_family": "c_cpp",
        "task_type": "abstention_insufficient_evidence",
        "gold_value": "ABSTAIN_INSUFFICIENT_EVIDENCE",
        "mode": "gold_vs_each_other",
    },
    {
        "name": "web_evidence_candidate_vs_others",
        "language_family": "web_js_ts_html",
        "task_type": "evidence_citation",
        "gold_value": "candidate_change_surface",
        "mode": "gold_vs_each_other",
    },
    {
        "name": "web_symptom_main_vs_others",
        "language_family": "web_js_ts_html",
        "task_type": "symptom_localization",
        "gold_value": "src/main.js",
        "mode": "gold_vs_each_other",
    },
    {
        "name": "web_minfix_main_vs_others",
        "language_family": "web_js_ts_html",
        "task_type": "minimal_fix_selection",
        "gold_value": "src/main.js",
        "mode": "gold_vs_each_other",
    },
    {
        "name": "web_patch_main_vs_others",
        "language_family": "web_js_ts_html",
        "task_type": "patch_impact",
        "gold_value": "src/main.js",
        "mode": "gold_vs_each_other",
    },
    {
        "name": "python_evidence_verifier_vs_others",
        "language_family": "python",
        "task_type": "evidence_citation",
        "gold_value": "verifier_and_test_constraint",
        "mode": "gold_vs_each_other",
    },
    {
        "name": "rust_evidence_candidate_vs_others",
        "language_family": "rust",
        "task_type": "evidence_citation",
        "gold_value": "candidate_change_surface",
        "mode": "gold_vs_each_other",
    },
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_order(values: list[str], seed: str) -> list[str]:
    return sorted(values, key=lambda value: hashlib.sha256(f"{seed}::{value}".encode("utf-8")).hexdigest())


def rebuild_prompt(prompt: str, options: list[dict[str, str]]) -> str:
    if "\nOptions:\n" not in prompt or "\nAnswer:\n" not in prompt:
        raise ValueError("compact_prompt_missing_options_block")
    prefix, rest = prompt.split("\nOptions:\n", 1)
    _, suffix = rest.split("\nAnswer:\n", 1)
    option_lines = "\n".join(f"{row['label']}. {row['value']}" for row in options)
    return prefix + "\nOptions:\n" + option_lines + "\nAnswer:\n" + suffix


def label_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get("target_text") or "")
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def matches_spec(row: dict[str, Any], spec: dict[str, Any]) -> bool:
    source = row.get("standalone_projection_source") or {}
    if str(row.get("split") or "") != "train":
        return False
    if str(row.get("language_family") or "") != str(spec["language_family"]):
        return False
    if str(row.get("task_type") or "") != str(spec["task_type"]):
        return False
    if str(source.get("gold_value") or "") != str(spec.get("gold_value") or ""):
        return False
    options = [str(opt.get("value") or "") for opt in source.get("opaque_options") or [] if isinstance(opt, dict)]
    return spec["gold_value"] in options and len(options) >= 2


def first_rows_by_source(rows: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    matched = [row for row in rows if matches_spec(row, spec)]
    by_source: dict[str, dict[str, Any]] = {}
    for row in matched:
        source_row_id = str(row.get("source_row_id") or row.get("row_id") or "")
        current = by_source.get(source_row_id)
        if current is None or str(row.get("row_id") or "") < str(current.get("row_id") or ""):
            by_source[source_row_id] = row
    return [by_source[key] for key in sorted(by_source)]


def build_contrast_rows(base_row: dict[str, Any], spec: dict[str, Any]) -> list[dict[str, Any]]:
    base_source = dict(base_row.get("standalone_projection_source") or {})
    gold_value = str(base_source.get("gold_value") or "")
    all_values = [str(opt.get("value") or "") for opt in base_source.get("opaque_options") or [] if isinstance(opt, dict)]
    other_values = [v for v in all_values if v and v != gold_value]
    rows: list[dict[str, Any]] = []
    for other_index, other_value in enumerate(other_values):
        contrast_values = [gold_value, other_value]
        seed = f"{base_row.get('source_row_id') or base_row.get('row_id')}::{spec['name']}::{other_value}"
        canonical = stable_order(contrast_values, seed)
        reverse = list(reversed(canonical))
        unique_orders: list[list[str]] = []
        for order in [canonical, reverse]:
            if order not in unique_orders:
                unique_orders.append(order)
        for order_index, ordered_values in enumerate(unique_orders):
            options = [{"label": CHOICE_LABELS[i], "value": value} for i, value in enumerate(ordered_values)]
            label_by_value = {option["value"]: option["label"] for option in options}
            target = label_by_value[gold_value]
            row = dict(base_row)
            row["row_id"] = f"{base_row.get('row_id')}::contrast::{spec['name']}::{other_index:02d}::{order_index:02d}"
            row["semantic_key"] = f"{base_row.get('semantic_key')}::contrast::{spec['name']}::{other_index:02d}::{order_index:02d}"
            row["query_text"] = f"{base_row.get('query_text')}::contrast::{spec['name']}::{other_index:02d}::{order_index:02d}"
            row["prompt_text"] = rebuild_prompt(str(base_row.get("prompt_text") or ""), options)
            row["input_text"] = row["prompt_text"]
            row["target_text"] = target
            row["decoder_text"] = target
            row["target_token_len"] = len(target.encode("utf-8"))
            anti_cheat = dict(row.get("anti_cheat") or {})
            anti_cheat.update({
                "targeted_contrast_row": True,
                "bundle_coherence_counterbalance": True,
                "train_only_augmentation": True,
                "derived_from_train_row": True,
                "strict_eval_unchanged": True,
            })
            row["anti_cheat"] = anti_cheat
            source = dict(base_source)
            source["opaque_options"] = options
            source["contrast_family"] = spec["name"]
            source["contrast_values"] = ordered_values
            source["contrast_index"] = order_index
            source["contrast_source_row_id"] = str(base_row.get("row_id") or "")
            source["contrast_cardinality"] = len(options)
            source["contrast_focus_other"] = other_value
            row["standalone_projection_source"] = source
            rows.append(row)
    return rows


def build_package() -> dict[str, Any]:
    base_package = load_json(BASE_PACKAGE)
    train_rows = load_jsonl(ROOT / str(base_package.get("train_dataset_path") or ""))
    eval_rows = load_jsonl(ROOT / str(base_package.get("eval_dataset_path") or ""))
    augmented_rows: list[dict[str, Any]] = []
    augmentation_manifest: list[dict[str, Any]] = []
    for spec in CONTRAST_SPECS:
        selected = first_rows_by_source(train_rows, spec)
        produced = 0
        source_row_ids: list[str] = []
        for row in selected:
            built = build_contrast_rows(row, spec)
            augmented_rows.extend(built)
            produced += len(built)
            source_row_ids.append(str(row.get("source_row_id") or row.get("row_id") or ""))
        augmentation_manifest.append({
            "contrast_family": spec["name"],
            "selected_train_source_rows": len(selected),
            "augmented_rows": produced,
            "source_row_ids": source_row_ids,
            "gold_value": spec["gold_value"],
        })
    final_train_rows = train_rows + augmented_rows
    write_jsonl(TRAIN_JSONL, final_train_rows)
    write_jsonl(EVAL_JSONL, eval_rows)
    metrics = {
        "base_train_rows": len(train_rows),
        "base_strict_eval_rows": len(eval_rows),
        "augmented_train_rows": len(augmented_rows),
        "final_train_rows": len(final_train_rows),
        "final_strict_eval_rows": len(eval_rows),
        "train_label_counts": label_counts(final_train_rows),
        "strict_eval_label_counts": label_counts(eval_rows),
    }
    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "source_package": display(BASE_PACKAGE),
        "passed": bool(final_train_rows) and bool(eval_rows) and bool(augmented_rows),
        "metrics": metrics,
        "augmentation_manifest": augmentation_manifest,
        "unsupported_reviewed_failure_families": [
            "python::verifier_outcome lacks honest multi-option train support in the current compact package and stays evaluation-only",
        ],
        "train_dataset_path": display(TRAIN_JSONL),
        "eval_dataset_path": display(EVAL_JSONL),
        "fit_for": {
            "standalone_decoder_ce_training": True,
            "full_product_harness_training": False,
            "expert_maintainer_primary_score": False,
            "compact_bounded_auxiliary_projection_only": True,
        },
        "required_honesty_gates": [
            "strict eval rows are copied unchanged from stage10213, stage10200, and stage10149",
            "all bundle-coherence counterbalance rows derive only from train split rows",
            "unsupported reviewed failure families remain evaluation-only and are not fabricated into train",
            "stage10142 standalone decoder contract audit remains binding for post-training score claims",
        ],
    }
    write_json(PACKAGE_JSON, package)
    write_json(SUMMARY, {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": package["passed"],
        "package": display(PACKAGE_JSON),
        "metrics": metrics,
        "augmentation_manifest": augmentation_manifest,
        "unsupported_reviewed_failure_families": package["unsupported_reviewed_failure_families"],
    })
    return package


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    package = build_package()
    print(json.dumps({
        "stage": STAGE,
        "passed": package["passed"],
        "package": display(PACKAGE_JSON),
        "metrics": package["metrics"],
        "augmentation_manifest": package["augmentation_manifest"],
        "unsupported_reviewed_failure_families": package["unsupported_reviewed_failure_families"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
