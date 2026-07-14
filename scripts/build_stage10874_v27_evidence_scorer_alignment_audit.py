#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
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


STAGE = 10874
NAME = "stage10874_v27_evidence_scorer_alignment_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_JSON = OUT_DIR / "v27_evidence_scorer_alignment_audit.json"

SPLITS = {
    "eval": ROOT / "runs/local/artifacts/stage10864_residual_family_support_package_plus_second_python_materialized/agentkernel_lite_encdec_validation.jsonl",
    "strict_eval": ROOT / "runs/local/artifacts/stage10864_residual_family_support_package_plus_second_python_materialized/agentkernel_lite_encdec_strict_eval.jsonl",
}

RUNTIMES = {
    "stage10870": ROOT / "runs/local/artifacts/stage10870_residual_family_probe_plus_second_python_materialized/runtime_model/runtime_model_bundle.json",
    "stage10873": ROOT / "runs/local/artifacts/stage10873_verifier_candidate_semantic_probe/runtime_model/runtime_model_bundle.json",
}

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


def perspective(row: dict[str, Any]) -> str:
    return str(row.get("task_type") or "")


def option_pairs(row: dict[str, Any]) -> list[tuple[str, str]]:
    return [(str(opt["label"]), str(opt["value"])) for opt in (row.get("opaque_options") or [])]


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
    raise ValueError(f"unsupported evidence policy text: {policy}")


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
    if perspective(row) == "evidence_citation":
        texts = [evidence_option_text(value, evidence_variant) for _, value in pairs]
    else:
        texts = [value for _, value in pairs]
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
        pred = role_pred if perspective(row) == "evidence_citation" else raw_pred
    elif policy == "decoder_label":
        pred = decoder_pred
    elif policy == "hybrid_decoder_on_evidence":
        if perspective(row) == "evidence_citation" and decoder_top_text in {label for label, _ in option_pairs(row)}:
            pred = decoder_top_text
        else:
            pred = raw_pred
    else:
        raise ValueError(f"unsupported policy: {policy}")

    return {
        "row_id": str(row["row_id"]),
        "task_type": perspective(row),
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
    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for card in cards:
        by_language[card["language_family"]].append(card)
        by_task[card["task_type"]].append(card)
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
        "by_task": {
            key: {
                "rows": len(items),
                "correct": sum(1 for item in items if item["correct"]),
                "accuracy": sum(1 for item in items if item["correct"]) / len(items),
            }
            for key, items in sorted(by_task.items())
        },
        "misses": [card for card in cards if not card["correct"]],
    }


def main() -> None:
    split_rows = {split: load_jsonl(path) for split, path in SPLITS.items()}
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "claim_scope": [
            "Audit whether current reviewed v2.7 evidence-row failures are better addressed by scorer alignment than by another train-only support package.",
            "Compare raw encoder retrieval, evidence-role remapping, decoder-label scoring, and an evidence-only decoder fallback policy on the same frozen eval rows.",
        ],
        "runtimes": {},
    }

    for runtime_name, runtime_bundle in RUNTIMES.items():
        model, tokenizer = load_runtime(runtime_bundle)
        runtime_payload = {"runtime_bundle": str(runtime_bundle), "splits": {}}
        for split_name, rows in split_rows.items():
            split_payload = {"policies": {}}
            for policy in POLICIES:
                cards = [policy_prediction(model, tokenizer, row, policy) for row in rows]
                split_payload["policies"][policy] = summarize(cards)
            runtime_payload["splits"][split_name] = split_payload
        payload["runtimes"][runtime_name] = runtime_payload

    findings = []
    for runtime_name, runtime_payload in payload["runtimes"].items():
        strict_policies = runtime_payload["splits"]["strict_eval"]["policies"]
        baseline = strict_policies["encoder_raw"]["accuracy"]
        best_policy, best_summary = max(strict_policies.items(), key=lambda item: item[1]["accuracy"])
        findings.append(
            {
                "runtime": runtime_name,
                "strict_baseline_accuracy": baseline,
                "strict_best_policy": best_policy,
                "strict_best_accuracy": best_summary["accuracy"],
                "strict_best_delta": best_summary["accuracy"] - baseline,
                "strict_tokenizers_evidence_cards": [
                    card
                    for card in best_summary["misses"] + [c for c in []]
                    if "tokenizers::tokenizers::rust::evidence_citation" in card["row_id"]
                ],
            }
        )
    payload["findings"] = findings
    payload["next_best_step"] = (
        "If an evidence-row scorer policy strictly improves the frozen strict set with no extra regressions, productize it as a standalone scoring interface and rerun the same-manifest Gemma comparison under matched reporting."
    )

    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
