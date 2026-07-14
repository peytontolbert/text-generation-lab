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


STAGE = 10876
NAME = "stage10876_narrow_evidence_role_map_runtime_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_JSON = OUT_DIR / "narrow_evidence_role_map_runtime_audit.json"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10870_residual_family_probe_plus_second_python_materialized/runtime_model/runtime_model_bundle.json"
SPLITS = {
    "eval": ROOT / "runs/local/artifacts/stage10864_residual_family_support_package_plus_second_python_materialized/agentkernel_lite_encdec_validation.jsonl",
    "strict_eval": ROOT / "runs/local/artifacts/stage10864_residual_family_support_package_plus_second_python_materialized/agentkernel_lite_encdec_strict_eval.jsonl",
}
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
    return [(str(opt["label"]), str(opt["value"])) for opt in (row.get("opaque_options") or [])]


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


def score_row(
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    row: dict[str, Any],
    *,
    role_map: bool,
) -> dict[str, Any]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    query = out["pooled"][0:1]
    if getattr(model, "retrieval_query_head", None) is not None:
        query = model.retrieval_query_head(query)
    pairs = option_pairs(row)
    texts = []
    for _, value in pairs:
        if role_map:
            texts.append(f"Visible fact role under review: {EVIDENCE_ROLE_MAP.get(value, value)}")
        else:
            texts.append(value)
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
    pred = str(scored[0]["label"])
    target = str(row["target_text"])
    return {
        "row_id": str(row["row_id"]),
        "language_family": str(row.get("language_family") or "unknown"),
        "target": target,
        "pred": pred,
        "correct": pred == target,
        "top3": scored[:3],
    }


def summarize(cards: list[dict[str, Any]]) -> dict[str, Any]:
    rows = len(cards)
    correct = sum(1 for card in cards if card["correct"])
    return {
        "rows": rows,
        "correct": correct,
        "accuracy": (correct / rows) if rows else None,
        "misses": [card for card in cards if not card["correct"]],
    }


def main() -> None:
    model, tokenizer = load_runtime()
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "runtime_bundle": str(RUNTIME_BUNDLE),
        "claim_scope": [
            "Compare raw evidence-value retrieval against a role-mapped evidence-value scorer on evidence_citation rows only.",
            "Use the current stronger stage10870 runtime and the frozen v2.7 eval rows.",
        ],
        "splits": {},
    }
    for split_name, path in SPLITS.items():
        rows = [row for row in load_jsonl(path) if row.get("task_type") == "evidence_citation"]
        raw_cards = [score_row(model, tokenizer, row, role_map=False) for row in rows]
        mapped_cards = [score_row(model, tokenizer, row, role_map=True) for row in rows]
        payload["splits"][split_name] = {
            "raw": summarize(raw_cards),
            "role_mapped": summarize(mapped_cards),
        }
    payload["next_best_step"] = (
        "If role-mapped evidence scoring improves strict evidence rows without collateral loss, isolate it as a standalone scored-interface candidate for the reviewed v2.7 frontier."
    )
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
