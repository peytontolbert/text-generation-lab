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

NAME = "stage10383_option_text_variant_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = ROOT / "runs/local/artifacts/stage10378_balanced_residual_probe_execution_request/balanced_residual_probe_manifest.jsonl"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10379_balanced_residual_probe/runtime_model/runtime_model_bundle.json"


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


def _header_prefix(row: dict[str, object]) -> str:
    prompt = str(row.get("prompt_text") or "")
    before_evidence = prompt.split("\nEvidence:\n", 1)[0].strip()
    return before_evidence


def _perspective(row: dict[str, object]) -> str:
    prompt = str(row.get("prompt_text") or "")
    for line in prompt.splitlines():
        if line.startswith("Perspective: "):
            return line.split(": ", 1)[1].strip()
    return ""


def _variant_texts(row: dict[str, object], value: str) -> dict[str, str]:
    header = _header_prefix(row)
    perspective = _perspective(row)
    variants = {
        "raw_value": value,
        "header_only": f"{header}\nCandidate under review: {value}" if header else f"Candidate under review: {value}",
        "task_templated": f"Perspective={perspective}\nCandidate answer under review: {value}",
    }
    if perspective == "evidence_citation":
        variants["task_role_templated"] = f"Perspective=evidence_citation\nVisible fact role under review: {value}"
    elif perspective == "verifier_outcome":
        variants["task_role_templated"] = f"Perspective=verifier_outcome\nVerifier or test target under review: {value}"
    elif perspective == "abstention_insufficient_evidence":
        variants["task_role_templated"] = f"Perspective=abstention_insufficient_evidence\nCandidate answer under review: {value}"
    else:
        variants["task_role_templated"] = f"Perspective={perspective}\nCandidate under review: {value}"
    return variants


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


def _score_variant(model: AgentKernelLiteTransformerSeq2Seq, tokenizer: AgentKernelBPETokenizer, row: dict[str, object], variant_name: str) -> dict[str, object]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    query = out["pooled"][0:1]
    retrieval_query_head = getattr(model, "retrieval_query_head", None)
    retrieval_doc_head = getattr(model, "retrieval_doc_head", None)
    if retrieval_query_head is not None:
        query = retrieval_query_head(query)
    option_pairs = _option_pairs(row)
    option_texts = [_variant_texts(row, value)[variant_name] for _, value in option_pairs]
    option_vectors = _encode_option_texts(model, tokenizer, option_texts, query.device)
    if retrieval_doc_head is not None:
        option_vectors = retrieval_doc_head(option_vectors)
    query = F.normalize(query.float(), dim=-1)
    option_vectors = F.normalize(option_vectors.float(), dim=-1)
    logits = torch.matmul(query, option_vectors.transpose(0, 1)).squeeze(0)
    scored = [
        {
            "label": label,
            "value": value,
            "logit": float(logits[idx].item()),
        }
        for idx, (label, value) in enumerate(option_pairs)
    ]
    scored.sort(key=lambda item: item["logit"], reverse=True)
    return {
        "pred": scored[0]["label"],
        "target": row["decoder_text"],
        "correct": scored[0]["label"] == row["decoder_text"],
        "top3": scored[:3],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _load_rows()
    model, tokenizer = _load_runtime()
    variant_names = ["raw_value", "header_only", "task_templated", "task_role_templated"]
    results: dict[str, dict[str, object]] = {}
    for variant_name in variant_names:
        row_results = []
        correct = 0
        for row in rows:
            result = _score_variant(model, tokenizer, row, variant_name)
            row_results.append({"row_id": row["row_id"], **result})
            correct += int(result["correct"])
        results[variant_name] = {
            "rows": len(rows),
            "correct": correct,
            "accuracy": correct / len(rows),
            "misses": [row for row in row_results if not row["correct"]],
        }
    out_path = OUT_DIR / "option_text_variant_audit.json"
    out_path.write_text(json.dumps({"runtime_bundle": str(RUNTIME_BUNDLE), "results": results}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
