#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10204
NAME = "stage10204_c_cpp_abstention_counterbalance_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
EVAL_JSONL = OUT_DIR / "agentkernel_lite_encdec_eval.jsonl"
PACKAGE_JSON = OUT_DIR / "c_cpp_abstention_counterbalance_package.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
BASE_PACKAGE = ROOT / "runs/local/artifacts/stage10200_targeted_contrast_compact_package/targeted_contrast_compact_package.json"
PREVIEW_JSONL = ROOT / "runs/local/artifacts/stage10119_true_source_backed_maintainer_root_bundle_preview/true_source_backed_maintainer_root_bundle_preview.jsonl"
REVIEW_ROOT = ROOT / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/review_packets"
SUCCESSOR_PACKET_JSONL = ROOT / "runs/local/artifacts/stage10110_real_session_shortcut_safe_successor_packet/real_session_shortcut_safe_successor_packet.jsonl"
SUCCESSOR_REVIEW_ROOT = ROOT / "runs/local/artifacts/stage10111_real_session_successor_review_packets/review_packets"
SUCCESSOR_REVIEW_PACKET_MANIFEST = ROOT / "runs/local/artifacts/stage10111_real_session_successor_review_packets/real_session_successor_review_packets.jsonl"
CHOICE_LABELS = list("ABCDEFGHJKLMNOPQRSTUVWXYZ")
TARGET_PERSPECTIVES = {
    "evidence_citation",
    "verifier_outcome",
    "abstention_insufficient_evidence",
}
TRAIN_ONLY_BUNDLES = [
    "stage10119::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_25t04_03_50_019d2329_b8e4_7312_aed0_4b6b_peytontolbert_parameter_golf_data_profile_causal_machine_training_py_peytontolbe_04b753812b_aug_1500000_8b46e7f662::c_cpp",
    "stage10119::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_25t18_14_10_019d2634_3b0e_7ee2_896b_6d95_parameter_golf_data_analyze_spectral_sidecar_py_parameter_golf_profile_architect_171988f281_aug_1500000_8b46e7f662::c_cpp",
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


def snippet(text: str, limit: int = 280) -> str:
    clean = " ".join(str(text).split())
    return clean if len(clean) <= limit else clean[: max(0, limit - 3)] + "..."


def stable_order(values: list[str], seed: str) -> list[str]:
    return sorted(values, key=lambda value: hashlib.sha256(f"{seed}::{value}".encode("utf-8")).hexdigest())


def compile_prompt(bundle: dict[str, Any], perspective: str, contract: dict[str, Any], *, options: list[tuple[str, str]]) -> str:
    parts = [
        f"Language: {bundle.get('language_family')}",
        f"Perspective: {perspective}",
        f"Task: {' '.join(str(contract.get('task') or '').split())}",
    ]
    visible = bundle.get("maintainer_visible_evidence") if isinstance(bundle.get("maintainer_visible_evidence"), dict) else {}
    lines: list[str] = []
    for key in contract.get("visible_evidence_keys") or []:
        values = visible.get(key)
        if not isinstance(values, list) or not values:
            continue
        first = values[0]
        if not isinstance(first, dict):
            continue
        visible_path = str(first.get("path") or "")
        source_type = str(first.get("source_type") or "")
        text = snippet(str(first.get("text") or ""))
        prefix = str(key)
        if visible_path:
            prefix += f" [{visible_path}]"
        elif source_type:
            prefix += f" [{source_type}]"
        lines.append(f"{prefix}: {text}")
    if lines:
        parts.append("Evidence:")
        parts.extend(lines[:4])
    parts.append("Options:")
    parts.extend(f"{label}. {value}" for label, value in options)
    parts.append("Answer:")
    return "\n".join(parts) + "\n"


def compile_successor_prompt_surface(row: dict[str, Any], *, options: list[tuple[str, str]], perspective: str) -> str:
    prompt_surface = row.get("prompt_surface") if isinstance(row.get("prompt_surface"), dict) else {}
    parts = [
        f"Language: {row.get('language_family')}",
        f"Perspective: {perspective}",
        f"Task: {' '.join(str(prompt_surface.get('task_observation') or '').split())}",
    ]
    visible_evidence = prompt_surface.get("visible_evidence")
    if isinstance(visible_evidence, list) and visible_evidence:
        parts.append("Evidence:")
        for idx, value in enumerate(visible_evidence[:5], start=1):
            parts.append(f"supporting_visible_evidence_{idx}: {snippet(str(value))}")
    parts.append("Options:")
    parts.extend(f"{label}. {value}" for label, value in options)
    parts.append("Answer:")
    return "\n".join(parts) + "\n"


def build_option_values(answer: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    answer_kind = str(answer.get("gold_answer_kind") or "")
    gold_value = str(answer.get("gold_answer_value") or "")
    values: list[str]
    if answer_kind == "candidate_path":
        values = [str(v) for v in (answer.get("candidate_paths") or contract.get("candidate_paths") or []) if v]
    elif answer_kind == "selected_test":
        values = [str(v) for v in (answer.get("selected_tests") or contract.get("selected_tests") or []) if v]
    elif answer_kind == "visible_evidence_key":
        values = [str(v) for v in (answer.get("visible_evidence_keys") or contract.get("visible_evidence_keys") or []) if v]
    elif answer_kind == "abstain":
        values = [str(v) for v in (answer.get("candidate_paths") or contract.get("candidate_paths") or []) if v]
        if not values:
            values = [str(v) for v in (answer.get("selected_tests") or contract.get("selected_tests") or []) if v]
        if not values:
            values = [str(v) for v in (answer.get("visible_evidence_keys") or contract.get("visible_evidence_keys") or []) if v]
        values.append("ABSTAIN_INSUFFICIENT_EVIDENCE")
    else:
        values = [gold_value]
    deduped: list[str] = []
    seen = set()
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    if gold_value not in seen and gold_value:
        deduped.append(gold_value)
    return deduped


def preview_bundles() -> dict[str, dict[str, Any]]:
    rows = load_jsonl(PREVIEW_JSONL)
    return {str(row.get("bundle_id") or ""): row for row in rows if isinstance(row, dict)}


def successor_rows() -> dict[str, dict[str, Any]]:
    rows = load_jsonl(SUCCESSOR_PACKET_JSONL)
    return {str(row.get("row_id") or ""): row for row in rows if isinstance(row, dict)}


def successor_review_packet_dirs() -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for row in load_jsonl(SUCCESSOR_REVIEW_PACKET_MANIFEST):
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("row_id") or "")
        packet_dir = str(row.get("packet_dir") or "")
        if row_id and packet_dir:
            mapping[row_id] = ROOT / packet_dir
    return mapping


def compile_recovered_successor_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows_by_id = successor_rows()
    review_dirs = successor_review_packet_dirs()
    compiled: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    for bundle_id in TRAIN_ONLY_BUNDLES:
        row_id = bundle_id.replace("stage10119::", "stage10110::").replace("::c_cpp", "::cpp_implementation_vs_implementation")
        row = rows_by_id.get(row_id)
        if not row:
            manifest.append({"bundle_id": bundle_id, "row_id": row_id, "status": "missing_stage10110_successor_row"})
            continue
        packet_dir = review_dirs.get(row_id)
        if packet_dir is None:
            manifest.append({"bundle_id": bundle_id, "row_id": row_id, "status": "missing_stage10111_review_packet_dir"})
            continue
        rubric = load_json(packet_dir / "expert_maintainer_rubric_review.json")
        anti_cheat = load_json(packet_dir / "anti_cheat_review_card.json")
        prompt_surface = row.get("prompt_surface") if isinstance(row.get("prompt_surface"), dict) else {}
        hidden = row.get("hidden_metadata") if isinstance(row.get("hidden_metadata"), dict) else {}
        choices = prompt_surface.get("candidate_choices") if isinstance(prompt_surface.get("candidate_choices"), list) else []
        values = [str(choice.get("candidate_id") or "") for choice in choices if isinstance(choice, dict) and str(choice.get("candidate_id") or "")]
        if "ABSTAIN_INSUFFICIENT_EVIDENCE" not in values:
            values.append("ABSTAIN_INSUFFICIENT_EVIDENCE")
        seed = f"train_only_successor::{row_id}::abstention"
        canonical = stable_order(values, seed)
        reverse = list(reversed(canonical))
        for idx, ordered in enumerate([canonical, reverse]):
            options = list(zip(CHOICE_LABELS[: len(ordered)], ordered))
            label_by_value = {value: label for label, value in options}
            prompt = compile_successor_prompt_surface(row, options=options, perspective="abstention_insufficient_evidence")
            compiled.append(
                {
                    "row_id": f"{bundle_id}::abstention_insufficient_evidence::train_only_successor_abstain::{idx:02d}",
                    "language_family": str(row.get("language_family") or ""),
                    "route": "KEEP_BOUNDED_DECODER",
                    "objective_family": "bounded_decoder_ce",
                    "surface": "maintainer_bundle_compact_bounded_choice",
                    "task_type": "abstention_insufficient_evidence",
                    "split": "train",
                    "prompt_text": prompt,
                    "input_text": prompt,
                    "query_text": f"train_only_successor::{row.get('language_family')}::abstention_insufficient_evidence::abstain::{idx:02d}",
                    "target_text": label_by_value["ABSTAIN_INSUFFICIENT_EVIDENCE"],
                    "decoder_text": label_by_value["ABSTAIN_INSUFFICIENT_EVIDENCE"],
                    "target_token_len": len(label_by_value["ABSTAIN_INSUFFICIENT_EVIDENCE"].encode("utf-8")),
                    "loss_mask": {"decoder_ce": True},
                    "expected_enabled_loss": "decoder_ce",
                    "disable_losses": ["denoise_ce", "runtime_reward", "structured_aux"],
                    "source_skill_area": "maintainer_bundle_compact_bounded_choice",
                    "source_stage": STAGE,
                    "source_row_id": row_id,
                    "source_bundle_id": bundle_id,
                    "semantic_key": f"maintainer_bundle_train_only_successor::{bundle_id}::abstention_insufficient_evidence::{idx:02d}",
                    "anti_cheat": {
                        "opaque_labels": True,
                        "bundle_level_split_preserved": True,
                        "freeform_rows_excluded": True,
                        "compact_prompt_contract": True,
                        "train_only_invalid_for_eval_bundle": True,
                        "reviewed_abstention_support_only": True,
                        "raw_changed_path_list_not_exposed": True,
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
                        "projection_stage": 10110,
                        "projection_mode": "real_session_shortcut_safe_successor_prompt_surface",
                        "gold_answers_path": None,
                        "original_answer_kind": "abstain",
                        "gold_value": "ABSTAIN_INSUFFICIENT_EVIDENCE",
                        "opaque_options": [{"label": label, "value": value} for label, value in options],
                        "train_only_invalid_for_eval_bundle": True,
                        "bundle_valid_for_eval": False,
                        "review_packet_dir": display(packet_dir),
                        "source_packet_row_id": row_id,
                        "ai_adjudicated_abstain_reason": "Prompt-visible evidence does not justify exactly one implementation candidate; abstention is the honest train-only support label.",
                        "review_state": {
                            "rubric_passed": bool(rubric.get("passed")),
                            "anti_cheat_passed": bool(anti_cheat.get("passed")),
                            "rubric_status": str(rubric.get("status") or ""),
                            "anti_cheat_status": str(anti_cheat.get("status") or ""),
                            "selected_tests_count": len(hidden.get("selected_tests") or []),
                            "candidate_count": len(choices),
                        },
                    },
                }
            )
        manifest.append(
            {
                "bundle_id": bundle_id,
                "row_id": row_id,
                "status": "recovered_from_stage10110_successor_packet",
                "rows_emitted": 2,
                "bundle_valid_for_eval": False,
                "ai_adjudicated_abstain_only": True,
            }
        )
    return compiled, manifest


def compile_train_only_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    bundles = preview_bundles()
    compiled: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    for bundle_id in TRAIN_ONLY_BUNDLES:
        bundle = bundles.get(bundle_id)
        if not bundle:
            manifest.append({"bundle_id": bundle_id, "status": "missing_preview_bundle"})
            continue
        packet_dir = REVIEW_ROOT / bundle_id.replace("::", "__")
        gold = load_json(packet_dir / "perspective_gold_adjudication.json")
        rubric = load_json(packet_dir / "expert_maintainer_rubric_review.json")
        answers = [row for row in gold.get("perspective_gold_answers") or [] if isinstance(row, dict)]
        emitted = 0
        for answer in answers:
            perspective = str(answer.get("perspective") or "")
            if perspective not in TARGET_PERSPECTIVES:
                continue
            if str(answer.get("gold_answer_kind") or "") != "abstain":
                continue
            if str(answer.get("gold_answer_value") or "") != "ABSTAIN_INSUFFICIENT_EVIDENCE":
                continue
            contracts = {
                str(row.get("perspective") or ""): row.get("prompt_contract")
                for row in bundle.get("perspective_rows") or []
                if isinstance(row, dict)
            }
            contract = contracts.get(perspective) or {}
            values = build_option_values(answer, contract)
            if len(values) > len(CHOICE_LABELS):
                raise ValueError(f"too_many_options::{bundle_id}::{perspective}")
            seed = f"train_only_aux::{bundle_id}::{perspective}"
            canonical = stable_order(values, seed)
            reverse = list(reversed(canonical))
            for idx, ordered in enumerate([canonical, reverse]):
                options = list(zip(CHOICE_LABELS[: len(ordered)], ordered))
                label_by_value = {value: label for label, value in options}
                prompt = compile_prompt(bundle, perspective, contract, options=options)
                row = {
                    "row_id": f"{bundle_id}::{perspective}::train_only_aux_abstain::{idx:02d}",
                    "language_family": str(bundle.get("language_family") or ""),
                    "route": "KEEP_BOUNDED_DECODER",
                    "objective_family": "bounded_decoder_ce",
                    "surface": "maintainer_bundle_compact_bounded_choice",
                    "task_type": perspective,
                    "split": "train",
                    "prompt_text": prompt,
                    "input_text": prompt,
                    "query_text": f"train_only_aux::{bundle.get('language_family')}::{perspective}::abstain::{idx:02d}",
                    "target_text": label_by_value["ABSTAIN_INSUFFICIENT_EVIDENCE"],
                    "decoder_text": label_by_value["ABSTAIN_INSUFFICIENT_EVIDENCE"],
                    "target_token_len": len(label_by_value["ABSTAIN_INSUFFICIENT_EVIDENCE"].encode("utf-8")),
                    "loss_mask": {"decoder_ce": True},
                    "expected_enabled_loss": "decoder_ce",
                    "disable_losses": ["denoise_ce", "runtime_reward", "structured_aux"],
                    "source_skill_area": "maintainer_bundle_compact_bounded_choice",
                    "source_stage": STAGE,
                    "source_row_id": f"{bundle_id}::{perspective}",
                    "source_bundle_id": bundle_id,
                    "semantic_key": f"maintainer_bundle_train_only_aux::{bundle_id}::{perspective}::{idx:02d}",
                    "anti_cheat": {
                        "opaque_labels": True,
                        "bundle_level_split_preserved": True,
                        "freeform_rows_excluded": True,
                        "compact_prompt_contract": True,
                        "train_only_invalid_for_eval_bundle": True,
                        "reviewed_abstention_support_only": True,
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
                        "projection_stage": 10119,
                        "projection_mode": "compact_bounded_choice_auxiliary",
                        "gold_answers_path": display(packet_dir / "perspective_gold_adjudication.json"),
                        "original_answer_kind": "abstain",
                        "gold_value": "ABSTAIN_INSUFFICIENT_EVIDENCE",
                        "opaque_options": [{"label": label, "value": value} for label, value in options],
                        "train_only_invalid_for_eval_bundle": True,
                        "bundle_valid_for_eval": bool(rubric.get("bundle_valid_for_eval")),
                        "review_packet_dir": display(packet_dir),
                    },
                }
                compiled.append(row)
                emitted += 1
        manifest.append(
            {
                "bundle_id": bundle_id,
                "status": "compiled",
                "review_bundle_valid_for_eval": bool(rubric.get("bundle_valid_for_eval")),
                "rows_emitted": emitted,
            }
        )
    if compiled:
        return compiled, manifest
    return compile_recovered_successor_rows()


def label_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get("target_text") or "")
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def build_package() -> dict[str, Any]:
    base_package = load_json(BASE_PACKAGE)
    train_rows = load_jsonl(ROOT / str(base_package.get("train_dataset_path") or ""))
    eval_rows = load_jsonl(ROOT / str(base_package.get("eval_dataset_path") or ""))
    extra_rows, extra_manifest = compile_train_only_rows()
    final_train = train_rows + extra_rows
    write_jsonl(TRAIN_JSONL, final_train)
    write_jsonl(EVAL_JSONL, eval_rows)
    metrics = {
        "base_train_rows": len(train_rows),
        "base_strict_eval_rows": len(eval_rows),
        "extra_train_rows": len(extra_rows),
        "final_train_rows": len(final_train),
        "final_strict_eval_rows": len(eval_rows),
        "train_label_counts": label_counts(final_train),
        "strict_eval_label_counts": label_counts(eval_rows),
    }
    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "source_package": display(BASE_PACKAGE),
        "passed": bool(extra_rows) and bool(eval_rows),
        "metrics": metrics,
        "train_only_bundle_manifest": extra_manifest,
        "train_dataset_path": display(TRAIN_JSONL),
        "eval_dataset_path": display(EVAL_JSONL),
        "fit_for": {
            "standalone_decoder_ce_training": True,
            "full_product_harness_training": False,
            "expert_maintainer_primary_score": False,
            "compact_bounded_auxiliary_projection_only": True,
        },
        "required_honesty_gates": [
            "strict eval rows are copied unchanged from stage10200",
            "extra c_cpp support rows come only from reviewed-but-eval-invalid abstention bundles or stored stage10110 successor prompt surfaces and remain train-only auxiliary",
            "these bundles do not support benchmark promotion and exist only to regularize abstention honesty",
            "stage10142 standalone decoder contract audit remains binding for any score claim",
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
            "train_only_bundle_manifest": extra_manifest,
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
                "train_only_bundle_manifest": package["train_only_bundle_manifest"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
