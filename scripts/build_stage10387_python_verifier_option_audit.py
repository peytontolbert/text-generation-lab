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

NAME = "stage10387_python_verifier_option_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = ROOT / "runs/local/artifacts/stage10378_balanced_residual_probe_execution_request/balanced_residual_probe_manifest.jsonl"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10379_balanced_residual_probe/runtime_model/runtime_model_bundle.json"
TARGET_ROW_ID = (
    "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_"
    "models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::verifier_outcome::full_visible_compact_bounded"
)


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


def _perspective(row: dict[str, object]) -> str:
    prompt = str(row.get("prompt_text") or "")
    for line in prompt.splitlines():
        if line.startswith("Perspective: "):
            return line.split(": ", 1)[1].strip()
    return ""


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


def _basename(path_value: str) -> str:
    return Path(path_value).name


def _stem(path_value: str) -> str:
    return Path(path_value).stem


def _option_text(value: str, variant: str) -> str:
    if variant == "raw_value":
        return value
    if variant == "basename":
        return _basename(value)
    if variant == "stem":
        return _stem(value)
    if variant == "verifier_target_templated":
        return f"Verifier target under review: {value}"
    if variant == "verifier_target_basename_templated":
        return f"Verifier target under review: {_basename(value)}"
    if variant == "verifier_target_stem_templated":
        return f"Verifier target under review: {_stem(value)}"
    raise ValueError(f"unsupported option variant: {variant}")


def _score_row(
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    row: dict[str, object],
    *,
    option_variant: str,
) -> dict[str, object]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    query = out["pooled"][0:1]
    retrieval_query_head = getattr(model, "retrieval_query_head", None)
    retrieval_doc_head = getattr(model, "retrieval_doc_head", None)
    if retrieval_query_head is not None:
        query = retrieval_query_head(query)
    option_pairs = _option_pairs(row)
    texts = [_option_text(value, option_variant) for _, value in option_pairs]
    option_vectors = _encode_option_texts(model, tokenizer, texts, query.device)
    if retrieval_doc_head is not None:
        option_vectors = retrieval_doc_head(option_vectors)
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
    target_rows = [row for row in rows if row.get("row_id") == TARGET_ROW_ID]
    if len(target_rows) != 1:
        raise SystemExit(f"expected exactly one target row, found {len(target_rows)}")
    target_row = target_rows[0]
    model, tokenizer = _load_runtime()
    option_variants = [
        "raw_value",
        "basename",
        "stem",
        "verifier_target_templated",
        "verifier_target_basename_templated",
        "verifier_target_stem_templated",
    ]
    results = {
        variant: _score_row(model, tokenizer, target_row, option_variant=variant)
        for variant in option_variants
    }
    out_path = OUT_DIR / "python_verifier_option_audit.json"
    out_path.write_text(
        json.dumps(
            {
                "stage_name": NAME,
                "runtime_bundle": str(RUNTIME_BUNDLE),
                "target_row_id": TARGET_ROW_ID,
                "results": results,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(str(out_path))


if __name__ == "__main__":
    main()
