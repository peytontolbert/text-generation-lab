#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10183
NAME = "stage10183_hybrid_web_surface_rebalanced_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
EVAL_JSONL = OUT_DIR / "agentkernel_lite_encdec_eval.jsonl"
PACKAGE_JSON = OUT_DIR / "hybrid_web_surface_rebalanced_package.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
SOURCE = ROOT / "runs/local/artifacts/stage10176_code_assist_web_replenishment_bundle/code_assist_web_replenishment_admitted_manifest.json"

BOUND_KINDS = {"candidate_path", "selected_test", "visible_evidence_key", "abstain"}
CHOICE_LABELS = list("ABCDEFGHJKLMNOPQRSTUVWXYZ")
WEB_EVAL_BUNDLE_SUBSTR = "index_html_f0be60dc44"
WEB_FRONTEND_TRAIN_BUNDLE_SUBSTR = "src_main_js_index_html_440e122a0f"
WEB_CODE_ASSIST_BUNDLE_SUBSTR = "stage10176::localsess_code_assist"
WEB_FRONTEND_DUPLICATE_PERSPECTIVES = {
    "symptom_localization",
    "patch_impact",
    "minimal_fix_selection",
}
WEB_CODE_ASSIST_ALLOWED_PERSPECTIVES = {
    "verifier_outcome",
    "abstention_insufficient_evidence",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def snippet(text: str, limit: int = 280) -> str:
    clean = " ".join(str(text).split())
    return clean if len(clean) <= limit else clean[: max(0, limit - 3)] + "..."


def deterministic_order(values: list[str], seed: str) -> list[str]:
    return sorted(values, key=lambda value: hashlib.sha256(f"{seed}::{value}".encode("utf-8")).hexdigest())


def contract_for(bundle: dict[str, Any], perspective: str) -> dict[str, Any]:
    for row in bundle.get("perspective_rows") or []:
        if isinstance(row, dict) and str(row.get("perspective") or "") == perspective:
            contract = row.get("prompt_contract")
            if isinstance(contract, dict):
                return contract
    return {}


def evidence_lines(bundle: dict[str, Any], visible_keys: list[str]) -> list[str]:
    evidence = bundle.get("maintainer_visible_evidence") if isinstance(bundle.get("maintainer_visible_evidence"), dict) else {}
    lines: list[str] = []
    for key in visible_keys:
        values = evidence.get(key)
        if not isinstance(values, list) or not values:
            continue
        first = values[0]
        if not isinstance(first, dict):
            continue
        path = str(first.get("path") or "")
        source_type = str(first.get("source_type") or "")
        text = snippet(str(first.get("text") or ""))
        prefix = key
        if path:
            prefix += f" [{path}]"
        elif source_type:
            prefix += f" [{source_type}]"
        lines.append(f"{prefix}: {text}")
    return lines[:4]


def build_option_values(*, answer_kind: str, gold_value: str, contract: dict[str, Any], gold: dict[str, Any]) -> list[str]:
    if answer_kind == "candidate_path":
        values = [str(v) for v in (gold.get("candidate_paths") or contract.get("candidate_paths") or []) if v]
    elif answer_kind == "selected_test":
        values = [str(v) for v in (gold.get("selected_tests") or contract.get("selected_tests") or []) if v]
    elif answer_kind == "visible_evidence_key":
        values = [str(v) for v in (gold.get("visible_evidence_keys") or contract.get("visible_evidence_keys") or []) if v]
    elif answer_kind == "abstain":
        values = [str(v) for v in (gold.get("candidate_paths") or contract.get("candidate_paths") or []) if v]
        if not values:
            values = [str(v) for v in (gold.get("selected_tests") or contract.get("selected_tests") or []) if v]
        if not values:
            values = [str(v) for v in (gold.get("visible_evidence_keys") or contract.get("visible_evidence_keys") or []) if v]
        values.append("ABSTAIN_INSUFFICIENT_EVIDENCE")
    else:
        values = [gold_value]
    deduped: list[str] = []
    seen = set()
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    if gold_value not in seen:
        deduped.append(gold_value)
    return deduped


def compile_prompt(bundle: dict[str, Any], gold: dict[str, Any], *, options: list[tuple[str, str]]) -> str:
    perspective = str(gold.get("perspective") or "")
    contract = contract_for(bundle, perspective)
    task = " ".join(str(contract.get("task") or "").split())
    visible_keys = [str(v) for v in contract.get("visible_evidence_keys") or [] if v]
    ev_lines = evidence_lines(bundle, visible_keys)
    opt_lines = [f"{label}. {value}" for label, value in options]
    parts = [
        f"Language: {bundle.get('language_family')}",
        f"Perspective: {perspective}",
        f"Task: {task}",
    ]
    if ev_lines:
        parts.append("Evidence:")
        parts.extend(ev_lines)
    parts.append("Options:")
    parts.extend(opt_lines)
    parts.append("Answer:")
    return "\n".join(parts) + "\n"


def compile_bounded_row(bundle: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any] | None:
    perspective = str(gold.get("perspective") or "")
    answer_kind = str(gold.get("gold_answer_kind") or "")
    gold_value = str(gold.get("gold_answer_value") or "")
    if answer_kind not in BOUND_KINDS:
        return None
    contract = contract_for(bundle, perspective)
    values = build_option_values(answer_kind=answer_kind, gold_value=gold_value, contract=contract, gold=gold)
    seed = f"compact::{bundle['bundle_id']}::{perspective}::{answer_kind}"
    ordered_values = deterministic_order(values, seed)
    if len(ordered_values) > len(CHOICE_LABELS):
        raise ValueError(f"too_many_options::{bundle['bundle_id']}::{perspective}")
    options = list(zip(CHOICE_LABELS[: len(ordered_values)], ordered_values))
    label_by_value = {value: label for label, value in options}
    prompt = compile_prompt(bundle, gold, options=options)
    return {
        "row_id": f"{bundle['bundle_id']}::{perspective}::compact_bounded",
        "bundle_id": bundle["bundle_id"],
        "language_family": bundle["language_family"],
        "task_type": perspective,
        "perspective": perspective,
        "prompt_text": prompt,
        "input_text": prompt,
        "query_text": f"compact_bounded::{bundle['language_family']}::{perspective}::{answer_kind}",
        "target_text": label_by_value[gold_value],
        "opaque_options": [{"label": label, "value": value} for label, value in options],
        "gold_value": gold_value,
        "original_answer_kind": answer_kind,
    }


def rotate_options(options: list[dict[str, Any]], shift: int) -> list[dict[str, str]]:
    values = [str(option.get("value") or "") for option in options]
    labels = [str(option.get("label") or "") for option in options]
    if not values or len(values) != len(labels):
        return []
    rotated_values = values[shift:] + values[:shift]
    return [{"label": label, "value": value} for label, value in zip(labels, rotated_values)]


def rebuild_prompt(prompt: str, options: list[dict[str, str]]) -> str:
    if "\nOptions:\n" not in prompt or "\nAnswer:\n" not in prompt:
        raise ValueError("compact_prompt_missing_options_block")
    prefix, rest = prompt.split("\nOptions:\n", 1)
    _, suffix = rest.split("\nAnswer:\n", 1)
    option_lines = "\n".join(f"{row['label']}. {row['value']}" for row in options)
    return prefix + "\nOptions:\n" + option_lines + "\nAnswer:\n" + suffix


def build_variant_rows(bundle: dict[str, Any], row: dict[str, Any], *, split: str, semantic_suffix: str = "") -> list[dict[str, Any]]:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    options = [option for option in (row.get("opaque_options") or []) if isinstance(option, dict)]
    gold_value = str(row.get("gold_value") or "")
    if not options or not gold_value:
        return []
    values = [str(option.get("value") or "") for option in options]
    if gold_value not in values:
        return []
    variants: list[dict[str, Any]] = []
    for shift in range(len(options)):
        rotated = rotate_options(options, shift)
        if not rotated:
            continue
        label_by_value = {str(option["value"]): str(option["label"]) for option in rotated}
        target = label_by_value[gold_value]
        variant_prompt = rebuild_prompt(prompt, rotated)
        suffix = f"{semantic_suffix}::perm_{shift:02d}" if semantic_suffix else f"perm_{shift:02d}"
        variants.append(
            {
                "row_id": f"{row.get('row_id')}::{suffix}",
                "language_family": bundle["language_family"],
                "route": "KEEP_BOUNDED_DECODER",
                "objective_family": "bounded_decoder_ce",
                "surface": "maintainer_bundle_compact_bounded_choice",
                "task_type": str(row.get("task_type") or row.get("perspective") or ""),
                "split": split,
                "prompt_text": variant_prompt,
                "input_text": variant_prompt,
                "query_text": str(row.get("query_text") or "") + f"::{suffix}",
                "target_text": target,
                "decoder_text": target,
                "target_token_len": len(target.encode("utf-8")),
                "loss_mask": {"decoder_ce": True},
                "expected_enabled_loss": "decoder_ce",
                "disable_losses": ["denoise_ce", "runtime_reward", "structured_aux"],
                "source_skill_area": "maintainer_bundle_compact_bounded_choice",
                "source_stage": STAGE,
                "source_row_id": str(row.get("row_id") or ""),
                "source_bundle_id": str(bundle.get("bundle_id") or ""),
                "semantic_key": f"maintainer_bundle_compact_bounded_perm::{bundle.get('bundle_id')}::{row.get('perspective')}::{suffix}",
                "anti_cheat": {
                    "opaque_labels": True,
                    "bundle_level_split_preserved": True,
                    "freeform_rows_excluded": True,
                    "compact_prompt_contract": True,
                    "permutation_balanced_labels": True,
                    "standalone_decoder_contract_gate_required": True,
                },
                "authority": {
                    "model_execution_authorized_next": False,
                    "decoder_ce_training_authorized_next": False,
                    "denoise_ce_training_authorized_next": False,
                    "runtime_authorized": False,
                    "source_emission_authorized": False,
                    "body_emission_authorized": False,
                    "gemma_execution_authorized_next": False,
                    "harness_execution_authorized_next": False,
                    "scoring_authorized_next": False,
                    "controller_complete_merge_authorized_next": False,
                    "promotion_ready": False,
                },
                "standalone_projection_source": {
                    "projection_stage": STAGE,
                    "projection_mode": "compact_bounded_choice_auxiliary",
                    "gold_answers_path": str(bundle.get("perspective_gold_adjudication") or ""),
                    "original_answer_kind": str(row.get("original_answer_kind") or ""),
                    "gold_value": gold_value,
                    "variant_index": shift,
                    "variant_count": len(options),
                    "opaque_options": rotated,
                    "semantic_suffix": semantic_suffix or None,
                },
            }
        )
    return variants


def compile_bundle_rows(bundle: dict[str, Any], *, allowed_perspectives: set[str] | None = None) -> list[dict[str, Any]]:
    gold = load_json(ROOT / str(bundle.get("perspective_gold_adjudication") or ""))
    answers = [row for row in gold.get("perspective_gold_answers") or [] if isinstance(row, dict)]
    compiled: list[dict[str, Any]] = []
    for answer in answers:
        perspective = str(answer.get("perspective") or "")
        if allowed_perspectives is not None and perspective not in allowed_perspectives:
            continue
        row = compile_bounded_row(bundle, answer)
        if row is not None:
            compiled.append(row)
    return compiled


def group_bundles(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("language_family") or ""), []).append(row)
    for language in grouped:
        grouped[language] = sorted(grouped[language], key=lambda row: str(row.get("bundle_id") or ""))
    return grouped


def choose_language_splits(grouped: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]], list[str]]:
    train_bundles: dict[str, list[dict[str, Any]]] = {}
    eval_bundle: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for language, bundles in sorted(grouped.items()):
        if language != "web_js_ts_html":
            if len(bundles) < 2:
                failures.append(f"need_at_least_two_bundles::{language}")
                continue
            train_bundles[language] = [bundles[0]]
            eval_bundle[language] = bundles[1]
            continue
        web_eval = next((bundle for bundle in bundles if WEB_EVAL_BUNDLE_SUBSTR in str(bundle.get("bundle_id") or "")), None)
        frontend_train = next((bundle for bundle in bundles if WEB_FRONTEND_TRAIN_BUNDLE_SUBSTR in str(bundle.get("bundle_id") or "")), None)
        code_assist = next((bundle for bundle in bundles if WEB_CODE_ASSIST_BUNDLE_SUBSTR in str(bundle.get("bundle_id") or "")), None)
        if web_eval is None:
            failures.append("missing_web_eval_bundle")
            continue
        if frontend_train is None:
            failures.append("missing_frontend_web_train_bundle")
            continue
        if code_assist is None:
            failures.append("missing_code_assist_web_bundle")
            continue
        train_bundles[language] = [frontend_train, code_assist]
        eval_bundle[language] = web_eval
    return train_bundles, eval_bundle, failures


def label_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get("target_text") or "")
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def compile_train_rows_for_language(language: str, bundles: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    compiled: list[dict[str, Any]] = []
    web_strategy: dict[str, Any] = {}
    for bundle in bundles:
        bundle_id = str(bundle.get("bundle_id") or "")
        if language != "web_js_ts_html":
            for row in compile_bundle_rows(bundle):
                compiled.extend(build_variant_rows(bundle, row, split="train"))
            continue
        if WEB_FRONTEND_TRAIN_BUNDLE_SUBSTR in bundle_id:
            kept_rows = compile_bundle_rows(bundle)
            frontend_total = 0
            for row in kept_rows:
                base = build_variant_rows(bundle, row, split="train")
                compiled.extend(base)
                frontend_total += len(base)
                if str(row.get("perspective") or "") in WEB_FRONTEND_DUPLICATE_PERSPECTIVES:
                    duplicated = build_variant_rows(bundle, row, split="train", semantic_suffix="frontend_dup")
                    compiled.extend(duplicated)
                    frontend_total += len(duplicated)
            web_strategy["frontend_bundle"] = bundle_id
            web_strategy["frontend_duplicate_perspectives"] = sorted(WEB_FRONTEND_DUPLICATE_PERSPECTIVES)
            web_strategy["frontend_rows_emitted"] = frontend_total
            continue
        if WEB_CODE_ASSIST_BUNDLE_SUBSTR in bundle_id:
            kept_rows = compile_bundle_rows(bundle, allowed_perspectives=WEB_CODE_ASSIST_ALLOWED_PERSPECTIVES)
            code_assist_total = 0
            for row in kept_rows:
                variants = build_variant_rows(bundle, row, split="train")
                compiled.extend(variants)
                code_assist_total += len(variants)
            web_strategy["code_assist_bundle"] = bundle_id
            web_strategy["code_assist_allowed_perspectives"] = sorted(WEB_CODE_ASSIST_ALLOWED_PERSPECTIVES)
            web_strategy["code_assist_rows_emitted"] = code_assist_total
            continue
    return compiled, web_strategy


def build_package() -> dict[str, Any]:
    admitted = load_json(SOURCE)
    rows = [row for row in admitted.get("rows") or [] if isinstance(row, dict)]
    grouped = group_bundles(rows)
    train_selection, eval_selection, failures = choose_language_splits(grouped)
    train_rows: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []
    split_manifest: list[dict[str, Any]] = []
    web_strategy: dict[str, Any] = {}
    for language in sorted(train_selection):
        train_compiled, language_strategy = compile_train_rows_for_language(language, train_selection[language])
        eval_compiled: list[dict[str, Any]] = []
        bundle = eval_selection[language]
        for row in compile_bundle_rows(bundle):
            eval_compiled.extend(build_variant_rows(bundle, row, split="strict_eval"))
        train_rows.extend(train_compiled)
        eval_rows.extend(eval_compiled)
        if language == "web_js_ts_html":
            web_strategy = language_strategy
        split_manifest.append(
            {
                "language_family": language,
                "train_bundle_ids": [str(bundle.get("bundle_id") or "") for bundle in train_selection[language]],
                "strict_eval_bundle_id": str(bundle.get("bundle_id") or ""),
                "train_rows": len(train_compiled),
                "strict_eval_rows": len(eval_compiled),
            }
        )
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(EVAL_JSONL, eval_rows)
    metrics = {
        "languages": len(split_manifest),
        "train_rows": len(train_rows),
        "strict_eval_rows": len(eval_rows),
        "train_label_counts": label_counts(train_rows),
        "strict_eval_label_counts": label_counts(eval_rows),
        "web_train_bundle_count": len(train_selection.get("web_js_ts_html", [])),
    }
    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "source_admitted_manifest": display(SOURCE),
        "passed": not failures and bool(train_rows) and bool(eval_rows),
        "metrics": metrics,
        "split_manifest": split_manifest,
        "web_rebalance_strategy": {
            "diagnosis_source": "stage10182_augmented_web_frontier_probe_audit",
            "goal": "preserve stage10181 multilingual gains while reducing web surface-selection regression",
            "changes": [
                "frontend bddy web train bundle keeps all bounded perspectives",
                "frontend bddy symptom_localization, patch_impact, and minimal_fix_selection are duplicated once",
                "code_assist web bundle contributes only verifier_outcome and abstention_insufficient_evidence",
                "code_assist candidate_path and evidence_citation supervision are excluded from standalone web training",
            ],
            **web_strategy,
        },
        "failures": failures,
        "train_dataset_path": display(TRAIN_JSONL),
        "eval_dataset_path": display(EVAL_JSONL),
        "fit_for": {
            "standalone_decoder_ce_training": True,
            "full_product_harness_training": False,
            "expert_maintainer_primary_score": False,
            "compact_bounded_auxiliary_projection_only": True,
        },
        "required_honesty_gates": [
            "stage10142_standalone_decoder_contract_audit must pass before standalone score claims",
            "bundle-level heldout split must remain intact",
            "freeform maintainer rows remain excluded from compact standalone package",
            "web strict eval remains the original bddy index.html root",
            "code_assist web replenishment is restricted to verifier/abstention supervision because its candidate-path gold targets a backend surface rather than the held-out frontend edit target family",
        ],
    }
    write_json(PACKAGE_JSON, package)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": package["passed"],
            "package": display(PACKAGE_JSON),
            "metrics": metrics,
            "failures": failures,
            "web_rebalance_strategy": package["web_rebalance_strategy"],
        },
    )
    return package


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    package = build_package()
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": package["passed"],
                "package": display(PACKAGE_JSON),
                "metrics": package["metrics"],
                "failures": package["failures"],
                "web_rebalance_strategy": package["web_rebalance_strategy"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
