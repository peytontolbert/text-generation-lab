#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer, build_batch
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle

NAME = "stage10392_frontier_citation_role_map_eval"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = ROOT / "runs/local/artifacts/stage10378_balanced_residual_probe_execution_request/balanced_residual_probe_manifest.jsonl"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10379_balanced_residual_probe/runtime_model/runtime_model_bundle.json"
EVIDENCE_ROLE_MAP = {
    "algorithmic_background_reference": "background algorithm reference",
    "candidate_change_surface": "current proposed edit surface",
    "external_analogue_reference": "external analogue reference",
    "nearby_definition_or_usage_context": "nearby definition or usage context",
    "symptom_or_call_path_analogue": "symptom or call path analogue",
    "verifier_and_test_constraint": "failing verifier or test constraint",
}


def _load_rows() -> list[dict[str, object]]:
    rows = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("split") == "strict_eval":
            rows.append(row)
    rows.sort(key=lambda row: str(row["row_id"]))
    return rows


def _load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer]:
    bundle = json.loads(RUNTIME_BUNDLE.read_text(encoding="utf-8"))
    metadata = bundle["metadata"]
    model_config = json.loads(Path(str(metadata["model_config"])).read_text(encoding="utf-8"))
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(model_config)
    model = AgentKernelLiteTransformerSeq2Seq(config)
    _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    model.eval()
    return model, tokenizer


def _option_pairs(row: dict[str, object]) -> list[tuple[str, str]]:
    options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    return [(str(option["label"]), str(option["value"])) for option in options]


def _language(row: dict[str, object]) -> str:
    return str(row.get("language_family") or "unknown")


def _perspective(row: dict[str, object]) -> str:
    prompt = str(row.get("prompt_text") or "")
    for line in prompt.splitlines():
        if line.startswith("Perspective: "):
            return line.split(": ", 1)[1].strip()
    return ""


def _option_variant(row: dict[str, object]) -> str:
    perspective = _perspective(row)
    language = _language(row)
    if perspective == "evidence_citation":
        return "evidence_citation_role_map"
    if language == "rust":
        return "task_role_templated"
    return "raw_value"


def _option_text(row: dict[str, object], value: str, variant: str) -> str:
    perspective = _perspective(row)
    if variant == "raw_value":
        return value
    if variant == "task_role_templated":
        if perspective == "verifier_outcome":
            return f"Verifier or test target under review: {value}"
        if perspective == "abstention_insufficient_evidence":
            return f"Candidate answer under review: {value}"
        if perspective == "evidence_citation":
            return f"Visible fact role under review: {value}"
        return f"Candidate under review: {value}"
    if variant == "evidence_citation_role_map":
        return EVIDENCE_ROLE_MAP.get(value, value)
    raise ValueError(f"unsupported option variant: {variant}")


def _encode_option_texts(model: AgentKernelLiteTransformerSeq2Seq, tokenizer: AgentKernelBPETokenizer, texts: list[str], device: torch.device) -> torch.Tensor:
    encoded_rows = []
    pad_id = int(getattr(tokenizer, "pad_id", 0))
    bos_id = int(getattr(tokenizer, "bos_id", 1))
    eos_id = int(getattr(tokenizer, "eos_id", 2))
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


def _score_row(model: AgentKernelLiteTransformerSeq2Seq, tokenizer: AgentKernelBPETokenizer, row: dict[str, object]) -> dict[str, object]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    query = out["pooled"][0:1]
    if getattr(model, "retrieval_query_head", None) is not None:
        query = model.retrieval_query_head(query)
    option_variant = _option_variant(row)
    option_pairs = _option_pairs(row)
    texts = [_option_text(row, value, option_variant) for _, value in option_pairs]
    option_vectors = _encode_option_texts(model, tokenizer, texts, query.device)
    if getattr(model, "retrieval_doc_head", None) is not None:
        option_vectors = model.retrieval_doc_head(option_vectors)
    query = F.normalize(query.float(), dim=-1)
    option_vectors = F.normalize(option_vectors.float(), dim=-1)
    logits = torch.matmul(query, option_vectors.transpose(0, 1)).squeeze(0)
    scored = [
        {
            "label": label,
            "value": value,
            "text": texts[idx],
            "logit": float(logits[idx].item()),
        }
        for idx, (label, value) in enumerate(option_pairs)
    ]
    scored.sort(key=lambda item: item["logit"], reverse=True)
    pred = scored[0]["label"]
    target = str(row["decoder_text"])
    return {
        "row_id": row["row_id"],
        "language_family": _language(row),
        "perspective": _perspective(row),
        "option_variant": option_variant,
        "target": target,
        "pred": pred,
        "correct": pred == target,
        "top3": scored[:3],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _load_rows()
    model, tokenizer = _load_runtime()
    row_cards = [_score_row(model, tokenizer, row) for row in rows]
    correct = sum(1 for row in row_cards if row["correct"])
    payload = {
        "stage_name": NAME,
        "runtime_bundle": str(RUNTIME_BUNDLE),
        "manifest": str(MANIFEST),
        "rows": len(row_cards),
        "correct": correct,
        "accuracy": correct / len(row_cards),
        "row_cards": row_cards,
    }
    out_path = OUT_DIR / "frontier_citation_role_map_eval.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
