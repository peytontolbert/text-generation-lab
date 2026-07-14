#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10883
NAME = "stage10883_flash_attn_alias_safe_successor_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "flash_attn_alias_safe_successor_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
REPAIRED_BUNDLE_JSON = OUT_DIR / "flash_attn_alias_safe_repaired_bundle.json"
REPAIRED_ROWS_JSONL = OUT_DIR / "flash_attn_alias_safe_repaired_rows.jsonl"
ROOT_RECORD_JSON = OUT_DIR / "flash_attn_alias_safe_root_record.json"

BASE_DIR = ARTIFACTS / "stage10881_evidence_alias_quarantine_successor"
BASE_SUMMARY_JSON = BASE_DIR / "evidence_alias_quarantine_successor.json"
BASE_TRAIN_JSONL = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION_JSONL = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT_JSONL = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS_JSONL = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

FLASH_BUNDLE_JSON = ARTIFACTS / "stage10413_fresh_rust_flash_attn_preview" / "fresh_rust_flash_attn_preview_bundle.json"
FLASH_GOLD_JSON = ARTIFACTS / "stage10415_rust_flash_attn_review_packets" / "review_packets" / "stage10413__candle__candle-flash-attn__rust" / "perspective_gold_adjudication.json"
FLASH_ANTI_CHEAT_JSON = ARTIFACTS / "stage10415_rust_flash_attn_review_packets" / "review_packets" / "stage10413__candle__candle-flash-attn__rust" / "anti_cheat_review_card.json"

ROLE_TO_LABEL = {
    "DECISIVE_EVIDENCE": "A",
    "SURFACE_DISTRACTOR": "B",
    "VERIFIER_CONSTRAINT_DISTRACTOR": "C",
    "CALL_PATH_DISTRACTOR": "D",
    "NEARBY_CONTEXT_DISTRACTOR": "E",
    "BACKGROUND_DISTRACTOR": "F",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compact(text: str, limit: int = 280) -> str:
    clean = " ".join(str(text).split())
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + "..."


def slice_around(text: str, anchors: list[str], limit: int = 280) -> str:
    normalized = " ".join(str(text).split())
    if not normalized:
        return ""
    for anchor in anchors:
        idx = normalized.find(anchor)
        if idx >= 0:
            start = max(0, idx - min(60, idx))
            end = min(len(normalized), idx + len(anchor) + 180)
            if start > 0:
                start = normalized.rfind(" ", 0, start) + 1
            if end < len(normalized):
                next_space = normalized.find(" ", end)
                if next_space > 0:
                    end = next_space
            return compact(normalized[start:end], limit=limit)
    return compact(normalized, limit=limit)


def first_item(bundle: dict[str, Any], key: str, path_suffix: str | None = None) -> dict[str, Any]:
    values = ((bundle.get("maintainer_visible_evidence") or {}).get(key)) or []
    for item in values:
        if not isinstance(item, dict):
            continue
        if path_suffix is None or str(item.get("path") or "").endswith(path_suffix):
            return item
    raise KeyError(f"missing_evidence::{key}::{path_suffix or 'any'}")


def build_repaired_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    build_item = first_item(bundle, "candidate_change_surface", "build.rs")
    lib_item = first_item(bundle, "candidate_change_surface", "src/lib.rs")
    ffi_item = first_item(bundle, "candidate_change_surface", "src/ffi.rs")
    test_item = first_item(bundle, "verifier_and_test_constraint", "tests/flash_attn_tests.rs")

    repaired = json.loads(json.dumps(bundle))
    repaired["claim_boundary"] = {
        "gold_answers_fully_adjudicated": True,
        "supports_training_or_scoring_now": True,
        "preview_only": False,
        "alias_safe_successor": True,
        "train_support_only": True,
    }
    repaired["maintainer_visible_evidence"] = {
        "algorithmic_background_reference": [
            {
                **build_item,
                "retrieval_reason": "flash_attn_build_background_distinct",
                "text": slice_around(
                    str(build_item.get("text") or ""),
                    ["Build script to run nvcc", "const KERNEL_FILES", "fn main() -> Result<()>"],
                ),
            }
        ],
        "candidate_change_surface": [
            {
                **lib_item,
                "retrieval_reason": "flash_attn_runtime_candidate_surface_distinct",
                "text": slice_around(
                    str(lib_item.get("text") or ""),
                    ["impl candle::CustomOp3 for FlashAttn", "fn cuda_fwd(", 'fn name(&self) -> &' "'" "static str"],
                ),
            }
        ],
        "nearby_definition_or_usage_context": [
            {
                **ffi_item,
                "retrieval_reason": "flash_attn_ffi_nearby_context_distinct",
                "text": slice_around(
                    str(ffi_item.get("text") or ""),
                    ['extern "C" {', "pub(crate) fn run_mha(", "is_causal: c_int"],
                ),
            }
        ],
        "symptom_or_call_path_analogue": [
            {
                **test_item,
                "retrieval_reason": "flash_attn_test_call_path_distinct",
                "text": slice_around(
                    str(test_item.get("text") or ""),
                    ["fn fa_acausal(", "#[test] fn flash_attn_acausal", "flash_attn_acausal()"],
                ),
            }
        ],
        "verifier_and_test_constraint": [
            {
                **test_item,
                "retrieval_reason": "flash_attn_selected_test_constraint_distinct",
                "text": slice_around(
                    str(test_item.get("text") or ""),
                    ["let device = Device::new_cuda(0)?", "to_vec3_round", "Device::new_cuda(0)?"],
                ),
            }
        ],
    }
    return repaired


def duplicate_groups(prompt_text: str) -> list[dict[str, Any]]:
    if "Evidence:\n" not in prompt_text or "\nOptions:\n" not in prompt_text:
        return []
    evidence_block = prompt_text.split("Evidence:\n", 1)[1].split("\nOptions:\n", 1)[0]
    groups: dict[tuple[str, str], list[str]] = {}
    for line in evidence_block.splitlines():
        if " [" not in line or "]: " not in line:
            continue
        key = line.split(" [", 1)[0].strip()
        path, text = line.split(" [", 1)[1].split("]: ", 1)
        groups.setdefault((path.strip(), text.strip()), []).append(key)
    return [
        {"path": path, "keys": keys}
        for (path, text), keys in groups.items()
        if len(keys) > 1 and text
    ]


def contract_for(bundle: dict[str, Any], perspective: str) -> dict[str, Any]:
    for row in bundle.get("perspective_rows") or []:
        if isinstance(row, dict) and str(row.get("perspective") or "") == perspective:
            contract = row.get("prompt_contract")
            if isinstance(contract, dict):
                return contract
    return {}


def evidence_lines(bundle: dict[str, Any], visible_keys: list[str]) -> list[str]:
    evidence = bundle.get("maintainer_visible_evidence")
    if not isinstance(evidence, dict):
        return []
    lines: list[str] = []
    for key in visible_keys:
        values = evidence.get(key)
        if not isinstance(values, list) or not values:
            continue
        first = values[0]
        if not isinstance(first, dict):
            continue
        path = str(first.get("path") or "")
        text = compact(str(first.get("text") or ""))
        prefix = key if not path else f"{key} [{path}]"
        lines.append(f"{prefix}: {text}")
    return lines[:5]


def compile_prompt(bundle: dict[str, Any], perspective: str, options: list[tuple[str, str]]) -> str:
    contract = contract_for(bundle, perspective)
    task = " ".join(str(contract.get("task") or "").split())
    visible_keys = [str(v) for v in contract.get("visible_evidence_keys") or [] if v]
    parts = [
        f"Language: {bundle.get('language_family')}",
        f"Perspective: {perspective}",
        f"Task: {task}",
    ]
    ev_lines = evidence_lines(bundle, visible_keys)
    if ev_lines:
        parts.append("Evidence:")
        parts.extend(ev_lines)
    parts.append("Options:")
    parts.extend(f"{label}. {value}" for label, value in options)
    parts.append("Answer:")
    return "\n".join(parts) + "\n"


def role_for_option(option_value: str, gold_value: str) -> str:
    if option_value == gold_value:
        return "DECISIVE_EVIDENCE"
    if option_value == "candidate_change_surface":
        return "SURFACE_DISTRACTOR"
    if option_value == "verifier_and_test_constraint":
        return "VERIFIER_CONSTRAINT_DISTRACTOR"
    if option_value == "symptom_or_call_path_analogue":
        return "CALL_PATH_DISTRACTOR"
    if option_value == "nearby_definition_or_usage_context":
        return "NEARBY_CONTEXT_DISTRACTOR"
    return "BACKGROUND_DISTRACTOR"


def build_candidate_prompt(base_prompt: str, option: dict[str, Any]) -> str:
    return (
        f"{base_prompt}\n"
        f"Candidate under review: {option['label']}. {option['value']}\n"
        "Classify the role of this candidate evidence relative to the maintenance decision.\n\n"
        "Choices:\n"
        "A. DECISIVE_EVIDENCE\n"
        "B. SURFACE_DISTRACTOR\n"
        "C. VERIFIER_CONSTRAINT_DISTRACTOR\n"
        "D. CALL_PATH_DISTRACTOR\n"
        "E. NEARBY_CONTEXT_DISTRACTOR\n"
        "F. BACKGROUND_DISTRACTOR\n"
        "Answer:\n"
    )


def root_record(bundle: dict[str, Any], anti_cheat: dict[str, Any]) -> dict[str, Any]:
    visible_keys = sorted(
        key for key, values in (bundle.get("maintainer_visible_evidence") or {}).items() if isinstance(values, list) and values
    )
    selected_tests = [str(v) for v in bundle.get("selected_tests") or [] if v]
    return {
        "record_type": "reviewed_bundle_root",
        "bundle_id": str(bundle["bundle_id"]),
        "root_id": str(bundle["bundle_id"]),
        "repo_id": str(bundle["repo_id"]),
        "repo_family": str(bundle["repo_id"]),
        "language_family": "rust",
        "task_types": [str(row.get("perspective") or "") for row in bundle.get("perspective_rows") or [] if isinstance(row, dict)],
        "task_type_count": len(bundle.get("perspective_rows") or []),
        "candidate_paths_count": len(bundle.get("candidate_paths") or []),
        "selected_tests_count": len(selected_tests),
        "selected_test_anchor": bool(selected_tests),
        "verifier_anchor": bool(selected_tests) and ("verifier_and_test_constraint" in visible_keys),
        "visible_evidence_keys": visible_keys,
        "visible_evidence_key_count": len(visible_keys),
        "abstention_count": 4,
        "non_abstention_count": 4,
        "abstention_heavy": True,
        "source_heldout_admissible": False,
        "train_support_only": True,
        "strict_eval_eligible": False,
        "stress_overlap_only": False,
        "split_role": "train_support",
        "split": "train",
        "same_surface_eval_admissible": False,
        "reviewed_bundle_source": True,
        "successor_row_source": True,
        "claim_notes": [
            "flash_attn_alias_safe_successor",
            "train_support_only",
            "heldout_baseline_unchanged",
        ],
        "packet_dir": rel(FLASH_GOLD_JSON.parent),
        "perspective_gold_adjudication": rel(FLASH_GOLD_JSON),
        "rubric_review": "",
        "anti_cheat_review": rel(FLASH_ANTI_CHEAT_JSON),
        "reviewer_id": str(anti_cheat.get("reviewer_id") or ""),
    }


def compile_rows(bundle: dict[str, Any], root_meta: dict[str, Any], anti_cheat: dict[str, Any]) -> list[dict[str, Any]]:
    gold = load_json(FLASH_GOLD_JSON)
    gold_answer = None
    for answer in gold.get("perspective_gold_answers") or []:
        if isinstance(answer, dict) and str(answer.get("perspective") or "") == "evidence_citation":
            gold_answer = answer
            break
    if not isinstance(gold_answer, dict):
        raise ValueError("missing_flash_attn_evidence_gold")

    gold_value = str(gold_answer["gold_answer_value"])
    option_values = [
        "algorithmic_background_reference",
        "candidate_change_surface",
        "nearby_definition_or_usage_context",
        "symptom_or_call_path_analogue",
        "verifier_and_test_constraint",
    ]
    labels = list("ABCDE")
    options = list(zip(labels, option_values))
    label_by_value = {value: label for label, value in options}
    prompt = compile_prompt(bundle, "evidence_citation", options)
    base_row_id = f"{bundle['bundle_id']}::evidence_citation::reviewed_v27_compact_aliassafe"
    base_row = {
        "row_id": base_row_id,
        "source_bundle_id": bundle["bundle_id"],
        "source_root_id": bundle["bundle_id"],
        "repo_id": root_meta["repo_id"],
        "repo_family": root_meta["repo_family"],
        "language_family": root_meta["language_family"],
        "task_type": "evidence_citation",
        "split": "train",
        "split_role": "train_support",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "selected_test_anchor": root_meta["selected_test_anchor"],
        "verifier_anchor": root_meta["verifier_anchor"],
        "abstention_heavy": True,
        "surface": "maintainer_bundle_compact_bounded_choice",
        "objective_family": "bounded_decoder_ce",
        "prompt_text": prompt,
        "input_text": prompt,
        "query_text": "reviewed_v27::rust::evidence_citation::flash_attn_aliassafe",
        "target_text": label_by_value[gold_value],
        "decoder_text": label_by_value[gold_value],
        "target_token_len": len(label_by_value[gold_value].encode("utf-8")),
        "expected_enabled_loss": "decoder_ce",
        "loss_mask": {"decoder_ce": True},
        "disable_losses": [],
        "opaque_options": [{"label": label, "value": value} for label, value in options],
        "standalone_projection_source": {
            "projection_mode": "reviewed_v27_compact_bounded_choice_aliassafe_successor",
            "gold_value": gold_value,
            "original_answer_kind": "visible_evidence_key",
            "opaque_options": [{"label": label, "value": value} for label, value in options],
            "perspective_gold_adjudication": root_meta["perspective_gold_adjudication"],
            "repaired_from_row_id": "stage10413::candle::candle-flash-attn::rust::evidence_citation::reviewed_v27_compact",
        },
        "anti_cheat": {
            "reviewed_bundle_source": True,
            "opaque_labels": True,
            "compact_prompt_contract": True,
            "deterministic_option_shuffle": False,
            "same_surface_eval_admissible": False,
            "repo_overlap_stress_only": False,
            "semantic_role_projection_ready": True,
            "alias_safe_visible_evidence": True,
            "repaired_after_stage10880_alias_audit": True,
            "admissible_for_same_surface_comparison": bool(anti_cheat.get("admissible_for_same_surface_comparison")),
        },
        "support_provenance": {
            "rebalance_stage": STAGE,
            "rebalance_source_key": "flash_attn_aliassafe_successor",
            "rebalance_source_path": rel(REPAIRED_BUNDLE_JSON),
        },
        "residual_family_rebalance_source": "flash_attn_aliassafe_successor",
    }

    candidate_rows: list[dict[str, Any]] = []
    role_options = [{"label": key, "value": value} for value, key in {v: k for k, v in ROLE_TO_LABEL.items()}.items()]
    for option in base_row["opaque_options"]:
        role = role_for_option(str(option["value"]), gold_value)
        candidate_rows.append(
            {
                "row_id": f"{base_row_id}::candidate::{option['label']}",
                "parent_row_id": base_row_id,
                "language_family": "rust",
                "repo_family": root_meta["repo_family"],
                "source_bundle_id": bundle["bundle_id"],
                "split": "train",
                "split_role": "train_support",
                "task_type": "evidence_role_classification",
                "target_text": ROLE_TO_LABEL[role],
                "decoder_text": ROLE_TO_LABEL[role],
                "semantic_role": role,
                "candidate_label": option["label"],
                "candidate_value": option["value"],
                "gold_value": gold_value,
                "prompt_text": build_candidate_prompt(prompt, option),
                "opaque_options": role_options,
                "anti_cheat": {
                    **base_row["anti_cheat"],
                    "semantic_role_projection": True,
                    "same_surface_eval_admissible": False,
                },
                "train_support_only": True,
                "strict_eval_eligible": False,
                "selected_test_anchor": root_meta["selected_test_anchor"],
                "verifier_anchor": root_meta["verifier_anchor"],
                "expected_enabled_loss": "decoder_ce",
                "loss_mask": {"decoder_ce": True},
                "disable_losses": [],
                "evidence_role_projection_source": {
                    "base_task_type": "evidence_citation",
                    "base_gold_value": gold_value,
                    "candidate_value": option["value"],
                    "derived_semantic_role": role,
                    "projection_mode": "stage10883_evidence_role_projection_v1",
                },
                "support_provenance": base_row["support_provenance"],
                "residual_family_rebalance_source": "flash_attn_aliassafe_successor",
            }
        )

    rows = [base_row, *candidate_rows]
    for row in rows:
        if duplicate_groups(str(row.get("prompt_text") or "")):
            raise ValueError(f"duplicate_visible_evidence::{row['row_id']}")
    return rows


def main() -> None:
    base_summary = load_json(BASE_SUMMARY_JSON)
    base_train = load_jsonl(BASE_TRAIN_JSONL)
    base_validation = load_jsonl(BASE_VALIDATION_JSONL)
    base_strict = load_jsonl(BASE_STRICT_JSONL)
    base_stress = load_jsonl(BASE_STRESS_JSONL)
    flash_bundle = load_json(FLASH_BUNDLE_JSON)
    flash_anti_cheat = load_json(FLASH_ANTI_CHEAT_JSON)

    repaired_bundle = build_repaired_bundle(flash_bundle)
    root_meta = root_record(repaired_bundle, flash_anti_cheat)
    repaired_rows = compile_rows(repaired_bundle, root_meta, flash_anti_cheat)

    existing_ids = {str(row.get("row_id") or "") for row in base_train}
    train_rows = list(base_train)
    for row in repaired_rows:
        if row["row_id"] not in existing_ids:
            train_rows.append(row)
            existing_ids.add(row["row_id"])

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "flash_attn_alias_safe_train_successor_ready",
        "claim_scope": [
            "Repair the admitted Rust flash-attn evidence_citation train-support row after the stage10880 alias audit.",
            "Restore Rust evidence-family train coverage with source-derived, visibly distinct evidence keys while leaving heldout scoring unchanged.",
        ],
        "source_artifacts": {
            "base_quarantine_successor": rel(BASE_SUMMARY_JSON),
            "flash_attn_preview_bundle": rel(FLASH_BUNDLE_JSON),
            "flash_attn_gold_adjudication": rel(FLASH_GOLD_JSON),
            "flash_attn_anti_cheat_review": rel(FLASH_ANTI_CHEAT_JSON),
        },
        "metrics": {
            "train_rows_before": len(base_train),
            "train_rows_after": len(train_rows),
            "added_repaired_rows": len(repaired_rows),
            "validation_rows_unchanged": len(base_validation),
            "strict_rows_unchanged": len(base_strict),
            "stress_rows_unchanged": len(base_stress),
            "repaired_duplicate_visible_evidence_groups": 0,
        },
        "repaired_rows": [row["row_id"] for row in repaired_rows],
        "interpretation": [
            "This restores a real reviewed Rust root into train support without reviving the aliased tokenizers/candle-core evidence rows.",
            "The repaired flash-attn evidence prompt now separates build background, runtime candidate surface, FFI context, test call-path, and verifier/test constraint with distinct source-derived spans.",
            "Heldout multilingual scoring remains the 23-row quarantined baseline until a separate root-disjoint Rust eval bundle is admitted.",
        ],
        "limitations": [
            "This is train-support repair only; it does not replenish strict or validation Rust evidence coverage.",
            "Flash-attn remains abstention-heavy overall and should not be upgraded into a unique-file localization claim.",
        ],
        "next_best_step": "Use this successor as the anti-cheat-clean Rust evidence train baseline, then materialize a separate root-disjoint Rust eval bundle before changing the multilingual heldout headline.",
        "upstream_baseline_metrics": base_summary.get("metrics"),
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
            "repaired_bundle_json": rel(REPAIRED_BUNDLE_JSON),
            "repaired_rows_jsonl": rel(REPAIRED_ROWS_JSONL),
            "root_record_json": rel(ROOT_RECORD_JSON),
        },
    }

    write_json(REPAIRED_BUNDLE_JSON, repaired_bundle)
    write_json(ROOT_RECORD_JSON, root_meta)
    write_jsonl(REPAIRED_ROWS_JSONL, repaired_rows)
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, base_validation)
    write_jsonl(STRICT_JSONL, base_strict)
    write_jsonl(STRESS_JSONL, base_stress)
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
