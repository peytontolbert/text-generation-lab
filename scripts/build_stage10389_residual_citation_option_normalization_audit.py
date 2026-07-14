#!/usr/bin/env python3
from __future__ import annotations

import json
import re
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

NAME = "stage10389_residual_citation_option_normalization_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = ROOT / "runs/local/artifacts/stage10378_balanced_residual_probe_execution_request/balanced_residual_probe_manifest.jsonl"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10379_balanced_residual_probe/runtime_model/runtime_model_bundle.json"
TARGET_ROW_IDS = {
    "stage10119::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_56_21_019d3560_1014_7761_9ea7_5638_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_causalmachine_cuda_a018ca0b43_aug_1500000_8b46e7f662::c_cpp::evidence_citation::full_visible_compact_bounded",
    "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_26t00_55_44_019abda8_c0d8_7803_8a77_1e0f_scripts_universe_build_py_64d2cf209b_aug_1500000_8b46e7f662::python::evidence_citation::full_visible_compact_bounded",
}
ROLE_MAP = {
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
        if row.get("row_id") in TARGET_ROW_IDS:
            rows.append(row)
    rows.sort(key=lambda row: str(row["row_id"]))
    if len(rows) != len(TARGET_ROW_IDS):
        raise SystemExit(f"expected {len(TARGET_ROW_IDS)} rows, found {len(rows)}")
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


def _snake_to_words(value: str) -> str:
    return re.sub(r"_+", " ", value).strip()


def _option_text(value: str, variant: str) -> str:
    if variant == "raw_value":
        return value
    if variant == "desnake":
        return _snake_to_words(value)
    if variant == "role_map":
        return ROLE_MAP.get(value, value)
    if variant == "role_map_templated":
        return f"Visible fact role under review: {ROLE_MAP.get(value, value)}"
    raise ValueError(f"unsupported variant: {variant}")


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


def _score_row(model: AgentKernelLiteTransformerSeq2Seq, tokenizer: AgentKernelBPETokenizer, row: dict[str, object], variant: str) -> dict[str, object]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    query = out["pooled"][0:1]
    if getattr(model, "retrieval_query_head", None) is not None:
        query = model.retrieval_query_head(query)
    option_pairs = _option_pairs(row)
    texts = [_option_text(value, variant) for _, value in option_pairs]
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
    return {
        "row_id": row["row_id"],
        "target": row["decoder_text"],
        "pred": scored[0]["label"],
        "correct": scored[0]["label"] == row["decoder_text"],
        "top3": scored[:3],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _load_rows()
    model, tokenizer = _load_runtime()
    variants = ["raw_value", "desnake", "role_map", "role_map_templated"]
    results = {}
    for variant in variants:
        results[variant] = [_score_row(model, tokenizer, row, variant) for row in rows]
    out_path = OUT_DIR / "residual_citation_option_normalization_audit.json"
    out_path.write_text(
        json.dumps(
            {
                "stage_name": NAME,
                "runtime_bundle": str(RUNTIME_BUNDLE),
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
