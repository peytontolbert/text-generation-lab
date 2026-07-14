#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10362
NAME = "stage10362_source_backed_cpp_rust_citation_support_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
INVENTORY_JSON = OUT_DIR / "source_backed_cpp_rust_citation_support_inventory.json"
MANIFEST_JSONL = OUT_DIR / "source_backed_cpp_rust_citation_support_manifest.jsonl"
REQUEST_JSON = OUT_DIR / "source_backed_cpp_rust_citation_support_execution_request.json"
COMMAND_JSON = OUT_DIR / "source_backed_cpp_rust_citation_support_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10360_cpp_verifier_citation_support_execution_request/cpp_verifier_citation_support_manifest.jsonl"
ADMITTED_MANIFEST = ROOT / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_admitted_manifest.json"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10359_anchored_citation_plus_pythonverifier_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10363_source_backed_cpp_rust_citation_support_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10363_source_backed_cpp_rust_citation_support_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10363_source_backed_cpp_rust_citation_support_probe/runtime_model"
MAX_STEPS = 20
LEARNING_RATE = "4e-6"
BATCH_SIZE = 2
CHOICE_LABELS = list("ABCDEFGHJKLMNOPQRSTUVWXYZ")

SELECTED = [
    {
        "bundle_id": "stage10119::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_26t17_53_18_019d2b47_7d2d_7622_8e05_3513_agent_kernel_modeling_ssm_kernels_src_selective_scan_cpp_agent_kernel_modeling_w_5511e7fec6_aug_1500000_8b46e7f662::c_cpp",
        "gold_value": "verifier_and_test_constraint",
        "repeats": 2,
        "support_family": "source_backed_cpp_verifier_constraint",
        "ai_review": {
            "expert_passed": True,
            "anti_cheat_passed": True,
            "selected_candidate_rationale": "The visible tests concentrate on improvement retention and artifact validation behavior, so the verifier and test constraint is the strongest visible fact supporting the chosen edit target.",
            "anti_cheat_rationale": "The answer is grounded in prompt-visible selected tests and evidence buckets rather than hidden path metadata. This is train-only citation support and not a benchmark claim cell.",
        },
    },
    {
        "bundle_id": "stage10119::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_56_21_019d3560_1014_7761_9ea7_5638_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_causalmachine_cuda_a018ca0b43_aug_1500000_8b46e7f662::c_cpp",
        "gold_value": "verifier_and_test_constraint",
        "repeats": 2,
        "support_family": "source_backed_cpp_kernel_test_constraint",
        "ai_review": {
            "expert_passed": True,
            "anti_cheat_passed": True,
            "selected_candidate_rationale": "The prompt-visible selected tests directly target the muon CUDA and structured scan kernel behavior, so the verifier and test constraint is the clearest visible fact supporting the chosen edit target.",
            "anti_cheat_rationale": "This support row is justified by concrete test-path evidence rather than a changed-file prior. It remains train-only and permutation balanced.",
        },
    },
    {
        "bundle_id": "stage10126::tokenizers::tokenizers::rust",
        "gold_value": "symptom_or_call_path_analogue",
        "repeats": 2,
        "support_family": "source_backed_rust_tokenizers_symptom_path",
        "ai_review": {
            "expert_passed": True,
            "anti_cheat_passed": True,
            "selected_candidate_rationale": "The visible wasm example and related test path provide the strongest call-path analogue for the chosen edit target, stronger than the changed-candidate surface alone.",
            "anti_cheat_rationale": "The answer relies on the visible symptom/call-path evidence bucket, not on hidden bundle lineage. This is train-only auxiliary support.",
        },
    },
    {
        "bundle_id": "stage10126::candle::candle-core::rust",
        "gold_value": "symptom_or_call_path_analogue",
        "repeats": 2,
        "support_family": "source_backed_rust_candle_symptom_path",
        "ai_review": {
            "expert_passed": True,
            "anti_cheat_passed": True,
            "selected_candidate_rationale": "The visible primary signal points directly at the accelerate surface as the symptom or call-path analogue, making that bucket the strongest support for the chosen target.",
            "anti_cheat_rationale": "This bundle has no verifier bucket, so the answer is not driven by test presence; it is anchored to the visible symptom/call-path analogue itself. The row stays train-only.",
        },
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


def snippet(text: str, limit: int = 280) -> str:
    clean = " ".join(str(text).split())
    return clean if len(clean) <= limit else clean[: max(0, limit - 3)] + "..."


def rotate(values: list[str], shift: int) -> list[str]:
    return values[shift:] + values[:shift]


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
        source_type = str(first.get("source_type") or "")
        text = snippet(str(first.get("text") or ""))
        prefix = key
        if path:
            prefix += f" [{path}]"
        elif source_type:
            prefix += f" [{source_type}]"
        lines.append(f"{prefix}: {text}")
    return lines[:6]


def prompt_for(bundle: dict[str, Any], *, options: list[tuple[str, str]]) -> str:
    perspective = "evidence_citation"
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
    for label, value in options:
        parts.append(f"{label}. {value}")
    parts.append("Answer:")
    return "\n".join(parts) + "\n"


def bundle_map() -> dict[str, dict[str, Any]]:
    data = load_json(ADMITTED_MANIFEST)
    bundles = [row for row in data.get("rows") or [] if isinstance(row, dict)]
    return {str(bundle.get("bundle_id") or ""): bundle for bundle in bundles}


def build_support_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    bundles = bundle_map()
    train_rows: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []
    for spec in SELECTED:
        bundle_id = spec["bundle_id"]
        bundle = bundles.get(bundle_id)
        if bundle is None:
            raise KeyError(f"missing_bundle::{bundle_id}")
        contract = contract_for(bundle, "evidence_citation")
        visible_keys = [str(v) for v in contract.get("visible_evidence_keys") or [] if v]
        gold_value = str(spec["gold_value"])
        if gold_value not in visible_keys:
            raise ValueError(f"missing_gold_visible_key::{bundle_id}::{gold_value}")
        label_space = CHOICE_LABELS[: len(visible_keys)]
        inventory_rows.append(
            {
                "bundle_id": bundle_id,
                "language_family": bundle.get("language_family"),
                "repo_id": bundle.get("repo_id"),
                "support_family": spec["support_family"],
                "gold_value": gold_value,
                "visible_evidence_keys": visible_keys,
                "selected_tests": list(contract.get("selected_tests") or []),
                "candidate_paths": list(contract.get("candidate_paths") or []),
                "ai_review": spec["ai_review"],
                "repeats": spec["repeats"],
            }
        )
        for repeat_idx in range(int(spec["repeats"])):
            for shift in range(len(visible_keys)):
                ordered_values = rotate(visible_keys, shift)
                options = list(zip(label_space, ordered_values))
                label_by_value = {value: label for label, value in options}
                prompt = prompt_for(bundle, options=options)
                train_rows.append(
                    {
                        "row_id": f"stage10362::{spec['support_family']}::{bundle_id}::repeat_{repeat_idx:02d}::perm_{shift:02d}",
                        "semantic_key": f"stage10362::{spec['support_family']}::{bundle.get('language_family')}::{gold_value}::perm_{shift:02d}",
                        "bundle_id": bundle_id,
                        "language_family": bundle.get("language_family"),
                        "route": "DIRECT_ANSWER_MAINTAINER_BUNDLE_COMPACT_BOUNDED",
                        "objective_family": "maintainer_bundle_compact_bounded_choice",
                        "surface": "maintainer_bundle_compact_bounded_choice",
                        "task_type": "evidence_citation",
                        "perspective": "evidence_citation",
                        "split": "train",
                        "prompt_text": prompt,
                        "input_text": prompt,
                        "query_text": f"stage10362::{spec['support_family']}::{bundle.get('language_family')}::repeat_{repeat_idx:02d}::perm_{shift:02d}",
                        "target_text": label_by_value[gold_value],
                        "decoder_text": label_by_value[gold_value],
                        "target_token_len": len(label_by_value[gold_value].encode("utf-8")),
                        "loss_mask": {"decoder_ce": True},
                        "expected_enabled_loss": "decoder_ce",
                        "disable_losses": [],
                        "source_stage": 10129,
                        "source_bundle_id": bundle_id,
                        "source_row_id": f"{bundle_id}::evidence_citation",
                        "source_skill_area": "maintainer_bundle_compact_bounded_choice",
                        "standalone_projection_source": {
                            "projection_mode": "admitted_bundle_visible_evidence_support",
                            "projection_stage": STAGE,
                            "gold_value": gold_value,
                            "original_answer_kind": "visible_evidence_key",
                            "opaque_options": [{"label": label, "value": value} for label, value in options],
                            "visible_evidence_keys": visible_keys,
                            "candidate_paths": list(contract.get("candidate_paths") or []),
                            "selected_tests": list(contract.get("selected_tests") or []),
                            "support_family": spec["support_family"],
                            "admitted_bundle_manifest": display(ADMITTED_MANIFEST),
                            "ai_review": spec["ai_review"],
                            "claim_boundary": {
                                "train_support_only": True,
                                "same_surface_eval_admissible": False,
                                "source_backed_maintainer_bundle": True,
                            },
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
                        "anti_cheat": {
                            "prompt_visible_only_review": True,
                            "source_backed_maintainer_bundle": True,
                            "permutation_balanced_labels": True,
                            "train_support_only": True,
                            "not_for_primary_maintainer_claim": True,
                            "ai_review_completed_in_repo": True,
                            "same_surface_eval_admissible": False,
                        },
                    }
                )
    return train_rows, inventory_rows


def build_command(split_counts: dict[str, int]) -> list[str]:
    return [
        "env",
        f"TMPDIR={TMPDIR}",
        f"TEMP={TMPDIR}",
        f"TMP={TMPDIR}",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str(TRAINER),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST_JSONL),
        "--mode",
        "bounded_decoder_ce_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str(MODEL_CONFIG),
        "--tokenizer-json",
        str(TOKENIZER_JSON),
        "--tokenizer-config",
        str(TOKENIZER_CONFIG),
        "--tokenizer-hashlock",
        str(TOKENIZER_HASHLOCK),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows",
        str(split_counts.get("train", 0)),
        "--max-eval-rows",
        "0",
        "--max-strict-rows",
        str(split_counts.get("strict_eval", 0)),
        "--max-steps",
        str(MAX_STEPS),
        "--batch-size",
        str(BATCH_SIZE),
        "--learning-rate",
        LEARNING_RATE,
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "8",
        "--decoder-ce-weight",
        "0.2",
        "--bounded-choice-aux-weight",
        "1.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--eos-loss-weight",
        "4.0",
        "--enable-generation-audit",
        "--max-generation-rows",
        "16",
        "--max-generation-tokens",
        "8",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-kl-weight",
        "2.0",
        "--output-dir",
        OUTPUT_DIR,
        "--run-id",
        RUN_ID,
    ]


def main() -> None:
    base_rows = load_jsonl(BASE_MANIFEST)
    support_rows, inventory_rows = build_support_rows()
    combined_rows = support_rows + base_rows
    split_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    for row in combined_rows:
        split = str(row.get("split") or "unknown")
        split_counts[split] = split_counts.get(split, 0) + 1
        lang = str(row.get("language_family") or "unknown")
        language_counts[lang] = language_counts.get(lang, 0) + 1
    command = build_command(split_counts)
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "source_backed_cpp_rust_citation_support_ready",
        "manifest": display(MANIFEST_JSONL),
        "source_manifests": {
            "base": display(BASE_MANIFEST),
            "admitted_bundles": display(ADMITTED_MANIFEST),
            "inventory": display(INVENTORY_JSON),
        },
        "split_counts": split_counts,
        "language_counts": language_counts,
        "rows": len(combined_rows),
        "frontloaded_support_rows": len(support_rows),
        "support_summary": {
            "selected_bundles": len(SELECTED),
            "cpp_support_rows": sum(1 for row in support_rows if row.get("language_family") == "c_cpp"),
            "rust_support_rows": sum(1 for row in support_rows if row.get("language_family") == "rust"),
            "support_families": [spec["support_family"] for spec in SELECTED],
        },
        "initialize_from_runtime_model": display(INIT_RUNTIME),
        "preservation": {
            "reference_runtime_model": display(INIT_RUNTIME),
            "kl_weight": 2.0,
        },
        "max_steps": MAX_STEPS,
        "learning_rate": LEARNING_RATE,
        "required_honesty_gates": [
            "strict eval rows remain identical to stage10359 frontier",
            "new rows are train-support-only and excluded from same-surface benchmark claims",
            "support rows come from admitted source-backed maintainer bundles rather than synthetic citation templates",
            "evidence_citation labels are permutation balanced within each bundle",
        ],
        "next_best_step": "run one warm-start probe and check whether source-backed c_cpp/rust citation positives repair the remaining semantic collapse without reintroducing Python verifier drift",
        "command": command,
        "output_dir": OUTPUT_DIR,
        "run_id": RUN_ID,
    }
    write_jsonl(MANIFEST_JSONL, combined_rows)
    write_json(INVENTORY_JSON, {"stage": STAGE, "selected": inventory_rows})
    write_json(COMMAND_JSON, {"command": command})
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY, {"stage": STAGE, "passed": True, "request": display(REQUEST_JSON)})
    print(json.dumps({"stage": STAGE, "passed": True, "request": display(REQUEST_JSON)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
