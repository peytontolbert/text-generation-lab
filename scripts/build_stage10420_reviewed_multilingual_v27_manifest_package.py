#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10420
NAME = "stage10420_reviewed_multilingual_v27_manifest_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "reviewed_multilingual_v27_manifest_package.json"
ROOT_MANIFEST_JSONL = OUT_DIR / "reviewed_multilingual_v27_root_manifest.jsonl"
ROWS_JSONL = OUT_DIR / "reviewed_multilingual_v27_bounded_rows.jsonl"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

ATLAS_JSON = ROOT / "runs/local/artifacts/stage10417_multilingual_reviewed_scaling_atlas/multilingual_reviewed_scaling_atlas.json"
SUCCESSOR_AUDIT_JSON = ROOT / "runs/local/artifacts/stage10410_ai_adjudicated_successor_salvage/ai_adjudicated_successor_salvage.json"
SUCCESSOR_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10410_ai_adjudicated_successor_salvage/real_session_successor_adjudicated_manifest.jsonl"
FLASH_AUDIT_JSON = ROOT / "runs/local/artifacts/stage10416_ai_adjudicate_rust_flash_attn_bundle/rust_flash_attn_ai_adjudication_summary.json"
V26_FRONTIER_JSON = ROOT / "runs/local/artifacts/stage10404_generic_policy_frontier_eval/language_conditioned_frontier_eval.json"
V26_GEMMA_JSON = ROOT / "runs/local/artifacts/stage10406_gemma_same_frontier_comparison/gemma_same_frontier_comparison.json"

BUNDLE_SOURCES = [
    ROOT / "runs/local/artifacts/stage10119_true_source_backed_maintainer_root_bundle_preview/true_source_backed_maintainer_root_bundle_preview.jsonl",
    ROOT / "runs/local/artifacts/stage10126_true_source_backed_rust_root_bundle_preview/true_source_backed_rust_root_bundle_preview.jsonl",
]
BUNDLE_SINGLETONS = [
    ROOT / "runs/local/artifacts/stage10176_code_assist_web_replenishment_bundle/code_assist_web_replenishment_bundle.json",
    ROOT / "runs/local/artifacts/stage10413_fresh_rust_flash_attn_preview/fresh_rust_flash_attn_preview_bundle.json",
]

BOUND_KINDS = {"candidate_path", "selected_test", "visible_evidence_key", "abstain"}
CHOICE_LABELS = list("ABCDEFGHJKLMNOPQRSTUVWXYZ")

# Root-level split policy for the reviewed v2.7 package.
STRICT_ROOTS = {
    "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python",
    "stage10119::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_26t17_53_18_019d2b47_7d2d_7622_8e05_3513_agent_kernel_modeling_ssm_kernels_src_selective_scan_cpp_agent_kernel_modeling_w_5511e7fec6_aug_1500000_8b46e7f662::c_cpp",
    "stage10126::tokenizers::tokenizers::rust",
    "stage10119::localsess_bddy_website_sessseed_codex_sessions_rollout_2025_11_24t23_41_47_019ab83e_b023_7553_a34c_b93e_src_main_js_index_html_440e122a0f_aug_1500000_8b46e7f662::web_js_ts_html",
}
VALIDATION_ROOTS = {
    "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_26t00_55_44_019abda8_c0d8_7803_8a77_1e0f_scripts_universe_build_py_64d2cf209b_aug_1500000_8b46e7f662::python",
    "stage10119::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_56_21_019d3560_1014_7761_9ea7_5638_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_causalmachine_cuda_a018ca0b43_aug_1500000_8b46e7f662::c_cpp",
    "stage10126::candle::candle-core::rust",
    "stage10119::localsess_bddy_website_sessseed_codex_sessions_rollout_2025_11_28t14_11_27_019acacd_f95c_7802_9bfe_7232_index_html_f0be60dc44_aug_1500000_8b46e7f662::web_js_ts_html",
}
TRAIN_SUPPORT_ROOTS = {
    "stage10413::candle::candle-flash-attn::rust",
}
STRESS_ROOTS = {
    "stage10176::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t13_13_10_019bff96_2dc5_7162_88f8_83eb_src_code_assist_orchestrator_cognitive_perfection_py_src_code_assist_orchestrato_3a0f6d8311_aug_1500000_8b46e7f662::web_js_ts_html",
}
TRAIN_SUCCESSOR_ROWS = {
    "stage10110::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_45_019d39fb_a380_7a30_8790_9d59_agent_kernel_improvement_py_agent_kernel_modeling_adapter_training_py_agent_kern_94b87c02df_aug_1500000_8b46e7f662::python_implementation_vs_implementation",
    "stage10110::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_54_019d39fb_c43d_7e62_b055_b00b_agent_kernel_cycle_runner_py_agent_kernel_improvement_py_agent_kernel_learning_c_6a4dce0d0c_aug_1500000_8b46e7f662::python_implementation_vs_implementation",
    "stage10110::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_26t02_56_49_019d2812_bb90_78e1_825d_9bc7_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_causalmachine_cuda_6b714ae486_aug_1500000_8b46e7f662::cpp_implementation_vs_implementation",
}
STRESS_SUCCESSOR_ROWS = {
    "stage10110::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t13_13_10_019bff96_2dc5_7162_88f8_83eb_src_code_assist_orchestrator_cognitive_perfection_py_src_code_assist_orchestrato_3a0f6d8311_aug_1500000_8b46e7f662::web_implementation_vs_implementation",
}


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compact(text: str, limit: int = 280) -> str:
    clean = " ".join(str(text).split())
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + "..."


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


def deterministic_rotate(values: list[str], shift: int) -> list[str]:
    return values[shift:] + values[:shift]


def role_for_bundle(bundle_id: str) -> str:
    if bundle_id in STRESS_ROOTS:
        return "stress_overlap"
    if bundle_id in STRICT_ROOTS:
        return "strict_heldout"
    if bundle_id in VALIDATION_ROOTS:
        return "validation"
    if bundle_id in TRAIN_SUPPORT_ROOTS:
        return "train_support"
    return "train_support"


def split_for_role(role: str) -> str:
    return {
        "train_support": "train",
        "validation": "validation",
        "strict_heldout": "strict_eval",
        "stress_overlap": "stress_eval",
    }[role]


def role_for_successor(row_id: str) -> str:
    if row_id in STRESS_SUCCESSOR_ROWS:
        return "stress_overlap"
    if row_id in TRAIN_SUCCESSOR_ROWS:
        return "train_support"
    return "train_support"


def bundle_root_record(bundle: dict[str, Any], atlas_row: dict[str, Any]) -> dict[str, Any]:
    bundle_id = str(bundle["bundle_id"])
    role = role_for_bundle(bundle_id)
    selected_tests = [str(v) for v in bundle.get("selected_tests") or [] if v]
    visible_keys = sorted((bundle.get("maintainer_visible_evidence") or {}).keys())
    abstention_count = int(atlas_row.get("abstention_count") or 0)
    non_abstention_count = int(atlas_row.get("non_abstention_count") or 0)
    repo_id = str(bundle.get("repo_id") or atlas_row.get("repo_id") or "unknown")
    repo_family = repo_id
    selected_test_anchor = bool(selected_tests)
    verifier_anchor = selected_test_anchor and ("verifier_and_test_constraint" in visible_keys)
    abstention_heavy = abstention_count >= non_abstention_count
    source_heldout_admissible = False
    train_support_only = role == "train_support"
    strict_eval_eligible = role == "strict_heldout"
    stress_overlap_only = role == "stress_overlap"
    notes = []
    if bundle_id in STRESS_ROOTS:
        notes.append("repo_overlap_stress_only")
    if bundle_id == "stage10413::candle::candle-flash-attn::rust":
        notes.append("rust_abstention_heavy_support")
    if repo_id == "bddy_website" and not selected_test_anchor:
        notes.append("pure_web_no_selected_test_anchor")
    if repo_id == "code_assist":
        notes.append("mixed_language_code_assist_not_headline_web")
    return {
        "record_type": "reviewed_bundle_root",
        "bundle_id": bundle_id,
        "root_id": bundle_id,
        "repo_id": repo_id,
        "repo_family": repo_family,
        "language_family": str(bundle.get("language_family") or atlas_row.get("language_family") or "unknown"),
        "task_types": [str(row.get("perspective") or "") for row in bundle.get("perspective_rows") or [] if isinstance(row, dict)],
        "task_type_count": len(bundle.get("perspective_rows") or []),
        "candidate_paths_count": len(bundle.get("candidate_paths") or []),
        "selected_tests_count": len(selected_tests),
        "selected_test_anchor": selected_test_anchor,
        "verifier_anchor": verifier_anchor,
        "visible_evidence_keys": visible_keys,
        "visible_evidence_key_count": len(visible_keys),
        "abstention_count": abstention_count,
        "non_abstention_count": non_abstention_count,
        "abstention_heavy": abstention_heavy,
        "source_heldout_admissible": source_heldout_admissible,
        "train_support_only": train_support_only,
        "strict_eval_eligible": strict_eval_eligible,
        "stress_overlap_only": stress_overlap_only,
        "split_role": role,
        "split": split_for_role(role),
        "same_surface_eval_admissible": bool(atlas_row.get("admissible_for_same_surface_comparison")),
        "reviewed_bundle_source": True,
        "successor_row_source": False,
        "claim_notes": notes,
        "packet_dir": atlas_row.get("packet_dir"),
        "perspective_gold_adjudication": str(Path(str(atlas_row.get("packet_dir"))) / "perspective_gold_adjudication.json"),
        "rubric_review": str(Path(str(atlas_row.get("packet_dir"))) / "expert_maintainer_rubric_review.json"),
        "anti_cheat_review": str(Path(str(atlas_row.get("packet_dir"))) / "anti_cheat_review_card.json"),
    }


def contract_for(bundle: dict[str, Any], perspective: str) -> dict[str, Any]:
    for row in bundle.get("perspective_rows") or []:
        if isinstance(row, dict) and str(row.get("perspective") or "") == perspective:
            contract = row.get("prompt_contract")
            if isinstance(contract, dict):
                return contract
    return {}


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
            seen.add(value)
            deduped.append(value)
    if gold_value not in seen:
        deduped.append(gold_value)
    return deduped


def compile_bundle_prompt(bundle: dict[str, Any], gold: dict[str, Any], options: list[tuple[str, str]]) -> str:
    perspective = str(gold.get("perspective") or "")
    contract = contract_for(bundle, perspective)
    task = " ".join(str(contract.get("task") or "").split())
    visible_keys = [str(v) for v in contract.get("visible_evidence_keys") or [] if v]
    ev_lines = evidence_lines(bundle, visible_keys)
    parts = [
        f"Language: {bundle.get('language_family')}",
        f"Perspective: {perspective}",
        f"Task: {task}",
    ]
    if ev_lines:
        parts.append("Evidence:")
        parts.extend(ev_lines)
    parts.append("Options:")
    parts.extend(f"{label}. {value}" for label, value in options)
    parts.append("Answer:")
    return "\n".join(parts) + "\n"


def compile_bundle_row(bundle: dict[str, Any], root_meta: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any] | None:
    perspective = str(gold.get("perspective") or "")
    answer_kind = str(gold.get("gold_answer_kind") or "")
    gold_value = str(gold.get("gold_answer_value") or "")
    if answer_kind not in BOUND_KINDS:
        return None
    contract = contract_for(bundle, perspective)
    values = build_option_values(answer_kind=answer_kind, gold_value=gold_value, contract=contract, gold=gold)
    if len(values) > len(CHOICE_LABELS):
        raise ValueError(f"too_many_options::{bundle['bundle_id']}::{perspective}")
    options = list(zip(CHOICE_LABELS[: len(values)], values))
    label_by_value = {value: label for label, value in options}
    prompt = compile_bundle_prompt(bundle, gold, options)
    split = str(root_meta["split"])
    row = {
        "row_id": f"{bundle['bundle_id']}::{perspective}::reviewed_v27_compact",
        "source_bundle_id": bundle["bundle_id"],
        "source_root_id": bundle["bundle_id"],
        "repo_id": root_meta["repo_id"],
        "repo_family": root_meta["repo_family"],
        "language_family": root_meta["language_family"],
        "task_type": perspective,
        "split": split,
        "split_role": root_meta["split_role"],
        "train_support_only": root_meta["train_support_only"],
        "strict_eval_eligible": root_meta["strict_eval_eligible"],
        "source_heldout_admissible": root_meta["source_heldout_admissible"],
        "selected_test_anchor": root_meta["selected_test_anchor"],
        "verifier_anchor": root_meta["verifier_anchor"],
        "abstention_heavy": root_meta["abstention_heavy"],
        "surface": "maintainer_bundle_compact_bounded_choice",
        "objective_family": "bounded_decoder_ce",
        "prompt_text": prompt,
        "input_text": prompt,
        "query_text": f"reviewed_v27::{root_meta['language_family']}::{perspective}",
        "target_text": label_by_value[gold_value],
        "decoder_text": label_by_value[gold_value],
        "target_token_len": len(label_by_value[gold_value].encode("utf-8")),
        "expected_enabled_loss": "decoder_ce",
        "loss_mask": {"decoder_ce": split == "train"},
        "disable_losses": [] if split == "train" else ["denoise_ce", "runtime_reward", "structured_aux"],
        "opaque_options": [{"label": label, "value": value} for label, value in options],
        "standalone_projection_source": {
            "projection_mode": "reviewed_v27_compact_bounded_choice",
            "gold_value": gold_value,
            "original_answer_kind": answer_kind,
            "opaque_options": [{"label": label, "value": value} for label, value in options],
            "perspective_gold_adjudication": root_meta["perspective_gold_adjudication"],
        },
        "anti_cheat": {
            "reviewed_bundle_source": True,
            "opaque_labels": True,
            "compact_prompt_contract": True,
            "deterministic_option_shuffle": False,
            "same_surface_eval_admissible": root_meta["same_surface_eval_admissible"],
            "repo_overlap_stress_only": root_meta["stress_overlap_only"],
        },
    }
    return row


def compile_successor_prompt(row: dict[str, Any], values: list[str]) -> str:
    prompt_surface = row["prompt_surface"]
    parts = [
        f"Language: {row['language_family']}",
        f"Perspective: {row['successor_template']}",
        f"Task: {' '.join(str(prompt_surface.get('task_observation') or '').split())}",
    ]
    evidence = [compact(v) for v in prompt_surface.get("visible_evidence") or [] if v]
    if evidence:
        parts.append("Evidence:")
        parts.extend(f"visible_evidence_{i+1}: {text}" for i, text in enumerate(evidence[:5]))
    parts.append("Options:")
    for label, value in zip(CHOICE_LABELS, values):
        parts.append(f"{label}. {value}")
    parts.append("Answer:")
    return "\n".join(parts) + "\n"


def compile_successor_row(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    row_id = str(row["row_id"])
    role = role_for_successor(row_id)
    split = split_for_role(role)
    repo_id = str(row.get("repo_id") or "unknown")
    selected_tests = [str(v) for v in (((row.get("hidden_metadata") or {}).get("selected_tests")) or []) if v]
    selected_test_anchor = bool(selected_tests)
    verifier_anchor = selected_test_anchor
    gold_value = str(row.get("gold_answer") or "")
    candidates = [str(item.get("candidate_id") or "") for item in (row.get("prompt_surface") or {}).get("candidate_choices") or [] if item.get("candidate_id")]
    values = list(candidates)
    if gold_value == "ABSTAIN_INSUFFICIENT_EVIDENCE" and gold_value not in values:
        values.append(gold_value)
    label_by_value = {value: CHOICE_LABELS[idx] for idx, value in enumerate(values)}
    prompt = compile_successor_prompt(row, values)
    root_meta = {
        "record_type": "adjudicated_successor_row",
        "bundle_id": None,
        "root_id": row_id,
        "repo_id": repo_id,
        "repo_family": repo_id,
        "language_family": str(row.get("language_family") or "unknown"),
        "task_types": [str(row.get("successor_template") or "successor_candidate_contrast")],
        "task_type_count": 1,
        "candidate_paths_count": len(candidates),
        "selected_tests_count": len(selected_tests),
        "selected_test_anchor": selected_test_anchor,
        "verifier_anchor": verifier_anchor,
        "visible_evidence_keys": [],
        "visible_evidence_key_count": 0,
        "abstention_count": 1 if gold_value == "ABSTAIN_INSUFFICIENT_EVIDENCE" else 0,
        "non_abstention_count": 0 if gold_value == "ABSTAIN_INSUFFICIENT_EVIDENCE" else 1,
        "abstention_heavy": gold_value == "ABSTAIN_INSUFFICIENT_EVIDENCE",
        "source_heldout_admissible": False,
        "train_support_only": role == "train_support",
        "strict_eval_eligible": False,
        "stress_overlap_only": role == "stress_overlap",
        "split_role": role,
        "split": split,
        "same_surface_eval_admissible": False,
        "reviewed_bundle_source": False,
        "successor_row_source": True,
        "claim_notes": ["admitted_successor_row_only", "compressed_prompt_surface"],
        "packet_dir": None,
        "perspective_gold_adjudication": None,
        "rubric_review": str((row.get("review_provenance") or {}).get("expert_maintainer_rubric_review") or ""),
        "anti_cheat_review": str((row.get("review_provenance") or {}).get("cell_specific_anti_cheat_review") or ""),
    }
    compiled = {
        "row_id": f"{row_id}::reviewed_v27_successor",
        "source_bundle_id": None,
        "source_root_id": row_id,
        "repo_id": repo_id,
        "repo_family": repo_id,
        "language_family": root_meta["language_family"],
        "task_type": str(row.get("successor_template") or "successor_candidate_contrast"),
        "split": split,
        "split_role": role,
        "train_support_only": root_meta["train_support_only"],
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "selected_test_anchor": selected_test_anchor,
        "verifier_anchor": verifier_anchor,
        "abstention_heavy": root_meta["abstention_heavy"],
        "surface": "real_session_successor_candidate_contrast",
        "objective_family": "bounded_decoder_ce",
        "prompt_text": prompt,
        "input_text": prompt,
        "query_text": f"reviewed_v27::{root_meta['language_family']}::{row.get('successor_template')}",
        "target_text": label_by_value[gold_value],
        "decoder_text": label_by_value[gold_value],
        "target_token_len": len(label_by_value[gold_value].encode("utf-8")),
        "expected_enabled_loss": "decoder_ce",
        "loss_mask": {"decoder_ce": split == "train"},
        "disable_losses": [] if split == "train" else ["denoise_ce", "runtime_reward", "structured_aux"],
        "opaque_options": [{"label": label_by_value[value], "value": value} for value in values],
        "standalone_projection_source": {
            "projection_mode": "reviewed_v27_successor_candidate_contrast",
            "gold_value": gold_value,
            "original_answer_kind": str(row.get("gold_answer_kind") or ""),
            "opaque_options": [{"label": label_by_value[value], "value": value} for value in values],
            "review_provenance": row.get("review_provenance") or {},
        },
        "anti_cheat": {
            "reviewed_bundle_source": False,
            "successor_row_source": True,
            "opaque_labels": True,
            "compact_prompt_contract": True,
            "repo_overlap_stress_only": role == "stress_overlap",
            "requires_abstention_support": bool(((row.get("training_scoring_contract") or {}).get("requires_abstention_support"))),
        },
    }
    return root_meta, compiled


def load_bundle_map() -> dict[str, dict[str, Any]]:
    bundle_map: dict[str, dict[str, Any]] = {}
    for path in BUNDLE_SOURCES:
        for row in load_jsonl(path):
            bundle_id = str(row.get("bundle_id") or "")
            if bundle_id:
                bundle_map[bundle_id] = row
    for path in BUNDLE_SINGLETONS:
        row = load_json(path)
        bundle_id = str(row.get("bundle_id") or "")
        if bundle_id:
            bundle_map[bundle_id] = row
    return bundle_map


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter = Counter(str(row.get(key) or "unknown") for row in rows)
    return dict(sorted(counter.items()))


def main() -> None:
    bundle_map = load_bundle_map()
    atlas = load_json(ATLAS_JSON)
    flash = load_json(FLASH_AUDIT_JSON)
    successors = load_jsonl(SUCCESSOR_ROWS_JSONL)

    root_records: list[dict[str, Any]] = []
    bounded_rows: list[dict[str, Any]] = []
    failures: list[str] = []

    for atlas_row in atlas.get("admitted_bundle_rows") or []:
        if not isinstance(atlas_row, dict):
            continue
        bundle_id = str(atlas_row.get("bundle_id") or "")
        bundle = bundle_map.get(bundle_id)
        if bundle is None:
            failures.append(f"missing_bundle_payload::{bundle_id}")
            continue
        root_meta = bundle_root_record(bundle, atlas_row)
        root_records.append(root_meta)
        gold = load_json(ROOT / root_meta["perspective_gold_adjudication"])
        for answer in gold.get("perspective_gold_answers") or []:
            if not isinstance(answer, dict):
                continue
            compiled = compile_bundle_row(bundle, root_meta, answer)
            if compiled is not None:
                bounded_rows.append(compiled)

    for row in successors:
        if not isinstance(row, dict):
            continue
        root_meta, compiled = compile_successor_row(row)
        root_records.append(root_meta)
        bounded_rows.append(compiled)

    train_rows = [row for row in bounded_rows if row.get("split") == "train"]
    validation_rows = [row for row in bounded_rows if row.get("split") == "validation"]
    strict_rows = [row for row in bounded_rows if row.get("split") == "strict_eval"]
    stress_rows = [row for row in bounded_rows if row.get("split") == "stress_eval"]

    split_role_counts = count_by(root_records, "split_role")
    root_language_counts = count_by(root_records, "language_family")
    root_repo_counts = count_by(root_records, "repo_id")
    row_language_counts = count_by(bounded_rows, "language_family")
    row_task_counts = count_by(bounded_rows, "task_type")
    row_split_counts = count_by(bounded_rows, "split")
    row_repo_counts = count_by(bounded_rows, "repo_id")
    selected_anchor_counts = dict(sorted(Counter("present" if row.get("selected_test_anchor") else "absent" for row in bounded_rows).items()))
    verifier_anchor_counts = dict(sorted(Counter("present" if row.get("verifier_anchor") else "absent" for row in bounded_rows).items()))
    abstention_heavy_counts = dict(sorted(Counter("yes" if row.get("abstention_heavy") else "no" for row in bounded_rows).items()))

    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not failures,
        "v26_regression_suite": {
            "frontier_eval": display(V26_FRONTIER_JSON),
            "gemma_comparison": display(V26_GEMMA_JSON),
            "status": "frozen_regression_suite_only",
        },
        "source_artifacts": {
            "reviewed_scaling_atlas": display(ATLAS_JSON),
            "successor_salvage_audit": display(SUCCESSOR_AUDIT_JSON),
            "successor_rows": display(SUCCESSOR_ROWS_JSONL),
            "flash_attn_adjudication": display(FLASH_AUDIT_JSON),
        },
        "outputs": {
            "root_manifest": display(ROOT_MANIFEST_JSONL),
            "bounded_rows": display(ROWS_JSONL),
            "train_rows": display(TRAIN_JSONL),
            "validation_rows": display(VALIDATION_JSONL),
            "strict_rows": display(STRICT_JSONL),
            "stress_rows": display(STRESS_JSONL),
        },
        "metrics": {
            "root_records": len(root_records),
            "bounded_rows": len(bounded_rows),
            "split_role_counts": split_role_counts,
            "root_language_counts": root_language_counts,
            "root_repo_counts": root_repo_counts,
            "row_language_counts": row_language_counts,
            "row_task_counts": row_task_counts,
            "row_split_counts": row_split_counts,
            "row_repo_counts": row_repo_counts,
            "selected_test_anchor_counts": selected_anchor_counts,
            "verifier_anchor_counts": verifier_anchor_counts,
            "abstention_heavy_counts": abstention_heavy_counts,
            "strict_eval_rows": len(strict_rows),
            "validation_rows": len(validation_rows),
            "train_rows": len(train_rows),
            "stress_rows": len(stress_rows),
        },
        "claim_boundary": [
            "v2.6 remains the frozen 47-row regression suite and must not be used as the main scaling benchmark.",
            "This v2.7 package uses root-level reviewed inventory and admitted successor rows, not row-level sibling leakage.",
            "code_assist web artifacts remain repo-overlap stress-only and cannot support a source-heldout pure-web headline.",
            "candle-flash-attn is included as real source-backed Rust support, but it is flagged abstention-heavy and should support honesty/robustness claims rather than precise singleton-localization claims.",
            "source_heldout_admissible remains conservative and false until explicit heldout proof exists for a root.",
        ],
        "next_best_step": "Run one promotion-style probe/eval against the larger root-split reviewed package, tracking accuracy, margin, verifier-anchor slices, and abstention calibration separately from the frozen 47-row v2.6 regression suite.",
        "failures": failures,
        "flash_attn_claim_boundary": flash.get("claim_boundary") or [],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    write_json(PACKAGE_JSON, package)
    write_jsonl(ROOT_MANIFEST_JSONL, root_records)
    write_jsonl(ROWS_JSONL, bounded_rows)
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": not failures,
            "package": display(PACKAGE_JSON),
            "metrics": package["metrics"],
        },
    )
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": not failures,
                "package": display(PACKAGE_JSON),
                "metrics": package["metrics"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
