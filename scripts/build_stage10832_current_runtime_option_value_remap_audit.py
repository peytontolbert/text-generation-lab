#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import time

import torch
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit


ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10832
NAME = "stage10832_current_runtime_option_value_remap_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "current_runtime_option_value_remap_audit.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage10829_evidence_role_support_probe" / "runtime_model" / "runtime_model_bundle.json"
STRICT_ROWS = ARTIFACTS / "stage10827_evidence_role_augmented_support_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
EVAL_ROWS = ARTIFACTS / "stage10827_evidence_role_augmented_support_package" / "agentkernel_lite_encdec_validation.jsonl"

ROLE_MAP = {
    "algorithmic_background_reference": "background algorithm reference",
    "candidate_change_surface": "current proposed edit surface",
    "external_analogue_reference": "external analogue reference",
    "nearby_definition_or_usage_context": "nearby definition or usage context",
    "symptom_or_call_path_analogue": "symptom or call path analogue",
    "verifier_and_test_constraint": "failing verifier or test constraint",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


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
            value = str(option.get("value") or "")
            option["value"] = mapped_value(value)
    root_options = new_row.get("opaque_options")
    if isinstance(root_options, list):
        for option in root_options:
            if isinstance(option, dict):
                value = str(option.get("value") or "")
                option["value"] = mapped_value(value)
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
    task_summary: dict[str, dict[str, Any]] = {}
    for row in rows:
        task = str(row["row_id"]).split("::")[-2]
        stats = task_summary.setdefault(task, {"correct": 0, "total": 0, "exact": 0.0})
        stats["total"] += 1
        if row.get("constrained_choice_match") is True:
            stats["correct"] += 1
    for stats in task_summary.values():
        stats["exact"] = stats["correct"] / stats["total"] if stats["total"] else 0.0
    return {
        "rows": card.get("rows"),
        "constrained_choice_top1_accuracy": card.get("constrained_choice_top1_accuracy"),
        "full_vocab_top1_accuracy": card.get("full_vocab_top1_accuracy"),
        "rows_with_target_rank_1": card.get("rows_with_target_rank_1"),
        "task_summary": dict(sorted(task_summary.items())),
        "misses": [row for row in rows if row.get("constrained_choice_match") is not True],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    strict_rows = load_rows(STRICT_ROWS)
    eval_rows = load_rows(EVAL_ROWS)
    model, tokenizer = load_runtime()

    variants = {
        "raw": (strict_rows, eval_rows),
        "task_role_templated": (
            [remap_row(row, "task_role_templated") for row in strict_rows],
            [remap_row(row, "task_role_templated") for row in eval_rows],
        ),
        "role_map_templated": (
            [remap_row(row, "role_map_templated") for row in strict_rows],
            [remap_row(row, "role_map_templated") for row in eval_rows],
        ),
        "dynamic_productized": (
            [remap_row(row, "dynamic_productized") for row in strict_rows],
            [remap_row(row, "dynamic_productized") for row in eval_rows],
        ),
    }

    results = {}
    for variant_name, (strict_variant_rows, eval_variant_rows) in variants.items():
        strict_card = _write_bounded_choice_eval_audit(
            OUT_DIR,
            model=model,
            rows=strict_variant_rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=8,
            split_name=f"strict_eval_{variant_name}",
            bounded_choice_aux_source="encoder_option_retrieval",
            eval_batch_size=8,
        )
        eval_card = _write_bounded_choice_eval_audit(
            OUT_DIR,
            model=model,
            rows=eval_variant_rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=8,
            split_name=f"eval_{variant_name}",
            bounded_choice_aux_source="encoder_option_retrieval",
            eval_batch_size=8,
        )
        results[variant_name] = {
            "strict_eval": summarize(strict_card),
            "eval": summarize(eval_card),
        }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "runtime_bundle": str(RUNTIME_BUNDLE.relative_to(ROOT)),
        "strict_manifest": str(STRICT_ROWS.relative_to(ROOT)),
        "eval_manifest": str(EVAL_ROWS.relative_to(ROOT)),
        "results": results,
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
