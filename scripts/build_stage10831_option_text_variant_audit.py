#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer, build_batch
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _move_manifest_batch


ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10831
NAME = "stage10831_option_text_variant_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "option_text_variant_audit.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage10829_evidence_role_support_probe" / "runtime_model" / "runtime_model_bundle.json"
STRICT_ROWS = ARTIFACTS / "stage10827_evidence_role_augmented_support_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
EVAL_ROWS = ARTIFACTS / "stage10827_evidence_role_augmented_support_package" / "agentkernel_lite_encdec_validation.jsonl"

EVIDENCE_ROLE_MAP = {
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


def language(row: dict[str, Any]) -> str:
    return str(row.get("language_family") or "unknown")


def option_pairs(row: dict[str, Any]) -> list[tuple[str, str]]:
    options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    pairs: list[tuple[str, str]] = []
    for option in options:
        if isinstance(option, dict):
            pairs.append((str(option.get("label") or ""), str(option.get("value") or "")))
    return [(label, value) for label, value in pairs if label]


def option_variant(row: dict[str, Any], variant_name: str) -> str:
    if variant_name != "dynamic_productized":
        return variant_name
    current_perspective = perspective(row)
    current_language = language(row)
    if current_perspective == "evidence_citation":
        return "evidence_citation_role_map_templated"
    if current_language == "rust":
        return "task_role_templated"
    return "raw_value"


def option_text(row: dict[str, Any], value: str, variant_name: str) -> str:
    chosen = option_variant(row, variant_name)
    current_perspective = perspective(row)
    if chosen == "raw_value":
        return value
    if chosen == "task_role_templated":
        if current_perspective == "evidence_citation":
            return f"Visible fact role under review: {value}"
        if current_perspective == "verifier_outcome":
            return f"Verifier or test target under review: {value}"
        if current_perspective == "abstention_insufficient_evidence":
            return f"Candidate answer under review: {value}"
        return f"Candidate under review: {value}"
    if chosen == "evidence_citation_role_map_templated":
        return f"Visible fact role under review: {EVIDENCE_ROLE_MAP.get(value, value)}"
    raise ValueError(f"unsupported option variant: {chosen}")


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    model_config = load_json(Path(str(metadata["model_config"])))
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(model_config)
    model = AgentKernelLiteTransformerSeq2Seq(config)
    _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    model.eval()
    return model, tokenizer


def encode_option_texts(
    *,
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    texts: list[str],
    device: torch.device,
) -> torch.Tensor:
    pad_id = int(getattr(tokenizer, "pad_id", 0))
    bos_id = int(getattr(tokenizer, "bos_id", 1))
    eos_id = int(getattr(tokenizer, "eos_id", 2))
    encoded_rows: list[list[int]] = []
    for text in texts:
        token_ids = [idx for idx in tokenizer.encode(text, max_length=768) if idx not in {bos_id, eos_id}]
        if not token_ids:
            token_ids = [pad_id]
        encoded_rows.append(token_ids)
    width = max(len(ids) for ids in encoded_rows)
    input_ids = torch.full((len(encoded_rows), width), pad_id, dtype=torch.long, device=device)
    attention_mask = torch.zeros((len(encoded_rows), width), dtype=torch.bool, device=device)
    for row_idx, token_ids in enumerate(encoded_rows):
        input_ids[row_idx, : len(token_ids)] = torch.tensor(token_ids, dtype=torch.long, device=device)
        attention_mask[row_idx, : len(token_ids)] = True
    return model.encode_pooled(input_ids, attention_mask)


def score_row(
    *,
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    row: dict[str, Any],
    variant_name: str,
) -> dict[str, Any]:
    device = next(model.parameters()).device
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    batch = _move_manifest_batch(batch, device)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    query = out["pooled"][0:1]
    retrieval_query_head = getattr(model, "retrieval_query_head", None)
    retrieval_doc_head = getattr(model, "retrieval_doc_head", None)
    if retrieval_query_head is not None:
        query = retrieval_query_head(query)
    pairs = option_pairs(row)
    texts = [option_text(row, value, variant_name) for _, value in pairs]
    option_vectors = encode_option_texts(model=model, tokenizer=tokenizer, texts=texts, device=device)
    if retrieval_doc_head is not None:
        option_vectors = retrieval_doc_head(option_vectors)
    query = F.normalize(query.float(), dim=-1)
    option_vectors = F.normalize(option_vectors.float(), dim=-1)
    logits = torch.matmul(query, option_vectors.transpose(0, 1)).squeeze(0)
    best_idx = int(torch.argmax(logits).item())
    best_label, best_value = pairs[best_idx]
    top_items = []
    for idx, (label, value) in enumerate(pairs):
        top_items.append(
            {
                "label": label,
                "value": value,
                "text": texts[idx],
                "logit": float(logits[idx].item()),
            }
        )
    top_items.sort(key=lambda item: item["logit"], reverse=True)
    return {
        "row_id": str(row.get("row_id") or ""),
        "language_family": language(row),
        "task_type": str(row.get("task_type") or ""),
        "perspective": perspective(row),
        "target_label": str(row.get("decoder_text") or row.get("target_text") or ""),
        "predicted_label": best_label,
        "predicted_value": best_value,
        "correct": best_label == str(row.get("decoder_text") or row.get("target_text") or ""),
        "variant_used": option_variant(row, variant_name),
        "top3": top_items[:3],
    }


def summarize_split(
    *,
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    rows: list[dict[str, Any]],
    variant_name: str,
) -> dict[str, Any]:
    row_cards = [score_row(model=model, tokenizer=tokenizer, row=row, variant_name=variant_name) for row in rows]
    correct = sum(1 for row in row_cards if row["correct"])
    by_task: dict[str, dict[str, Any]] = {}
    for row in row_cards:
        stats = by_task.setdefault(row["task_type"], {"correct": 0, "total": 0, "exact": 0.0})
        stats["total"] += 1
        if row["correct"]:
            stats["correct"] += 1
    for stats in by_task.values():
        stats["exact"] = stats["correct"] / stats["total"] if stats["total"] else 0.0
    return {
        "rows": len(row_cards),
        "correct": correct,
        "accuracy": correct / len(row_cards) if row_cards else 0.0,
        "task_summary": dict(sorted(by_task.items())),
        "misses": [row for row in row_cards if not row["correct"]],
        "row_cards": row_cards,
    }


def main() -> None:
    model, tokenizer = load_runtime()
    strict_rows = load_rows(STRICT_ROWS)
    eval_rows = load_rows(EVAL_ROWS)
    variants = [
        "raw_value",
        "task_role_templated",
        "evidence_citation_role_map_templated",
        "dynamic_productized",
    ]
    results = {}
    for variant_name in variants:
        results[variant_name] = {
            "strict_eval": summarize_split(model=model, tokenizer=tokenizer, rows=strict_rows, variant_name=variant_name),
            "eval": summarize_split(model=model, tokenizer=tokenizer, rows=eval_rows, variant_name=variant_name),
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
