#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
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


STAGE = 10908
NAME = "stage10908_verifier_transition_policy_audit"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
OUT_JSON = OUT_DIR / "verifier_transition_policy_audit.json"

RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10906_python_verifier_transition_probe/runtime_model/runtime_model_bundle.json"
VALIDATION_ROWS = ROOT / "runs/local/artifacts/stage10881_evidence_alias_quarantine_successor/agentkernel_lite_encdec_validation.jsonl"
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


def decoder_pred(
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    row: dict[str, Any],
) -> str | None:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    logits = out["decoder_logits"][0, 0]
    scored: list[tuple[str, float]] = []
    for label, _ in option_pairs(row):
        token_id = single_token_id(tokenizer, label)
        if token_id is None:
            continue
        scored.append((label, float(logits[token_id].item())))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[0][0] if scored else None


def retrieval_pred(
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    row: dict[str, Any],
) -> str | None:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    pooled = out["pooled"][0:1]
    if getattr(model, "retrieval_query_head", None) is not None:
        pooled = model.retrieval_query_head(pooled)
    pairs = option_pairs(row)
    option_vectors = encode_option_texts(model, tokenizer, [value for _, value in pairs], pooled.device)
    if getattr(model, "retrieval_doc_head", None) is not None:
        option_vectors = model.retrieval_doc_head(option_vectors)
    query = F.normalize(pooled.float(), dim=-1)
    option_vectors = F.normalize(option_vectors.float(), dim=-1)
    logits = torch.matmul(query, option_vectors.transpose(0, 1)).squeeze(0)
    scored = [(label, float(logits[idx].item())) for idx, (label, _) in enumerate(pairs)]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[0][0] if scored else None


def policy_pred(task_type: str, decoder: str | None, retrieval: str | None, policy: str) -> str | None:
    if policy == "current_retrieval":
        return retrieval
    if policy == "decoder_on_all_verifier":
        if task_type in {"verifier_outcome", "verifier_outcome_semantic_transition"}:
            return decoder
        return retrieval
    if policy == "decoder_on_transition_only":
        if task_type == "verifier_outcome_semantic_transition":
            return decoder
        return retrieval
    raise ValueError(policy)


def summarize(cards: list[dict[str, Any]]) -> dict[str, Any]:
    rows = len(cards)
    correct = sum(1 for card in cards if card["correct"])
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for card in cards:
        by_task[str(card["task_type"])].append(card)
    return {
        "rows": rows,
        "correct": correct,
        "accuracy": (correct / rows) if rows else None,
        "by_task": {
            task: {
                "rows": len(items),
                "correct": sum(1 for item in items if item["correct"]),
                "accuracy": sum(1 for item in items if item["correct"]) / len(items),
            }
            for task, items in sorted(by_task.items())
        },
        "misses": [card for card in cards if not card["correct"]],
    }


def evaluate_split(
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    rows: list[dict[str, Any]],
    *,
    policy: str,
    split_name: str,
) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    for row in rows:
        task_type = str(row.get("task_type") or "")
        decoder = decoder_pred(model, tokenizer, row)
        retrieval = retrieval_pred(model, tokenizer, row)
        pred = policy_pred(task_type, decoder, retrieval, policy)
        cards.append(
            {
                "split": split_name,
                "row_id": str(row.get("row_id")),
                "task_type": task_type,
                "target": str(row.get("target_text")),
                "decoder_pred": decoder,
                "retrieval_pred": retrieval,
                "pred": pred,
                "correct": pred == str(row.get("target_text")),
            }
        )
    return summarize(cards)


def main() -> None:
    model, tokenizer = load_runtime()
    validation_rows = load_jsonl(VALIDATION_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)
    policies = ["current_retrieval", "decoder_on_all_verifier", "decoder_on_transition_only"]
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "runtime_bundle": str(RUNTIME_BUNDLE.relative_to(ROOT)),
        "claim_scope": [
            "Audit whether a task-specific policy mix can recover the fresh Python verifier-transition slice without regressing the cleaned 23-row canary.",
            "Keep retrieval as the baseline and compare it against decoder-first-step fallback on verifier tasks.",
        ],
        "policies": {},
    }
    for policy in policies:
        payload["policies"][policy] = {
            "eval": evaluate_split(model, tokenizer, validation_rows, policy=policy, split_name="eval"),
            "strict_eval": evaluate_split(model, tokenizer, strict_rows, policy=policy, split_name="strict_eval"),
        }
    payload["next_best_step"] = "If decoder-only on verifier-transition rows recovers 2/2 strict without hurting the 23-row canary, promote that as an interface candidate and compare it against Gemma under the same policy boundary."
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
