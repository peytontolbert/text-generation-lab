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

from legacy_src.agentkernel_lite.modeling_transformer import (  # noqa: E402
    AgentKernelLiteTransformerConfig,
    AgentKernelLiteTransformerSeq2Seq,
)
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer, build_batch  # noqa: E402
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle  # noqa: E402


STAGE = 10907
NAME = "stage10907_python_verifier_transition_scorer_audit"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
OUT_JSON = OUT_DIR / "python_verifier_transition_scorer_audit.json"

RUNTIMES = {
    "stage10890": ROOT / "runs/local/artifacts/stage10890_flash_attn_alias_safe_multilingual_support_probe/runtime_model/runtime_model_bundle.json",
    "stage10906": ROOT / "runs/local/artifacts/stage10906_python_verifier_transition_probe/runtime_model/runtime_model_bundle.json",
}
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10902_python_verifier_transition_candidate_slice/strict_candidate_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_runtime(runtime_bundle: Path) -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer]:
    bundle = load_json(runtime_bundle)
    metadata = bundle["metadata"]
    model_config = load_json(Path(str(metadata["model_config"])))
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(model_config)
    model = AgentKernelLiteTransformerSeq2Seq(config)
    _load_runtime_model_bundle(runtime_bundle, model=model)
    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    model.eval()
    return model, tokenizer


def option_pairs(row: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        (str(opt.get("label") or ""), str(opt.get("value") or ""))
        for opt in ((row.get("standalone_projection_source") or {}).get("opaque_options") or row.get("opaque_options") or [])
        if isinstance(opt, dict)
    ]


def single_token_id(tokenizer: AgentKernelBPETokenizer, text: str) -> int | None:
    pad_id = int(getattr(tokenizer, "pad_id", 0))
    bos_id = int(getattr(tokenizer, "bos_id", 1))
    eos_id = int(getattr(tokenizer, "eos_id", 2))
    token_ids = [idx for idx in tokenizer.encode(text, max_length=8) if idx not in {pad_id, bos_id, eos_id}]
    if len(token_ids) != 1:
        return None
    return int(token_ids[0])


def encode_option_texts(
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
        encoded_rows.append(token_ids or [pad_id])
    width = max(len(ids) for ids in encoded_rows)
    input_ids = torch.full((len(encoded_rows), width), pad_id, dtype=torch.long, device=device)
    attention_mask = torch.zeros((len(encoded_rows), width), dtype=torch.bool, device=device)
    for row_idx, token_ids in enumerate(encoded_rows):
        input_ids[row_idx, : len(token_ids)] = torch.tensor(token_ids, dtype=torch.long, device=device)
        attention_mask[row_idx, : len(token_ids)] = True
    return model.encode_pooled(input_ids, attention_mask)


def conditioned_text(prompt_text: str, option_value: str) -> str:
    marker = "\nOptions:\n"
    prompt = prompt_text.split(marker, 1)[0].rstrip() if marker in prompt_text else prompt_text.strip()
    return f"{prompt}\nCandidate under review: {option_value}" if prompt else f"Candidate under review: {option_value}"


def score_row(
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    row: dict[str, Any],
    *,
    source: str,
) -> dict[str, Any]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    pairs = option_pairs(row)
    if source == "decoder_first_step":
        logits = out["decoder_logits"][0, 0]
        scores: list[dict[str, Any]] = []
        for label, value in pairs:
            token_id = single_token_id(tokenizer, label)
            if token_id is None:
                continue
            scores.append(
                {
                    "label": label,
                    "value": value,
                    "score": float(logits[token_id].item()),
                    "token_id": token_id,
                }
            )
        scores.sort(key=lambda item: item["score"], reverse=True)
        return {"source": source, "scores": scores, "pred": (scores[0]["label"] if scores else None)}

    pooled = out["pooled"][0:1]
    if getattr(model, "retrieval_query_head", None) is not None:
        pooled = model.retrieval_query_head(pooled)
    prompt_text = str(row.get("prompt_text") or row.get("input_text") or "")
    if source == "encoder_option_retrieval":
        option_texts = [value for _, value in pairs]
    elif source == "encoder_option_retrieval_conditioned":
        option_texts = [conditioned_text(prompt_text, value) for _, value in pairs]
    else:
        raise ValueError(f"unsupported source: {source}")
    option_vectors = encode_option_texts(model, tokenizer, option_texts, pooled.device)
    if getattr(model, "retrieval_doc_head", None) is not None:
        option_vectors = model.retrieval_doc_head(option_vectors)
    query = F.normalize(pooled.float(), dim=-1)
    option_vectors = F.normalize(option_vectors.float(), dim=-1)
    logits = torch.matmul(query, option_vectors.transpose(0, 1)).squeeze(0)
    scores = [
        {
            "label": label,
            "value": value,
            "score": float(logits[idx].item()),
            "text": option_texts[idx],
        }
        for idx, (label, value) in enumerate(pairs)
    ]
    scores.sort(key=lambda item: item["score"], reverse=True)
    return {"source": source, "scores": scores, "pred": (scores[0]["label"] if scores else None)}


def main() -> None:
    rows = load_jsonl(STRICT_ROWS)
    payload: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "claim_scope": [
            "Compare decoder-first-step, raw encoder option retrieval, and conditioned encoder option retrieval on the fresh Python verifier-transition strict slice.",
            "Determine whether the remaining miss is scorer-interface-specific or remains wrong across available scoring views.",
        ],
        "strict_row_ids": [str(row.get("row_id")) for row in rows],
        "runtimes": {},
    }
    for runtime_name, runtime_bundle in RUNTIMES.items():
        model, tokenizer = load_runtime(runtime_bundle)
        runtime_cards: list[dict[str, Any]] = []
        for row in rows:
            row_card = {
                "row_id": str(row.get("row_id")),
                "target": str(row.get("target_text")),
                "repo_id": str(row.get("repo_id") or ""),
                "scores": {},
            }
            for source in ("decoder_first_step", "encoder_option_retrieval", "encoder_option_retrieval_conditioned"):
                row_card["scores"][source] = score_row(model, tokenizer, row, source=source)
            runtime_cards.append(row_card)
        payload["runtimes"][runtime_name] = {
            "runtime_bundle": str(runtime_bundle.relative_to(ROOT)),
            "row_cards": runtime_cards,
        }

    payload["findings"] = [
        "If conditioned retrieval recovers the hard stage10894 row while raw retrieval does not, the next move should be a scored-interface audit rather than another generic support probe.",
        "If all retrieval views still miss while decoder-first-step remains correct, the model contains the right label token but the retrieval heads are not aligning verifier semantics.",
    ]
    payload["next_best_step"] = "Use this audit to decide whether the next experiment should switch the verifier-transition slice to a conditioned scorer path or rebuild the verifier option text interface."
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
