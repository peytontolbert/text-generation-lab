#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit


ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10849
NAME = "stage10849_current_runtime_scoring_policy_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "current_runtime_scoring_policy_audit.json"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage10847_residual_family_rebalanced_probe" / "runtime_model" / "runtime_model_bundle.json"
STRICT_ROWS = ARTIFACTS / "stage10844_residual_family_rebalanced_support_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
EVAL_ROWS = ARTIFACTS / "stage10844_residual_family_rebalanced_support_package" / "agentkernel_lite_encdec_validation.jsonl"

ROLE_MAP = {
    "algorithmic_background_reference": "background algorithm reference",
    "candidate_change_surface": "current proposed edit surface",
    "external_analogue_reference": "external analogue reference",
    "nearby_definition_or_usage_context": "nearby definition or usage context",
    "symptom_or_call_path_analogue": "symptom or call path analogue",
    "verifier_and_test_constraint": "failing verifier or test constraint",
}

OPTION_SOURCES = [
    "encoder_option_retrieval",
    "encoder_option_retrieval_conditioned",
    "decoder_first_step",
]

VALUE_VARIANTS = [
    "raw",
    "task_role_templated",
    "role_map_templated",
    "dynamic_productized",
]

PY_STRICT_ROW = "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::verifier_outcome::reviewed_v27_compact"
RUST_STRICT_ROW = "stage10126::tokenizers::tokenizers::rust::evidence_citation::reviewed_v27_compact"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def perspective(row: dict[str, Any]) -> str:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    for line in prompt.splitlines():
        if line.startswith("Perspective: "):
            return line.split(": ", 1)[1].strip()
    return ""


def role_map_text(value: str) -> str:
    return f"Visible fact role under review: {ROLE_MAP.get(value, value)}"


def remap_row(row: dict[str, Any], variant: str) -> dict[str, Any]:
    new_row = copy.deepcopy(row)
    current_perspective = perspective(new_row)
    current_language = str(new_row.get("language_family") or "")
    if variant == "raw":
        return new_row

    def mapped_value(value: str) -> str:
        if variant == "role_map_templated" and current_perspective == "evidence_citation":
            return role_map_text(value)
        if variant == "task_role_templated":
            if current_perspective == "evidence_citation":
                return f"Visible fact role under review: {value}"
            if current_perspective == "verifier_outcome":
                return f"Verifier or test target under review: {value}"
            if current_perspective == "abstention_insufficient_evidence":
                return f"Candidate answer under review: {value}"
            return f"Candidate under review: {value}"
        if variant == "dynamic_productized":
            if current_perspective == "evidence_citation":
                return f"Visible fact role under review: {value}"
            if current_language == "rust":
                if current_perspective == "verifier_outcome":
                    return f"Verifier or test target under review: {value}"
                if current_perspective == "abstention_insufficient_evidence":
                    return f"Candidate answer under review: {value}"
                return f"Candidate under review: {value}"
        return value

    options = (((new_row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    for option in options:
        if isinstance(option, dict):
            option["value"] = mapped_value(str(option.get("value") or ""))
    root_options = new_row.get("opaque_options")
    if isinstance(root_options, list):
        for option in root_options:
            if isinstance(option, dict):
                option["value"] = mapped_value(str(option.get("value") or ""))
    projection = new_row.get("standalone_projection_source")
    if isinstance(projection, dict):
        projection["option_value_variant"] = variant
    new_row["option_value_variant"] = variant
    return new_row


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    if torch.cuda.is_available():
        model = model.to(torch.device("cuda"))
    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    model.eval()
    return model, tokenizer


def summarize(card: dict[str, Any]) -> dict[str, Any]:
    rows = card.get("row_cards") or []
    return {
        "rows": card.get("rows"),
        "constrained_choice_top1_accuracy": card.get("constrained_choice_top1_accuracy"),
        "full_vocab_top1_accuracy": card.get("full_vocab_top1_accuracy"),
        "rows_with_target_rank_1": card.get("rows_with_target_rank_1"),
        "misses": [row for row in rows if row.get("constrained_choice_match") is not True],
        "python_strict": next((row for row in rows if row.get("row_id") == PY_STRICT_ROW), None),
        "rust_strict": next((row for row in rows if row.get("row_id") == RUST_STRICT_ROW), None),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    strict_rows = load_rows(STRICT_ROWS)
    eval_rows = load_rows(EVAL_ROWS)
    model, tokenizer = load_runtime()

    results: dict[str, Any] = {}
    best = {
        "strict_accuracy": -1.0,
        "eval_accuracy": -1.0,
        "variant": None,
        "source": None,
    }

    for variant in VALUE_VARIANTS:
        strict_variant_rows = [remap_row(row, variant) for row in strict_rows]
        eval_variant_rows = [remap_row(row, variant) for row in eval_rows]
        for source in OPTION_SOURCES:
            strict_card = _write_bounded_choice_eval_audit(
                OUT_DIR,
                model=model,
                rows=strict_variant_rows,
                tokenizer=tokenizer,
                max_encoder_tokens=768,
                max_decoder_tokens=8,
                split_name=f"strict_eval_{variant}_{source}",
                bounded_choice_aux_source=source,
                eval_batch_size=8,
            )
            eval_card = _write_bounded_choice_eval_audit(
                OUT_DIR,
                model=model,
                rows=eval_variant_rows,
                tokenizer=tokenizer,
                max_encoder_tokens=768,
                max_decoder_tokens=8,
                split_name=f"eval_{variant}_{source}",
                bounded_choice_aux_source=source,
                eval_batch_size=8,
            )
            strict_summary = summarize(strict_card)
            eval_summary = summarize(eval_card)
            key = f"{variant}__{source}"
            results[key] = {
                "value_variant": variant,
                "option_source": source,
                "strict_eval": strict_summary,
                "eval": eval_summary,
            }
            if strict_summary["constrained_choice_top1_accuracy"] > best["strict_accuracy"] or (
                strict_summary["constrained_choice_top1_accuracy"] == best["strict_accuracy"]
                and eval_summary["constrained_choice_top1_accuracy"] > best["eval_accuracy"]
            ):
                best = {
                    "strict_accuracy": strict_summary["constrained_choice_top1_accuracy"],
                    "eval_accuracy": eval_summary["constrained_choice_top1_accuracy"],
                    "variant": variant,
                    "source": source,
                }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "runtime_bundle": str(RUNTIME_BUNDLE.relative_to(ROOT)),
        "strict_manifest": str(STRICT_ROWS.relative_to(ROOT)),
        "eval_manifest": str(EVAL_ROWS.relative_to(ROOT)),
        "best_policy": best,
        "results": results,
    }
    write_json(OUT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": "current_runtime_scoring_policy_audit_complete",
            "best_policy": best,
            "artifact": str(OUT_JSON.relative_to(ROOT)),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
