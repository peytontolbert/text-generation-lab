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


STAGE = 10911
NAME = "stage10911_current_evidence_role_policy_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_JSON = OUT_DIR / "current_evidence_role_policy_audit.json"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10906_python_verifier_transition_probe/runtime_model/runtime_model_bundle.json"
ROWS_JSONL = ROOT / "runs/local/artifacts/stage10881_evidence_alias_quarantine_successor/agentkernel_lite_encdec_validation.jsonl"

EVIDENCE_ROLE_MAP = {
    "algorithmic_background_reference": "background algorithm reference",
    "candidate_change_surface": "current proposed edit surface",
    "external_analogue_reference": "external analogue reference",
    "nearby_definition_or_usage_context": "nearby definition or usage context",
    "symptom_or_call_path_analogue": "symptom or call path analogue",
    "verifier_and_test_constraint": "failing verifier or test constraint",
}

POLICIES = [
    "encoder_raw",
    "encoder_evidence_role_map",
    "decoder_label",
    "hybrid_decoder_on_evidence",
]


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
    opts = ((row.get("standalone_projection_source") or {}).get("opaque_options")) or row.get("opaque_options") or []
    return [(str(opt["label"]), str(opt["value"])) for opt in opts if isinstance(opt, dict)]


def encode_option_texts(
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    texts: list[str],
    device: torch.device,
) -> torch.Tensor:
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


def evidence_option_text(value: str, policy: str) -> str:
    if policy == "encoder_raw":
        return value
    if policy == "encoder_evidence_role_map":
        return f"Visible fact role under review: {EVIDENCE_ROLE_MAP.get(value, value)}"
    raise ValueError(policy)


def encoder_choice(
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    row: dict[str, Any],
    *,
    evidence_variant: str,
) -> tuple[str, list[dict[str, Any]]]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    query = out["pooled"][0:1]
    if getattr(model, "retrieval_query_head", None) is not None:
        query = model.retrieval_query_head(query)
    pairs = option_pairs(row)
    texts = [evidence_option_text(value, evidence_variant) for _, value in pairs]
    option_vectors = encode_option_texts(model, tokenizer, texts, query.device)
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
        for idx, (label, value) in enumerate(pairs)
    ]
    scored.sort(key=lambda item: item["logit"], reverse=True)
    return str(scored[0]["label"]), scored


def single_token_id(tokenizer: AgentKernelBPETokenizer, text: str) -> int | None:
    ids = [idx for idx in tokenizer.encode(text, max_length=8) if idx not in {int(getattr(tokenizer, "bos_id", 1)), int(getattr(tokenizer, "eos_id", 2))}]
    if len(ids) != 1:
        return None
    return int(ids[0])


def decoder_label_choice(
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    row: dict[str, Any],
) -> tuple[str | None, str | None, list[dict[str, Any]]]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    logits = out["decoder_logits"][0, 0]
    top_token_id = int(torch.argmax(logits).item())
    top_text = tokenizer.decode([top_token_id]).strip()
    option_scores = []
    best_label = None
    best_logit = None
    for label, value in option_pairs(row):
        tok_id = single_token_id(tokenizer, label)
        if tok_id is None:
            continue
        score = float(logits[tok_id].item())
        option_scores.append({"label": label, "value": value, "token_id": tok_id, "logit": score})
        if best_logit is None or score > best_logit:
            best_logit = score
            best_label = label
    option_scores.sort(key=lambda item: item["logit"], reverse=True)
    return best_label, top_text, option_scores


def policy_prediction(
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    row: dict[str, Any],
    policy: str,
) -> dict[str, Any]:
    raw_pred, raw_scores = encoder_choice(model, tokenizer, row, evidence_variant="encoder_raw")
    role_pred, role_scores = encoder_choice(model, tokenizer, row, evidence_variant="encoder_evidence_role_map")
    decoder_pred, decoder_top_text, decoder_scores = decoder_label_choice(model, tokenizer, row)

    if policy == "encoder_raw":
        pred = raw_pred
    elif policy == "encoder_evidence_role_map":
        pred = role_pred
    elif policy == "decoder_label":
        pred = decoder_pred
    elif policy == "hybrid_decoder_on_evidence":
        pred = decoder_top_text if decoder_top_text in {label for label, _ in option_pairs(row)} else raw_pred
    else:
        raise ValueError(policy)

    return {
        "row_id": str(row["row_id"]),
        "task_type": str(row.get("task_type") or ""),
        "language_family": str(row.get("language_family") or "unknown"),
        "target": str(row["target_text"]),
        "pred": pred,
        "correct": pred == str(row["target_text"]),
        "raw_pred": raw_pred,
        "role_pred": role_pred,
        "decoder_pred": decoder_pred,
        "decoder_top_text": decoder_top_text,
        "raw_top3": raw_scores[:3],
        "role_top3": role_scores[:3],
        "decoder_top3": decoder_scores[:3],
    }


def summarize(cards: list[dict[str, Any]]) -> dict[str, Any]:
    rows = len(cards)
    correct = sum(1 for card in cards if card["correct"])
    by_language: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        by_language.setdefault(card["language_family"], []).append(card)
    return {
        "rows": rows,
        "correct": correct,
        "accuracy": (correct / rows) if rows else None,
        "by_language": {
            key: {
                "rows": len(items),
                "correct": sum(1 for item in items if item["correct"]),
                "accuracy": sum(1 for item in items if item["correct"]) / len(items),
            }
            for key, items in sorted(by_language.items())
        },
        "misses": [card for card in cards if not card["correct"]],
    }


def main() -> None:
    model, tokenizer = load_runtime()
    rows = [row for row in load_jsonl(ROWS_JSONL) if str(row.get("task_type") or "") == "evidence_citation"]
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "runtime_bundle": str(RUNTIME_BUNDLE),
        "claim_scope": [
            "Compare raw retrieval, evidence-role mapped retrieval, decoder-label, and hybrid decoder-on-evidence scoring on the current cleaned reviewed-v2.7 evidence-citation validation slice.",
            "Determine whether an honest evidence-citation interface candidate exists on the checked surface before building more roots.",
        ],
        "policies": {},
    }
    for policy in POLICIES:
        cards = [policy_prediction(model, tokenizer, row, policy) for row in rows]
        payload["policies"][policy] = summarize(cards)
    payload["next_best_step"] = "If one evidence policy improves the checked surface without introducing a web regression, promote it as a candidate interface; otherwise prioritize fresh source-backed evidence roots."
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
