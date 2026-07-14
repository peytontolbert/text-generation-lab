#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer, build_batch
from legacy_src.agentkernel_lite.training_loop import (
    _bounded_choice_option_logits,
    _bounded_choice_target_label,
    _load_runtime_model_bundle,
    _move_manifest_batch,
    _target_text,
    _write_bounded_choice_eval_audit,
)


ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11172
NAME = "stage11172_scorer_objective_mismatch_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "scorer_objective_mismatch_audit.json"
ROW_CARDS_JSONL = OUT_DIR / "scorer_objective_row_cards.jsonl"

RUNTIME_BUNDLE = ARTIFACTS / "stage11170_external_fail_to_pass_support_probe" / "runtime_model" / "runtime_model_bundle.json"
CLEAN_STRICT_ROWS = ARTIFACTS / "stage11146_singleton_strict_quarantine_successor" / "agentkernel_lite_encdec_strict_eval.jsonl"
CLEAN_VALIDATION_ROWS = ARTIFACTS / "stage11146_singleton_strict_quarantine_successor" / "agentkernel_lite_encdec_validation.jsonl"
RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "reserved_residual_candidates.jsonl"
LATEST_POSTRUN = ARTIFACTS / "stage11171_external_fail_to_pass_support_postrun_audit" / "external_fail_to_pass_support_postrun_audit.json"

MAX_ENCODER_TOKENS = int(os.environ.get("AGENTKERNEL_MAX_ENCODER_TOKENS", "768"))
MAX_DECODER_TOKENS = int(os.environ.get("AGENTKERNEL_MAX_DECODER_TOKENS", "8"))
EVAL_BATCH_SIZE = int(os.environ.get("AGENTKERNEL_EVAL_BATCH_SIZE", "8"))
TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
EVAL_DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))

SCORER_SOURCES = [
    "encoder_option_retrieval",
    "decoder_first_step",
    "encoder_option_retrieval_conditioned",
    "encoder_option_retrieval_verifier_conditioned",
    "encoder_option_retrieval_evidence_role_map",
    "encoder_option_retrieval_dynamic_productized",
    "encoder_option_retrieval_evidence_conditioned_gated",
    "encoder_pooled",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any]]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = dict(bundle.get("metadata") or {})
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    model.to(EVAL_DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def option_value_for_label(row: dict[str, Any], label: str | None) -> str | None:
    if not label:
        return None
    options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    for option in options:
        if isinstance(option, dict) and str(option.get("label") or "") == str(label):
            return str(option.get("value") or "")
    return None


def option_labels(row: dict[str, Any]) -> list[str]:
    options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    return [str(option.get("label") or "") for option in options if isinstance(option, dict) and option.get("label")]


def metric(cards: list[dict[str, Any]], field: str = "match") -> dict[str, Any]:
    scored = [card for card in cards if isinstance(card.get(field), bool)]
    correct = sum(1 for card in scored if card.get(field) is True)
    return {
        "rows": len(cards),
        "scored_rows": len(scored),
        "correct": correct,
        "accuracy": (correct / len(scored)) if scored else None,
    }


def grouped(cards: list[dict[str, Any]], key: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for card in cards:
        buckets[str(card.get(key) or "unknown")].append(card)
    return {name: metric(rows) for name, rows in sorted(buckets.items())}


def row_task(row: dict[str, Any]) -> str:
    return str(row.get("task_type") or row.get("perspective") or row.get("task_family") or "unknown")


def score_rows_detailed(
    *,
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    rows: list[dict[str, Any]],
    split_name: str,
    source: str,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    model_device = next(model.parameters()).device
    pad_id = int(getattr(tokenizer, "pad_id", 0))
    bos_id = int(getattr(tokenizer, "bos_id", 1))
    eos_id = int(getattr(tokenizer, "eos_id", 2))
    for start in range(0, len(rows), EVAL_BATCH_SIZE):
        row_batch = rows[start : start + EVAL_BATCH_SIZE]
        batch = build_batch(
            row_batch,
            max_encoder_tokens=MAX_ENCODER_TOKENS,
            max_decoder_tokens=MAX_DECODER_TOKENS,
            tokenizer=tokenizer,
        )
        batch = _move_manifest_batch(batch, model_device)
        with torch.no_grad():
            out = model(batch.input_ids, batch.decoder_input_ids)
            first_step_logits = out["decoder_logits"][:, 0, :].detach()
            pooled = out.get("pooled")
        for row_idx, row in enumerate(row_batch):
            row_id = str(row.get("row_id") or f"{split_name}:{start + row_idx}")
            logits = first_step_logits[row_idx].float().cpu()
            target_text = _target_text(row).strip()
            target_label = _bounded_choice_target_label(row).strip()
            target_ids = [idx for idx in tokenizer.encode(target_text, max_length=MAX_DECODER_TOKENS) if idx not in {pad_id, bos_id, eos_id}]
            target_token_id = int(target_ids[0]) if target_ids else None
            full_top1_id = int(torch.argmax(logits).item())
            full_top1_text = tokenizer.decode([full_top1_id]).strip()
            full_match = bool(target_token_id is not None and full_top1_id == target_token_id)
            full_rank = int((logits > logits[target_token_id]).sum().item()) + 1 if target_token_id is not None else None
            option_logits, option_pairs, skip_reason = _bounded_choice_option_logits(
                row=row,
                tokenizer=tokenizer,
                source=source,
                first_step_logits_row=first_step_logits[row_idx],
                pooled_row=(pooled[row_idx] if isinstance(pooled, torch.Tensor) else None),
                model=model,
                untied_head=getattr(model, "bounded_choice_probe_head", None),
            )
            predicted_label = None
            match = None
            target_rank = None
            target_margin_vs_top = None
            option_rankings: list[dict[str, Any]] = []
            if option_logits is not None and option_pairs and target_label:
                option_logits_cpu = option_logits.detach().float().cpu()
                order = torch.argsort(option_logits_cpu, descending=True).tolist()
                best_idx = int(order[0])
                predicted_label = str(option_pairs[best_idx][0])
                match = bool(predicted_label == target_label)
                label_to_index = {str(label): idx for idx, (label, _token_id) in enumerate(option_pairs)}
                if target_label in label_to_index:
                    target_idx = int(label_to_index[target_label])
                    target_rank = int((option_logits_cpu > option_logits_cpu[target_idx]).sum().item()) + 1
                    target_margin_vs_top = float(option_logits_cpu[target_idx].item() - option_logits_cpu[best_idx].item())
                for rank, opt_idx in enumerate(order, start=1):
                    label = str(option_pairs[opt_idx][0])
                    option_rankings.append(
                        {
                            "rank": rank,
                            "label": label,
                            "value": option_value_for_label(row, label),
                            "score": float(option_logits_cpu[opt_idx].item()),
                        }
                    )
            cards.append(
                {
                    "split": split_name,
                    "source": source,
                    "row_id": row_id,
                    "language_family": str(row.get("language_family") or "unknown"),
                    "repo_family": str(row.get("repo_family") or "unknown"),
                    "task_type": row_task(row),
                    "target_label": target_label,
                    "target_value": option_value_for_label(row, target_label),
                    "predicted_label": predicted_label,
                    "predicted_value": option_value_for_label(row, predicted_label),
                    "match": match,
                    "skip_reason": skip_reason,
                    "option_labels": option_labels(row),
                    "option_count": len(option_labels(row)),
                    "target_rank_option": target_rank,
                    "target_margin_vs_top": target_margin_vs_top,
                    "full_vocab_top1_text": full_top1_text,
                    "full_vocab_match": full_match,
                    "target_rank_full_vocab": full_rank,
                    "option_rankings": option_rankings,
                }
            )
    return cards


def scorer_summary(cards: list[dict[str, Any]]) -> dict[str, Any]:
    misses = [card for card in cards if card.get("match") is False]
    return {
        **metric(cards),
        "by_language": grouped(cards, "language_family"),
        "by_task_type": grouped(cards, "task_type"),
        "miss_row_ids": [card["row_id"] for card in misses],
        "miss_target_values": dict(sorted(Counter(str(card.get("target_value") or "unknown") for card in misses).items())),
    }


def best_safe_policies(results: dict[str, dict[str, dict[str, Any]]], base_source: str = "encoder_option_retrieval") -> list[dict[str, Any]]:
    base_strict = results[base_source]["clean_strict"]["correct"]
    base_validation = results[base_source]["clean_validation"]["correct"]
    base_reserved = results[base_source]["reserved_residual"]["correct"]
    candidates: list[dict[str, Any]] = []
    for source, split_results in sorted(results.items()):
        strict = split_results["clean_strict"]["correct"]
        validation = split_results["clean_validation"]["correct"]
        reserved = split_results["reserved_residual"]["correct"]
        candidates.append(
            {
                "source": source,
                "strict_correct": strict,
                "validation_correct": validation,
                "reserved_correct": reserved,
                "strict_delta": strict - base_strict,
                "validation_delta": validation - base_validation,
                "reserved_delta": reserved - base_reserved,
                "safe_vs_base": strict >= base_strict and validation >= base_validation,
                "improves_reserved_without_clean_regression": strict >= base_strict and validation >= base_validation and reserved > base_reserved,
            }
        )
    return candidates


def main() -> None:
    model, tokenizer, init_card = load_runtime()
    clean_strict = load_jsonl(CLEAN_STRICT_ROWS)
    clean_validation = load_jsonl(CLEAN_VALIDATION_ROWS)
    reserved = load_jsonl(RESERVED_ROWS)
    splits = {
        "clean_strict": clean_strict,
        "clean_validation": clean_validation,
        "reserved_residual": reserved,
    }

    all_cards: list[dict[str, Any]] = []
    results: dict[str, dict[str, dict[str, Any]]] = {}
    for source in SCORER_SOURCES:
        results[source] = {}
        for split_name, rows in splits.items():
            audit_card = _write_bounded_choice_eval_audit(
                OUT_DIR,
                model=model,
                rows=rows,
                tokenizer=tokenizer,
                max_encoder_tokens=MAX_ENCODER_TOKENS,
                max_decoder_tokens=MAX_DECODER_TOKENS,
                split_name=f"{split_name}_{source}",
                bounded_choice_aux_source=source,
                eval_batch_size=EVAL_BATCH_SIZE,
            )
            detailed_cards = score_rows_detailed(
                model=model,
                tokenizer=tokenizer,
                rows=rows,
                split_name=split_name,
                source=source,
            )
            all_cards.extend(detailed_cards)
            results[source][split_name] = {
                "audit_accuracy": audit_card.get("constrained_choice_top1_accuracy"),
                "audit_rows": audit_card.get("constrained_choice_rows"),
                **scorer_summary(detailed_cards),
            }

    policy_candidates = best_safe_policies(results)
    safe_reserved_improvers = [policy for policy in policy_candidates if policy["improves_reserved_without_clean_regression"]]
    strict_singletons = [
        str(row.get("row_id") or "")
        for row in clean_strict
        if len(option_labels(row)) <= 1
    ]
    base_misses = [
        card
        for card in all_cards
        if card["source"] == "encoder_option_retrieval" and card.get("match") is False
    ]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "scorer_objective_mismatch_audited",
        "claim_scope": [
            "Audit latest runtime scorer behavior only; this is not a new training run and not a promotion claim.",
            "Compare base retrieval, decoder-label scoring, conditioned option text, evidence role-map text, dynamic productized text, evidence-conditioned gating, and encoder-pooled label scoring on the same rows.",
            "Record per-row option rankings and target margins to identify whether the plateau is caused by support data, scorer policy, or objective mismatch.",
        ],
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "clean_strict_rows": rel(CLEAN_STRICT_ROWS),
            "clean_validation_rows": rel(CLEAN_VALIDATION_ROWS),
            "reserved_rows": rel(RESERVED_ROWS),
            "latest_postrun": rel(LATEST_POSTRUN),
        },
        "runtime_init": init_card,
        "eval_config": {
            "device": str(EVAL_DEVICE),
            "torch_threads": TORCH_THREADS,
            "max_encoder_tokens": MAX_ENCODER_TOKENS,
            "max_decoder_tokens": MAX_DECODER_TOKENS,
            "eval_batch_size": EVAL_BATCH_SIZE,
            "scorer_sources": SCORER_SOURCES,
        },
        "split_counts": {name: len(rows) for name, rows in splits.items()},
        "strict_singleton_option_rows": strict_singletons,
        "results": results,
        "policy_candidates_vs_base": policy_candidates,
        "safe_reserved_improvers": safe_reserved_improvers,
        "base_miss_diagnosis": [
            {
                "split": card["split"],
                "row_id": card["row_id"],
                "language_family": card["language_family"],
                "repo_family": card["repo_family"],
                "task_type": card["task_type"],
                "target_label": card["target_label"],
                "target_value": card["target_value"],
                "predicted_label": card["predicted_label"],
                "predicted_value": card["predicted_value"],
                "target_rank_option": card["target_rank_option"],
                "target_margin_vs_top": card["target_margin_vs_top"],
                "full_vocab_top1_text": card["full_vocab_top1_text"],
                "target_rank_full_vocab": card["target_rank_full_vocab"],
                "top_options": card["option_rankings"][:3],
            }
            for card in base_misses
        ],
        "findings": [
            "A safe scorer replacement requires no clean strict or validation regression and a reserved-residual gain.",
            "If no safe_reserved_improvers are found, more inference-side routing is not justified from this runtime.",
            "Rows where full-vocab label rank is good but option-rank is poor are objective/interface mismatch cases; rows where both are poor need better root materialization or a different semantic target.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "row_cards_jsonl": rel(ROW_CARDS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    write_jsonl(ROW_CARDS_JSONL, all_cards)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
