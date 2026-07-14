#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10247
NAME = "stage10247_weakness_counterbalance_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
EVAL_JSONL = OUT_DIR / "agentkernel_lite_encdec_eval.jsonl"
PACKAGE_JSON = OUT_DIR / "weakness_counterbalance_package.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
BASE_PACKAGE = ROOT / "runs/local/artifacts/stage10149_v27_standalone_compact_permutation_balanced_package/standalone_compact_permutation_balanced_package.json"
SOURCE_PAYLOAD = ROOT / "runs/local/artifacts/stage10240_admitted_projection_runtime_payload_successor/admitted_projection_runtime_payload_successor.json"
SOURCE_SUMMARY = ROOT / "runs/local/artifacts/stage10242_admitted_projection_runtime_successor_multilingual_cuda/first_wave_bundle_inference_summary.json"

RULES = [
    {"name": "python_evidence", "language_family": "python", "task_type": "evidence_citation", "gold_value": "verifier_and_test_constraint"},
    {"name": "python_verifier", "language_family": "python", "task_type": "verifier_outcome"},
    {"name": "python_symptom", "language_family": "python", "task_type": "symptom_localization"},
    {"name": "python_patch", "language_family": "python", "task_type": "patch_impact"},
    {"name": "python_minfix", "language_family": "python", "task_type": "minimal_fix_selection"},
    {"name": "rust_evidence", "language_family": "rust", "task_type": "evidence_citation"},
    {"name": "cpp_abstain", "language_family": "c_cpp", "task_type": "abstention_insufficient_evidence", "gold_value": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    {"name": "web_evidence", "language_family": "web_js_ts_html", "task_type": "evidence_citation"},
    {"name": "web_symptom", "language_family": "web_js_ts_html", "task_type": "symptom_localization"},
    {"name": "web_patch", "language_family": "web_js_ts_html", "task_type": "patch_impact"},
    {"name": "web_minfix", "language_family": "web_js_ts_html", "task_type": "minimal_fix_selection"},
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


def root_key(row_id: str, task_type: str) -> str:
    marker = f"::{task_type}::compact_bounded"
    if marker in row_id:
        return row_id.split(marker, 1)[0]
    return row_id


def matches_rule(row: dict[str, Any], rule: dict[str, Any]) -> bool:
    if str(row.get("split") or "") != "train":
        return False
    if str(row.get("language_family") or "") != str(rule["language_family"]):
        return False
    if str(row.get("task_type") or "") != str(rule["task_type"]):
        return False
    source = row.get("standalone_projection_source") or {}
    gold_value = str(source.get("gold_value") or "")
    wanted_gold = str(rule.get("gold_value") or "")
    if wanted_gold and gold_value != wanted_gold:
        return False
    return True


def normalize_probe_row_schema(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    target_text = str(out.get("target_text") or "")
    out["decoder_text"] = target_text
    out["target_token_len"] = len(target_text.encode("utf-8"))
    out["loss_mask"] = {"decoder_ce": True}
    out["disable_losses"] = []
    out["expected_enabled_loss"] = "decoder_ce"
    out["authority"] = dict(out.get("authority") or {})
    out["source_row_id"] = str(out.get("source_row_id") or out.get("row_id") or "")
    out["source_bundle_id"] = str(out.get("source_bundle_id") or out.get("bundle_id") or "")
    out["source_stage"] = int(out.get("source_stage") or 10240)
    out["source_skill_area"] = str(out.get("source_skill_area") or out.get("surface") or "edit_localization")
    return out


def augment_train_row(row: dict[str, Any], rule_name: str) -> dict[str, Any]:
    out = normalize_probe_row_schema(row)
    out["row_id"] = f"{row.get('row_id')}::weakness::{rule_name}"
    out["semantic_key"] = f"{row.get('semantic_key') or row.get('row_id')}::weakness::{rule_name}"
    anti = dict(out.get("anti_cheat") or {})
    anti.update({
        "weakness_counterbalance_train_only": True,
        "derived_from_disjoint_train_root": True,
        "exact_stage10242_miss_rows_heldout": True,
        "not_for_primary_maintainer_claim": True,
    })
    out["anti_cheat"] = anti
    source = dict(out.get("standalone_projection_source") or {})
    source["weakness_counterbalance_rule"] = rule_name
    source["weakness_counterbalance_stage"] = STAGE
    out["standalone_projection_source"] = source
    out["split"] = "train"
    return out


def build_package() -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    source_payload = load_json(SOURCE_PAYLOAD)
    base_package = load_json(BASE_PACKAGE)
    base_train_rows = load_jsonl(ROOT / str(base_package.get("train_dataset_path") or ""))

    eval_lookup: dict[str, dict[str, Any]] = {}
    for run in source_payload.get("runs") or []:
        if not isinstance(run, dict):
            continue
        task_pack = run.get("task_pack") if isinstance(run.get("task_pack"), dict) else {}
        for row in task_pack.get("rows") or []:
            if isinstance(row, dict):
                eval_lookup[str(row.get("row_id") or "")] = row

    holdout_rows: list[dict[str, Any]] = []
    holdout_root_keys: set[str] = set()
    missed_rule_names: set[str] = set()
    missed_row_ids: set[str] = set()
    missing_eval_rows: list[str] = []
    for result in source_summary.get("results") or []:
        if not isinstance(result, dict):
            continue
        pred_path = ROOT / str(result.get("adapter_payload") or "")
        pred_path = pred_path.with_name("bundle_predictions.json")
        preds = load_json(pred_path)
        for row in preds.get("hundred_m") or []:
            if not isinstance(row, dict) or row.get("correct") is not False:
                continue
            row_id = str(row.get("row_id") or "")
            base = eval_lookup.get(row_id)
            if base is None:
                missing_eval_rows.append(row_id)
                continue
            if row_id in missed_row_ids:
                continue
            missed_row_ids.add(row_id)
            holdout = normalize_probe_row_schema(base)
            holdout["split"] = "strict_eval"
            anti = dict(holdout.get("anti_cheat") or {})
            anti.update({
                "weakness_counterbalance_holdout_only": True,
                "exact_stage10242_miss_row": True,
                "train_excluded_by_root": True,
            })
            holdout["anti_cheat"] = anti
            source = dict(holdout.get("standalone_projection_source") or {})
            source["weakness_holdout_stage"] = STAGE
            holdout["standalone_projection_source"] = source
            holdout_rows.append(holdout)
            task_type = str(base.get("task_type") or "")
            holdout_root_keys.add(root_key(row_id, task_type))
            for rule in RULES:
                if str(base.get("language_family") or "") == str(rule["language_family"]) and str(base.get("task_type") or "") == str(rule["task_type"]):
                    missed_rule_names.add(str(rule["name"]))

    selected_train_rows: list[dict[str, Any]] = []
    selected_train_ids: set[str] = set()
    rule_counts: dict[str, int] = {str(rule['name']): 0 for rule in RULES}
    uncovered_rules: list[str] = []
    for rule in RULES:
        matching = []
        for row in base_train_rows:
            if not matches_rule(row, rule):
                continue
            row_id = str(row.get("row_id") or "")
            row_root = root_key(row_id, str(row.get("task_type") or ""))
            if row_root in holdout_root_keys:
                continue
            matching.append(row)
        if matching:
            for row in matching:
                row_id = str(row.get("row_id") or "")
                if row_id in selected_train_ids:
                    continue
                selected_train_ids.add(row_id)
                selected_train_rows.append(augment_train_row(row, str(rule["name"])))
                rule_counts[str(rule["name"])] += 1
        else:
            uncovered_rules.append(str(rule["name"]))

    language_counts_train: dict[str, int] = {}
    for row in selected_train_rows:
        lang = str(row.get("language_family") or "")
        language_counts_train[lang] = language_counts_train.get(lang, 0) + 1
    language_counts_eval: dict[str, int] = {}
    for row in holdout_rows:
        lang = str(row.get("language_family") or "")
        language_counts_eval[lang] = language_counts_eval.get(lang, 0) + 1

    write_jsonl(TRAIN_JSONL, selected_train_rows)
    write_jsonl(EVAL_JSONL, holdout_rows)
    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(selected_train_rows) and bool(holdout_rows) and not missing_eval_rows,
        "base_package": display(BASE_PACKAGE),
        "source_payload": display(SOURCE_PAYLOAD),
        "source_summary": display(SOURCE_SUMMARY),
        "train_dataset_path": display(TRAIN_JSONL),
        "eval_dataset_path": display(EVAL_JSONL),
        "claim_scope": "auxiliary weakness-repair package only; exact stage10242 misses remain holdout rows and do not become train rows",
        "required_honesty_gates": [
            "exact stage10242 miss rows remain strict-eval holdout only",
            "train rows must come only from preexisting train split data",
            "rows sharing the same root key as holdout misses are excluded from train",
            "package is support-only and does not upgrade the maintainer-grade claim by itself",
        ],
        "metrics": {
            "train_rows": len(selected_train_rows),
            "holdout_rows": len(holdout_rows),
            "train_language_counts": dict(sorted(language_counts_train.items())),
            "holdout_language_counts": dict(sorted(language_counts_eval.items())),
            "rule_counts": dict(sorted(rule_counts.items())),
            "holdout_root_count": len(holdout_root_keys),
            "missed_rule_count": len(missed_rule_names),
            "uncovered_rule_count": len(uncovered_rules),
        },
        "uncovered_rules": uncovered_rules,
        "missing_eval_rows": missing_eval_rows,
    }
    write_json(PACKAGE_JSON, package)
    write_json(SUMMARY, {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": package["passed"],
        "package": display(PACKAGE_JSON),
        "train_dataset_path": display(TRAIN_JSONL),
        "eval_dataset_path": display(EVAL_JSONL),
        "metrics": package["metrics"],
        "uncovered_rules": uncovered_rules,
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
        "uncovered_rules": package["uncovered_rules"],
    }, indent=2, sort_keys=True))
    if not package["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
