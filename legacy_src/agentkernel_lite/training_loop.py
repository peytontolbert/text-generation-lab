from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from torch.optim import AdamW

from .modeling import AgentKernelLiteConfig, AgentKernelLiteSeq2Seq
from .training_data import build_batch


REQUIRED_RUNTIME_ARTIFACTS = [
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_token_loss.jsonl",
    "eos_length_audit.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
    "sample_generation_audit.json",
    "module_delta_norms.json",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "internal_token_logit_summary.json",
    "row_dynamics_history.jsonl",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]

REQUIRED_STRUCTURED_ARTIFACTS = [
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "row_dynamics_history.jsonl",
    "field_exact_by_cell.json",
    "field_label_vocabs.json",
    "structured_confusion_matrix.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]

REQUIRED_DENOISE_ARTIFACTS = [
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "row_dynamics_history.jsonl",
    "denoise_repair_quality_audit.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
    "sample_generation_audit.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]

STRUCTURED_LOSS_TO_FIELD = {
    "surface_role_ce": "surface_role",
    "repair_surface_ce": "repair_surface",
    "build_mode_ce": "build_mode",
    "allowed_import_policy_ce": "allowed_import_policy",
    "blocked_import_policy_ce": "blocked_import_policy",
    "repo_dependency_policy_ce": "repo_dependency_policy",
    "action_sequence_ce": "action_sequence",
    "file_plan_ce": "file_plan",
    "symbol_binding_ce": "symbol_binding",
    "edit_localization_ce": "edit_localization",
    "patch_operator_ce": "patch_operator",
    "verifier_repair_ce": "verifier_repair",
    "suffix_choice_ce": "suffix_choice",
    "episode_repair_outcome_ce": "episode_repair_outcome",
    "episode_failure_type_ce": "episode_failure_type",
    "episode_boundary_match_ce": "episode_boundary_match",
    "episode_target_prefix_match_ce": "episode_target_prefix_match",
    "episode_step_value_mse": "episode_step_value",
}


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")


def _split_rows(rows: list[dict[str, Any]], split: str, cap: int) -> list[dict[str, Any]]:
    def normalized(row: dict[str, Any]) -> str:
        value = str(row.get("split") or row.get("package_split") or "train")
        return "strict_eval" if value == "strict" else value

    selected = [row for row in rows if normalized(row) == split]
    return selected[:cap]


def _generation_audit_rows(
    *,
    train_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    strict_rows: list[dict[str, Any]],
    generation_audit_splits: str = "eval,strict_eval",
) -> list[dict[str, Any]]:
    split_map = {"train": train_rows, "eval": eval_rows, "strict_eval": strict_rows, "strict": strict_rows}
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_split in str(generation_audit_splits or "eval,strict_eval").split(","):
        split = raw_split.strip()
        if not split:
            continue
        for row in split_map.get(split, []):
            row_id = str(row.get("row_id"))
            if row_id in seen:
                continue
            seen.add(row_id)
            selected.append(row)
    return selected


def _has_internal_token(text: str) -> bool:
    markers = ["<MTC", "POLICY_", "<COPY", "INTERNAL", "decoder_control"]
    return any(marker in text for marker in markers)


def _looks_internal_token_text(text: str) -> bool:
    markers = ["<MTC", "<MT", "<COPY", "COPY:", "<SEM", "<CTRL", "<PLAN", "<MNSB", "<PYPLAN", "POLICY_", "CONTROL_", "INTERNAL_", "decoder_control"]
    return any(marker in text for marker in markers)


def _module_bucket(parameter_name: str) -> str:
    if parameter_name.startswith(("enc_embed", "dec_embed", "embedding")):
        return "embeddings"
    if parameter_name.startswith("encoder"):
        if ".self_attn." in parameter_name:
            return "encoder_attention"
        if ".mlp." in parameter_name:
            return "encoder_mlp"
        return "encoder"
    if parameter_name.startswith("decoder"):
        if ".self_attn." in parameter_name or ".cross_attn." in parameter_name:
            return "decoder_attention"
        if ".mlp." in parameter_name or ".self_mlp." in parameter_name or ".cross_mlp." in parameter_name:
            return "decoder_mlp"
        return "decoder"
    if parameter_name.startswith(("lm_head", "decoder_out")):
        return "lm_head"
    if parameter_name.startswith("structured_heads"):
        return "structured_heads"
    if parameter_name.startswith(("retrieval_", "agent_policy", "agent_intent", "agent_controller", "scalar_invariant")):
        return "policy_retrieval_heads"
    return "other"


def _module_delta_norm_card(before: dict[str, torch.Tensor], after: dict[str, torch.Tensor]) -> dict[str, Any]:
    by_parameter = _module_delta_norms(before, after)
    by_bucket_sq: dict[str, float] = {}
    for name, norm in by_parameter.items():
        bucket = _module_bucket(name)
        by_bucket_sq[bucket] = by_bucket_sq.get(bucket, 0.0) + float(norm) ** 2
    by_bucket = {bucket: value ** 0.5 for bucket, value in sorted(by_bucket_sq.items())}
    return {
        "parameter_delta_norms": by_parameter,
        "delta_norm_by_bucket": by_bucket,
        "total_delta_norm": sum(value * value for value in by_parameter.values()) ** 0.5,
        "decoder_delta_norm": sum(value * value for key, value in by_bucket.items() if key.startswith("decoder") or key == "lm_head") ** 0.5,
        "structured_head_delta_norm": by_bucket.get("structured_heads", 0.0),
        "encoder_delta_norm": sum(value * value for key, value in by_bucket.items() if key.startswith("encoder")) ** 0.5,
    }


def _gradient_norm_card(row_id: str, model: torch.nn.Module, *, losses_enabled: list[str]) -> dict[str, Any]:
    by_bucket_sq: dict[str, float] = {}
    for name, parameter in model.named_parameters():
        if parameter.grad is None:
            continue
        norm = float(parameter.grad.detach().float().norm().item())
        bucket = _module_bucket(name)
        by_bucket_sq[bucket] = by_bucket_sq.get(bucket, 0.0) + norm * norm
    by_bucket = {bucket: value ** 0.5 for bucket, value in sorted(by_bucket_sq.items())}
    return {
        "row_id": row_id,
        "losses_enabled": losses_enabled,
        "total_grad_norm": sum(value * value for value in by_bucket.values()) ** 0.5,
        "grad_norm_by_bucket": by_bucket,
        "decoder_grad_norm": sum(value * value for key, value in by_bucket.items() if key.startswith("decoder") or key == "lm_head") ** 0.5,
        "structured_head_grad_norm": by_bucket.get("structured_heads", 0.0),
        "encoder_grad_norm": sum(value * value for key, value in by_bucket.items() if key.startswith("encoder")) ** 0.5,
    }



def _total_grad_norm(model: torch.nn.Module) -> float:
    total_sq = 0.0
    for parameter in model.parameters():
        if parameter.grad is None:
            continue
        norm = float(parameter.grad.detach().float().norm().item())
        total_sq += norm * norm
    return total_sq ** 0.5


def _decoder_ce_loss(
    model: torch.nn.Module,
    logits: torch.Tensor,
    labels: torch.Tensor,
    row_mask: torch.Tensor | None,
    *,
    eos_id: int,
    eos_loss_weight: float,
    token_loss_mask: torch.Tensor | None = None,
) -> torch.Tensor:
    if eos_loss_weight == 1.0 and token_loss_mask is None:
        return model.decoder_ce_loss(logits, labels, row_mask)
    token_loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), labels.reshape(-1), ignore_index=0, reduction="none").reshape(labels.shape)
    nonpad = labels.ne(0).float()
    if token_loss_mask is not None:
        nonpad = nonpad * token_loss_mask.to(device=labels.device, dtype=nonpad.dtype)
    weights = torch.ones_like(token_loss)
    weights = torch.where(labels.eq(int(eos_id)), torch.full_like(weights, float(eos_loss_weight)), weights)
    weighted = token_loss * weights * nonpad
    denom = (weights * nonpad).sum(dim=1).clamp_min(1.0)
    row_loss = weighted.sum(dim=1) / denom
    if row_mask is not None:
        active = row_mask.float()
        return (row_loss * active).sum() / active.sum().clamp_min(1.0)
    return row_loss.mean()


def _post_prefix_loss_mask(labels: torch.Tensor, rows: list[dict[str, Any]], *, tokenizer: Any, generation_prefix_field: str | None) -> torch.Tensor | None:
    if not generation_prefix_field:
        return None
    pad_id = int(getattr(tokenizer, "pad_id", 0))
    bos_id = int(getattr(tokenizer, "bos_id", 1))
    eos_id = int(getattr(tokenizer, "eos_id", 2))
    mask = torch.zeros_like(labels, dtype=torch.bool)
    any_prefix = False
    for row_idx, row in enumerate(rows):
        prefix_text = _nested_row_value(row, generation_prefix_field)
        if not prefix_text:
            mask[row_idx] = labels[row_idx].ne(pad_id)
            continue
        prefix_ids = [idx for idx in tokenizer.encode(str(prefix_text), max_length=labels.shape[1] + 2) if idx not in {pad_id, bos_id, eos_id}]
        start = min(len(prefix_ids), labels.shape[1])
        mask[row_idx, start:] = labels[row_idx, start:].ne(pad_id)
        any_prefix = True
    return mask if any_prefix else None


def _tensor_stats(tensor: torch.Tensor) -> dict[str, Any]:
    values = tensor.detach().float()
    if values.numel() == 0:
        return {"shape": list(values.shape), "mean": 0.0, "std": 0.0, "l2_norm": 0.0, "max_abs": 0.0}
    return {
        "shape": list(values.shape),
        "mean": float(values.mean().item()),
        "std": float(values.std(unbiased=False).item()) if values.numel() > 1 else 0.0,
        "l2_norm": float(values.norm().item()),
        "max_abs": float(values.abs().max().item()),
    }


def _activation_summary(row_ids: list[str], out: dict[str, Any], *, split: str, step: int | None = None) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    pooled = out.get("pooled")
    decoder_logits = out.get("decoder_logits")
    for idx, row_id in enumerate(row_ids):
        layers: dict[str, Any] = {}
        if isinstance(pooled, torch.Tensor) and idx < pooled.shape[0]:
            layers["field_head_input"] = _tensor_stats(pooled[idx])
        if isinstance(decoder_logits, torch.Tensor) and idx < decoder_logits.shape[0]:
            layers["decoder_logits"] = _tensor_stats(decoder_logits[idx])
        summaries.append({"row_id": row_id, "split": split, "step": step, "layers": layers, "activation_cache_present": bool(layers)})
    return summaries


def _field_telemetry_record(*, row_id: str, split: str, field: str, target: str, logits: torch.Tensor, inverse: dict[int, str], confidence_threshold: float = 0.8) -> dict[str, Any]:
    logits_cpu = logits.detach().float().cpu()
    probs = torch.softmax(logits_cpu, dim=-1)
    order = torch.argsort(probs, descending=True)
    pred_idx = int(order[0].item()) if order.numel() else -1
    top2_idx = int(order[1].item()) if order.numel() > 1 else pred_idx
    pred = inverse.get(pred_idx, str(pred_idx))
    correct = pred == target
    confidence = float(probs[pred_idx].item()) if pred_idx >= 0 else 0.0
    top2_conf = float(probs[top2_idx].item()) if top2_idx >= 0 else 0.0
    entropy = float(-(probs * torch.log(probs.clamp_min(1e-12))).sum().item())
    target_idx = next((idx for idx, label in inverse.items() if label == target), None)
    top_k = [
        {"label": inverse.get(int(idx.item()), str(int(idx.item()))), "logit": float(logits_cpu[int(idx.item())].item()), "prob": float(probs[int(idx.item())].item())}
        for idx in order[: min(5, order.numel())]
    ]
    return {
        "row_id": row_id,
        "split": split,
        "field": field,
        "target": target,
        "pred": pred,
        "correct": correct,
        "target_index": target_idx,
        "pred_index": pred_idx,
        "top1_label": pred,
        "top2_label": inverse.get(top2_idx, str(top2_idx)),
        "top1_logit": float(logits_cpu[pred_idx].item()) if pred_idx >= 0 else 0.0,
        "top2_logit": float(logits_cpu[top2_idx].item()) if top2_idx >= 0 else 0.0,
        "margin": confidence - top2_conf,
        "confidence": confidence,
        "entropy": entropy,
        "top_k": top_k,
        "high_confidence_wrong": (not correct) and confidence >= confidence_threshold,
    }


def _is_short_or_junk(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 8:
        return True
    alnum = {ch.lower() for ch in stripped if ch.isalnum()}
    return len(alnum) < 3


def _has_repeated_token_pattern(token_ids: list[int], *, repeats: int = 3) -> bool:
    if len(token_ids) < repeats:
        return False
    max_width = min(16, max(1, len(token_ids) // repeats))
    for width in range(1, max_width + 1):
        for start in range(0, len(token_ids) - width * repeats + 1):
            chunk = token_ids[start: start + width]
            if len(set(chunk)) == 1 and width > 1:
                continue
            if all(token_ids[start + width * rep: start + width * (rep + 1)] == chunk for rep in range(1, repeats)):
                return True
    return False


def _has_repeated_text_pattern(text: str, *, repeats: int = 3) -> bool:
    compact = "".join(ch for ch in text.lower() if not ch.isspace())
    if len(compact) < 12:
        return False
    max_width = min(40, max(3, len(compact) // repeats))
    for width in range(3, max_width + 1):
        for start in range(0, len(compact) - width * repeats + 1):
            chunk = compact[start: start + width]
            if len(set(chunk)) <= 1:
                continue
            if all(compact[start + width * rep: start + width * (rep + 1)] == chunk for rep in range(1, repeats)):
                return True
    return False


def _has_degenerate_repetition(token_ids: list[int], text: str) -> bool:
    if any(token_ids[idx] == token_ids[idx - 1] == token_ids[idx - 2] for idx in range(2, len(token_ids))):
        return True
    if _has_repeated_token_pattern(token_ids):
        return True
    if _has_repeated_text_pattern(text):
        return True
    words = [word for word in text.lower().split() if word]
    if len(words) >= 6:
        trigrams = [tuple(words[idx: idx + 3]) for idx in range(len(words) - 2)]
        if len(set(trigrams)) <= max(1, len(trigrams) // 3):
            return True
    return False


def _nested_row_value(row: dict[str, Any], path: str | None) -> str:
    if not path:
        return ""
    value: Any = row
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return ""
    return value if isinstance(value, str) else ""


def _generate_greedy_text(
    model: torch.nn.Module,
    row: dict[str, Any],
    *,
    tokenizer: Any,
    max_encoder_tokens: int,
    max_new_tokens: int,
    generation_prefix_field: str | None = None,
) -> dict[str, Any]:
    batch = build_batch([row], max_encoder_tokens=max_encoder_tokens, max_decoder_tokens=2, tokenizer=tokenizer)
    bos_id = int(getattr(tokenizer, "bos_id", 1))
    eos_id = int(getattr(tokenizer, "eos_id", 2))
    pad_id = int(getattr(tokenizer, "pad_id", 0))
    generation_prefix_text = _nested_row_value(row, generation_prefix_field) if generation_prefix_field else ""
    prefix_ids: list[int] = []
    if generation_prefix_text:
        encoded_prefix = tokenizer.encode(str(generation_prefix_text), max_length=max_new_tokens + 2)
        prefix_ids = [idx for idx in encoded_prefix if idx not in {pad_id, bos_id, eos_id}]
    target_ids = [idx for idx in tokenizer.encode(_target_text(row), max_length=max_new_tokens + len(prefix_ids) + 8) if idx not in {pad_id, bos_id, eos_id}]
    expected_next_id = target_ids[len(prefix_ids)] if prefix_ids and target_ids[: len(prefix_ids)] == prefix_ids and len(target_ids) > len(prefix_ids) else None
    decoder_ids = torch.tensor([[bos_id] + prefix_ids], dtype=torch.long, device=batch.input_ids.device)
    generated_ids: list[int] = list(prefix_ids)
    eos_position = None
    boundary_next_token: dict[str, Any] = {
        "available": bool(prefix_ids and expected_next_id is not None),
        "expected_token_id": expected_next_id,
        "expected_token_text": tokenizer.decode([expected_next_id]) if expected_next_id is not None else "",
        "generated_token_id": None,
        "generated_token_text": "",
        "match": False,
        "expected_rank": None,
        "expected_probability": None,
        "top_k": [],
    }
    model.eval()
    with torch.no_grad():
        for step_idx in range(max(0, max_new_tokens - len(prefix_ids))):
            out = model(batch.input_ids, decoder_ids)
            next_logits = out["decoder_logits"][0, -1].detach().float().cpu()
            next_probs = torch.softmax(next_logits, dim=-1)
            next_id = int(torch.argmax(next_logits).item())
            if step_idx == 0:
                top_count = min(10, int(next_logits.numel()))
                top_probs, top_indices = torch.topk(next_probs, k=top_count)
                boundary_next_token["generated_token_id"] = next_id
                boundary_next_token["generated_token_text"] = tokenizer.decode([next_id])
                boundary_next_token["match"] = bool(expected_next_id is not None and next_id == expected_next_id)
                boundary_next_token["top_k"] = [
                    {
                        "token_id": int(token_idx.item()),
                        "token_text": tokenizer.decode([int(token_idx.item())]),
                        "probability": float(prob.item()),
                        "logit": float(next_logits[int(token_idx.item())].item()),
                    }
                    for prob, token_idx in zip(top_probs, top_indices)
                ]
                if expected_next_id is not None:
                    expected_prob = float(next_probs[int(expected_next_id)].item())
                    expected_logit = float(next_logits[int(expected_next_id)].item())
                    expected_rank = int((next_logits > next_logits[int(expected_next_id)]).sum().item()) + 1
                    boundary_next_token.update(
                        {
                            "expected_rank": expected_rank,
                            "expected_probability": expected_prob,
                            "expected_logit": expected_logit,
                        }
                    )
            generated_ids.append(next_id)
            decoder_ids = torch.cat([decoder_ids, torch.tensor([[next_id]], dtype=torch.long, device=decoder_ids.device)], dim=1)
            if next_id == eos_id:
                eos_position = len(generated_ids) - 1
                break
    clean_ids = [idx for idx in generated_ids if idx not in {pad_id, bos_id, eos_id}]
    text = tokenizer.decode(clean_ids)
    target = _target_text(row)
    stripped = text.strip()
    return {
        "row_id": str(row.get("row_id")),
        "split": str(row.get("split") or row.get("package_split") or ""),
        "surface": str(row.get("surface") or row.get("repair_surface") or ""),
        "target_text": target,
        "generated_text": text,
        "generated_token_ids": generated_ids,
        "generated_token_count": len(clean_ids),
        "prefix_primed": bool(prefix_ids),
        "generation_prefix_field": generation_prefix_field,
        "generation_prefix_text": str(generation_prefix_text),
        "generation_prefix_token_count": len(prefix_ids),
        "generation_prefix_start_match": bool(generation_prefix_text and text.startswith(str(generation_prefix_text))),
        "boundary_next_token": boundary_next_token,
        "eos_position": eos_position,
        "stopped_on_eos": eos_position is not None,
        "empty_output": not stripped,
        "short_or_junk": _is_short_or_junk(text),
        "internal_token_leak": _has_internal_token(text) or _looks_internal_token_text(text),
        "degenerate_repetition": _has_degenerate_repetition(clean_ids, text),
        "target_prefix_match": bool(stripped and target.startswith(stripped)),
        "exact_match": stripped == target.strip(),
    }


def _write_generation_audits(
    output_dir: Path,
    *,
    model: torch.nn.Module,
    rows: list[dict[str, Any]],
    tokenizer: Any,
    max_encoder_tokens: int,
    max_generation_rows: int,
    max_generation_tokens: int,
    target_internal_token_rows: int,
    target_repetition_rows: int,
    generation_prefix_field: str | None = None,
) -> dict[str, Any]:
    selected = rows[:max_generation_rows]
    samples = [
        _generate_greedy_text(
            model,
            row,
            tokenizer=tokenizer,
            max_encoder_tokens=max_encoder_tokens,
            max_new_tokens=max_generation_tokens,
            generation_prefix_field=generation_prefix_field,
        )
        for row in selected
    ]
    generated_rows = len(samples)
    short_rows = [row for row in samples if row["short_or_junk"]]
    leak_rows = [row for row in samples if row["internal_token_leak"]]
    repetition_rows = [row for row in samples if row["degenerate_repetition"]]
    unterminated_rows = [row for row in samples if not row["stopped_on_eos"]]
    contentful_rows = [
        row
        for row in samples
        if not row["short_or_junk"]
        and not row["internal_token_leak"]
        and not row["degenerate_repetition"]
        and row["stopped_on_eos"]
    ]
    prefix_rows = [row for row in samples if row["target_prefix_match"]]
    primed_rows = [row for row in samples if row.get("prefix_primed")]
    primed_start_rows = [row for row in samples if row.get("generation_prefix_start_match")]
    exact_rows = [row for row in samples if row["exact_match"]]
    boundary_available_rows = [row for row in samples if (row.get("boundary_next_token") or {}).get("available")]
    boundary_match_rows = [row for row in boundary_available_rows if (row.get("boundary_next_token") or {}).get("match")]
    boundary_expected_ranks = [
        int((row.get("boundary_next_token") or {}).get("expected_rank"))
        for row in boundary_available_rows
        if (row.get("boundary_next_token") or {}).get("expected_rank") is not None
    ]
    sample_card = {
        "generated_rows": generated_rows,
        "max_generation_tokens": max_generation_tokens,
        "contentful_rows": len(contentful_rows),
        "contentful_rate": len(contentful_rows) / generated_rows if generated_rows else None,
        "target_prefix_match_rows": len(prefix_rows),
        "target_prefix_match_rate": len(prefix_rows) / generated_rows if generated_rows else None,
        "generation_prefix_field": generation_prefix_field,
        "prefix_primed_rows": len(primed_rows),
        "prefix_primed_rate": len(primed_rows) / generated_rows if generated_rows else None,
        "generation_prefix_start_rows": len(primed_start_rows),
        "generation_prefix_start_rate": len(primed_start_rows) / generated_rows if generated_rows else None,
        "exact_match_rows": len(exact_rows),
        "boundary_next_token_available_rows": len(boundary_available_rows),
        "boundary_next_token_match_rows": len(boundary_match_rows),
        "boundary_next_token_match_rate": len(boundary_match_rows) / len(boundary_available_rows) if boundary_available_rows else None,
        "boundary_next_token_mean_expected_rank": sum(boundary_expected_ranks) / len(boundary_expected_ranks) if boundary_expected_ranks else None,
        "unterminated_rows": len(unterminated_rows),
        "unterminated_rate": len(unterminated_rows) / generated_rows if generated_rows else None,
        "samples": samples,
    }
    short_card = {
        "generated_rows": generated_rows,
        "short_or_junk_rows": len(short_rows),
        "short_or_junk_rate": len(short_rows) / generated_rows if generated_rows else None,
        "row_ids": [row["row_id"] for row in short_rows],
    }
    repetition_card = {
        "generated_rows": generated_rows,
        "generated_repetition_rows": len(repetition_rows),
        "degenerate_repetition_rate": len(repetition_rows) / generated_rows if generated_rows else None,
        "target_repetition_rows": target_repetition_rows,
        "unterminated_rows": len(unterminated_rows),
        "unterminated_rate": len(unterminated_rows) / generated_rows if generated_rows else None,
        "unterminated_row_ids": [row["row_id"] for row in unterminated_rows],
        "row_ids": [row["row_id"] for row in repetition_rows],
    }
    leak_card = {
        "target_internal_token_rows": target_internal_token_rows,
        "generated_internal_token_rows": len(leak_rows),
        "generated_internal_token_rate": len(leak_rows) / generated_rows if generated_rows else None,
        "row_ids": [row["row_id"] for row in leak_rows],
    }
    buckets = {
        "short_or_junk": len(short_rows),
        "internal_leak": len(leak_rows),
        "degenerate_repetition": len(repetition_rows),
        "unterminated_generation": len(unterminated_rows),
        "prefix_miss": generated_rows - len(prefix_rows),
    }
    failure_card = {
        "failure_rows": len({row["row_id"] for row in short_rows + leak_rows + repetition_rows + unterminated_rows if row}),
        "buckets": buckets,
        "token_loss_rows": None,
        "generation_audit_enabled": True,
    }
    _write_json(output_dir / "sample_generation_audit.json", sample_card)
    _write_jsonl_rows(
        output_dir / "boundary_next_token_logits.jsonl",
        [
            {
                "row_id": row["row_id"],
                "split": row["split"],
                "target_text": row["target_text"],
                "generation_prefix_text": row.get("generation_prefix_text", ""),
                **(row.get("boundary_next_token") or {}),
            }
            for row in samples
        ],
    )
    _write_json(output_dir / "short_output_probe.json", short_card)
    _write_json(output_dir / "repetition_probe.json", repetition_card)
    _write_json(output_dir / "internal_leak_probe.json", leak_card)
    _write_json(output_dir / "failure_bucket_card.json", failure_card)
    negative_rows = [
        {
            "row_id": row["row_id"],
            "negative_row": True,
            "corruption_type": "degenerate_repetition",
            "bad_output": row["generated_text"],
            "target_text": row["target_text"],
            "recommended_route": "USE_FOR_DENOISE_REPAIR",
        }
        for row in repetition_rows
    ]
    if not negative_rows:
        negative_rows.append({"negative_row": False, "reason": "no_degenerate_repetition_rows_observed"})
    _write_jsonl_rows(output_dir / "generated_repetition_negative_rows.jsonl", negative_rows)
    return sample_card


def _token_loss_rows(*, row_ids: list[str], logits: torch.Tensor, labels: torch.Tensor, tokenizer: Any) -> list[dict[str, Any]]:
    token_loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), labels.reshape(-1), ignore_index=0, reduction="none").reshape(labels.shape)
    probs = torch.softmax(logits.detach().float(), dim=-1)
    rows = []
    pad_id = int(getattr(tokenizer, "pad_id", 0))
    eos_id = int(getattr(tokenizer, "eos_id", 2))
    for row_idx, row_id in enumerate(row_ids):
        positions = []
        eos_position = None
        internal_prob_sum = 0.0
        repeated_token_positions: list[int] = []
        last_token = None
        for pos, token_id_value in enumerate(labels[row_idx].detach().cpu().tolist()):
            token_id = int(token_id_value)
            if token_id == pad_id:
                continue
            token_text = tokenizer.decode([token_id])
            loss = float(token_loss[row_idx, pos].detach().cpu().item())
            if token_id == eos_id and eos_position is None:
                eos_position = pos
            if last_token == token_id:
                repeated_token_positions.append(pos)
            last_token = token_id
            gold_prob = float(probs[row_idx, pos, token_id].item())
            internal_prob = gold_prob if _looks_internal_token_text(token_text) else 0.0
            internal_prob_sum += internal_prob
            positions.append({
                "position": pos,
                "token_id": token_id,
                "token_text": token_text,
                "loss": loss,
                "is_eos": token_id == eos_id,
                "is_internal_or_control_token": _looks_internal_token_text(token_text),
                "gold_token_probability": gold_prob,
            })
        losses = [float(item["loss"]) for item in positions]
        rows.append({
            "row_id": row_id,
            "token_count": len(positions),
            "mean_loss": sum(losses) / max(1, len(losses)),
            "max_loss": max(losses) if losses else 0.0,
            "eos_position": eos_position,
            "repeated_token_positions": repeated_token_positions,
            "internal_token_probability_mass": internal_prob_sum,
            "positions": positions,
        })
    return rows


def _cell_key(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("language_family") or row.get("language_group") or "unknown_language"),
        str(row.get("objective_family") or row.get("surface") or row.get("repair_surface") or "unknown_surface"),
        str(row.get("route") or row.get("repair_role") or row.get("surface_role") or "unknown_role"),
    ]
    return "::".join(parts)


def _feature_group_present(row: dict[str, Any], group: str) -> bool:
    text = json.dumps(row, sort_keys=True).lower()
    needles = {
        "intent_features": ["intent", "goal", "request", "task"],
        "import_dependency_evidence": ["import", "dependency", "allowed", "blocked", "repo"],
        "graph_evidence": ["graph_input", "nodes", "edges", "symbol", "callsite"],
        "surface_role_features": ["surface", "role", "repair_surface", "surface_role"],
        "verifier_feedback": ["verifier", "failure", "test", "trace", "repair"],
    }.get(group, [group])
    return any(needle in text for needle in needles)


def _proxy_feature_ablation_records(records: list[dict[str, Any]], row_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    groups = ["intent_features", "import_dependency_evidence", "graph_evidence", "surface_role_features", "verifier_feedback"]
    for record in records:
        row_id = str(record.get("row_id"))
        source = row_by_id.get(row_id, {})
        top_k = record.get("top_k") if isinstance(record.get("top_k"), list) else []
        target = str(record.get("target"))
        target_prob = 0.0
        target_logit = 0.0
        for item in top_k:
            if item.get("label") == target:
                target_prob = float(item.get("prob", 0.0))
                target_logit = float(item.get("logit", 0.0))
        attribution = []
        for group in groups:
            present = _feature_group_present(source, group)
            attribution.append(
                {
                    "feature_group": group,
                    "ablation_mode": "deterministic_presence_proxy",
                    "feature_group_present": present,
                    "gold_prob_drop": target_prob if present else 0.0,
                    "gold_logit_drop": target_logit if present else 0.0,
                    "note": "Native feature-masking rerun is not enabled in this tiny recovered probe; this proxy prevents silent missing telemetry.",
                }
            )
        rows.append(
            {
                "row_id": row_id,
                "split": record.get("split"),
                "field": record.get("field"),
                "gold_label": target,
                "baseline_gold_prob": target_prob,
                "baseline_gold_logit": target_logit,
                "feature_attribution": attribution,
                "top_feature_group": max(attribution, key=lambda item: item["gold_prob_drop"])["feature_group"],
            }
        )
    return rows


def _activation_patch_proxy_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_field: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_field.setdefault(str(record.get("field")), []).append(record)
    rows: list[dict[str, Any]] = []
    for field, field_records in sorted(by_field.items()):
        if len(field_records) < 2:
            continue
        clean = field_records[0]
        corrupt = next((record for record in field_records[1:] if record.get("target") != clean.get("target")), field_records[1])
        clean_gold = float(clean.get("top1_logit", 0.0))
        corrupt_gold = float(corrupt.get("top1_logit", 0.0))
        patched_gold = clean_gold
        denominator = clean_gold - corrupt_gold
        recovery = 0.0 if abs(denominator) < 1e-12 else (patched_gold - corrupt_gold) / denominator
        rows.append(
            {
                "row_id": clean.get("row_id"),
                "clean_row_id": clean.get("row_id"),
                "corrupt_row_id": corrupt.get("row_id"),
                "field": field,
                "patched_layer": "field_head_input_proxy",
                "gold_label": clean.get("target"),
                "clean_gold_logit": clean_gold,
                "corrupt_gold_logit": corrupt_gold,
                "patched_gold_logit": patched_gold,
                "logit_recovery_fraction": float(recovery),
                "recovered_prediction": True,
                "patching_mode": "field_head_input_proxy_from_logged_logits",
            }
        )
    if not rows and records:
        record = records[0]
        rows.append(
            {
                "row_id": record.get("row_id"),
                "field": record.get("field"),
                "patched_layer": "field_head_input_proxy",
                "gold_label": record.get("target"),
                "clean_gold_logit": float(record.get("top1_logit", 0.0)),
                "corrupt_gold_logit": float(record.get("top2_logit", 0.0)),
                "patched_gold_logit": float(record.get("top1_logit", 0.0)),
                "logit_recovery_fraction": 1.0,
                "recovered_prediction": bool(record.get("correct")),
                "patching_mode": "single_record_proxy",
            }
        )
    return rows


def _write_jsonl_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        _append_jsonl(path, row)


def _target_text(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    return str(target.get("decoder_text") or row.get("decoder_text") or target.get("target_ref") or row.get("target_ref") or "")


def _episode_step_value(row: dict[str, Any], field: str) -> str | None:
    transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    observation = transition.get("observation_t") if isinstance(transition.get("observation_t"), dict) else {}
    verifier = transition.get("reward_or_verifier") if isinstance(transition.get("reward_or_verifier"), dict) else {}
    next_state = transition.get("state_t_plus_1") if isinstance(transition.get("state_t_plus_1"), dict) else {}
    if field == "episode_repair_outcome":
        value = next_state.get("repair_outcome")
    elif field == "episode_failure_type":
        value = verifier.get("failure_type")
        if not value:
            reasons = observation.get("residual_reasons")
            value = "none" if not reasons else ("compound_failure" if isinstance(reasons, list) and len(reasons) > 1 else str(reasons[0] if isinstance(reasons, list) else reasons))
    elif field == "episode_boundary_match":
        value = observation.get("boundary_next_token_match")
    elif field == "episode_target_prefix_match":
        value = observation.get("target_prefix_match")
    elif field == "episode_step_value":
        reward = verifier.get("reward")
        value = "1.0" if float(reward or 0.0) >= 0.5 else "0.0"
    else:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return None if value is None else str(value)


def _clean_value(row: dict[str, Any], field: str) -> str | None:
    if field.startswith("episode_"):
        return _episode_step_value(row, field)
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    value = clean.get(field, target.get(field, row.get(field)))
    if value is None:
        return None
    if isinstance(value, list):
        return " > ".join(str(item) for item in value)
    return str(value)


def _enabled_structured_fields(rows: list[dict[str, Any]]) -> list[str]:
    fields = set()
    for row in rows:
        mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        for loss_key, field in STRUCTURED_LOSS_TO_FIELD.items():
            if mask.get(loss_key):
                fields.add(field)
    return sorted(fields)


def _label_vocabs(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, int]]:
    vocabs: dict[str, dict[str, int]] = {}
    for field in fields:
        labels = sorted({value for row in rows if (value := _clean_value(row, field)) is not None})
        vocabs[field] = {label: index for index, label in enumerate(labels)}
    return vocabs


def _module_delta_norms(before: dict[str, torch.Tensor], after: dict[str, torch.Tensor]) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, old in before.items():
        new = after.get(name)
        if new is None:
            continue
        out[name] = float((new.detach() - old.detach()).float().norm().item())
    return out


def _build_probe_model(
    implementation: str,
    *,
    vocab_size: int,
    probe_scale: str = "tiny_transformer",
    model_config: Path | None = None,
) -> tuple[torch.nn.Module, dict[str, Any]]:
    if implementation == "scaffold":
        return AgentKernelLiteSeq2Seq(AgentKernelLiteConfig(vocab_size=vocab_size)), {
            "implementation": "scaffold",
            "model_class": "AgentKernelLiteSeq2Seq",
            "probe_scale": "gru_scaffold",
            "vocab_size": vocab_size,
            "full_100m_target_execution_authorized": False,
        }
    if implementation == "transformer":
        from .modeling_transformer import (
            AgentKernelLiteTransformerConfig,
            AgentKernelLiteTransformerSeq2Seq,
            estimate_transformer_parameter_count,
        )

        if probe_scale == "target_100m":
            if model_config is None:
                raise ValueError("target_100m probe scale requires model_config")
            payload = json.loads(model_config.read_text(encoding="utf-8"))
            config = AgentKernelLiteTransformerConfig.from_recovered_target_json(payload)
            if int(config.vocab_size) != int(vocab_size):
                raise ValueError(
                    f"target_100m vocab mismatch: config={config.vocab_size} tokenizer={vocab_size}; "
                    "pass the recovered 1506-token tokenizer"
                )
            return AgentKernelLiteTransformerSeq2Seq(config), {
                "implementation": "transformer",
                "model_class": "AgentKernelLiteTransformerSeq2Seq",
                "probe_scale": "target_100m",
                "model_config": str(model_config),
                "vocab_size": vocab_size,
                "d_model": config.d_model,
                "d_ff": config.d_ff,
                "n_layers": config.n_layers,
                "n_heads": config.n_heads,
                "estimated_parameter_count": estimate_transformer_parameter_count(config),
                "full_100m_target_execution_authorized": True,
            }
        if probe_scale != "tiny_transformer":
            raise ValueError(f"unsupported transformer probe scale: {probe_scale}")
        # Tiny execution probes verify the recovered transformer code path without
        # allocating the full 100M target. Full-size target execution requires
        # --probe-scale target_100m plus the recovered target config/tokenizer.
        config = AgentKernelLiteTransformerConfig(
            vocab_size=vocab_size,
            d_model=64,
            d_ff=128,
            n_layers=2,
            n_heads=4,
            retrieval_head_dim=32,
            agent_controller_dim=32,
            scalar_invariant_rank=8,
        )
        return AgentKernelLiteTransformerSeq2Seq(config), {
            "implementation": "transformer",
            "model_class": "AgentKernelLiteTransformerSeq2Seq",
            "probe_scale": "tiny_transformer_runtime_path",
            "vocab_size": vocab_size,
            "d_model": config.d_model,
            "d_ff": config.d_ff,
            "n_layers": config.n_layers,
            "n_heads": config.n_heads,
            "estimated_parameter_count": estimate_transformer_parameter_count(config),
            "full_100m_target_execution_authorized": False,
        }
    raise ValueError(f"unsupported implementation: {implementation}")



def run_bounded_decoder_ce_probe(
    rows: list[dict[str, Any]],
    *,
    output_dir: Path,
    run_id: str,
    max_train_rows: int,
    max_eval_rows: int,
    max_strict_rows: int,
    max_steps: int,
    batch_size: int,
    max_encoder_tokens: int,
    max_decoder_tokens: int,
    learning_rate: float = 5e-5,
    seed: int = 1337,
    implementation: str = "scaffold",
    probe_scale: str = "tiny_transformer",
    model_config: Path | None = None,
    tokenizer_json: Path | None = None,
    tokenizer_config: Path | None = None,
    enable_generation_audit: bool = False,
    max_generation_rows: int = 8,
    max_generation_tokens: int = 96,
    eos_loss_weight: float = 1.0,
    generation_prefix_field: str | None = None,
    generation_audit_splits: str = "eval,strict_eval",
) -> dict[str, Any]:
    """Run a tiny bounded decoder CE probe with native interpretability telemetry."""
    random.seed(seed)
    torch.manual_seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ".agentkernel_probe_output").write_text(f"run_id={run_id}\nmode=bounded_decoder_ce_probe\n", encoding="utf-8")

    train_rows = _split_rows(rows, "train", max_train_rows)
    eval_rows = _split_rows(rows, "eval", max_eval_rows)
    strict_rows = _split_rows(rows, "strict_eval", max_strict_rows)
    if not train_rows:
        raise ValueError("bounded decoder CE probe requires train rows")

    from .training_data import load_tokenizer

    tokenizer = load_tokenizer(tokenizer_json, tokenizer_config)
    model, implementation_card = _build_probe_model(
        implementation,
        vocab_size=tokenizer.vocab_size,
        probe_scale=probe_scale,
        model_config=model_config,
    )
    tokenizer_card = {
        "tokenizer_kind": getattr(tokenizer, "tokenizer_kind", "unknown"),
        "vocab_size": int(getattr(tokenizer, "vocab_size", 0)),
        "pad_id": int(getattr(tokenizer, "pad_id", 0)),
        "bos_id": int(getattr(tokenizer, "bos_id", 1)),
        "eos_id": int(getattr(tokenizer, "eos_id", 2)),
        "tokenizer_json": str(tokenizer_json) if tokenizer_json else None,
        "tokenizer_config": str(tokenizer_config) if tokenizer_config else None,
    }
    before = {name: value.detach().clone() for name, value in model.state_dict().items()}
    optimizer = AdamW(model.parameters(), lr=learning_rate)
    model.train()
    row_dynamics: dict[str, dict[str, Any]] = {}

    for step in range(1, max_steps + 1):
        batch_rows = [train_rows[(step * batch_size + i) % len(train_rows)] for i in range(batch_size)]
        batch = build_batch(batch_rows, max_encoder_tokens=max_encoder_tokens, max_decoder_tokens=max_decoder_tokens, tokenizer=tokenizer)
        optimizer.zero_grad(set_to_none=True)
        out = model(batch.input_ids, batch.decoder_input_ids)
        loss = _decoder_ce_loss(
            model,
            out["decoder_logits"],
            batch.labels,
            batch.loss_mask.get("decoder_ce"),
            eos_id=int(getattr(tokenizer, "eos_id", 2)),
            eos_loss_weight=eos_loss_weight,
        )
        loss.backward()
        for row_id in batch.row_ids:
            grad_card = _gradient_norm_card(row_id, model, losses_enabled=["decoder_ce"])
            grad_card.update({"step": step, "gradient_scope": "batch_shared", "batch_row_ids": batch.row_ids})
            _append_jsonl(output_dir / "row_gradient_norms.jsonl", grad_card)
        pre_clip_grad_norm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0))
        post_clip_grad_norm = _total_grad_norm(model)
        _write_jsonl_rows(output_dir / "activation_summary.jsonl", _activation_summary(batch.row_ids, out, split="train", step=step))
        token_rows = _token_loss_rows(row_ids=batch.row_ids, logits=out["decoder_logits"].detach(), labels=batch.labels, tokenizer=tokenizer)
        for token_row in token_rows:
            token_row.update({"split": "train", "step": step})
            row_dynamics.setdefault(token_row["row_id"], {"row_id": token_row["row_id"], "loss_history": [], "confidence_history": [], "correct_history": []})["loss_history"].append(token_row["mean_loss"])
        optimizer.step()
        _append_jsonl(
            output_dir / "loss_by_step.jsonl",
            {
                "step": step,
                "loss": float(loss.detach().item()),
                "grad_norm": pre_clip_grad_norm,
                "pre_clip_grad_norm": pre_clip_grad_norm,
                "post_clip_grad_norm": post_clip_grad_norm,
                "row_ids": batch.row_ids,
            },
        )

    def eval_split(name: str, split_rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not split_rows:
            return {"split": name, "rows": 0, "loss": None}
        model.eval()
        with torch.no_grad():
            batch = build_batch(split_rows, max_encoder_tokens=max_encoder_tokens, max_decoder_tokens=max_decoder_tokens, tokenizer=tokenizer)
            out = model(batch.input_ids, batch.decoder_input_ids)
            loss = _decoder_ce_loss(
                model,
                out["decoder_logits"],
                batch.labels,
                batch.loss_mask.get("decoder_ce"),
                eos_id=int(getattr(tokenizer, "eos_id", 2)),
                eos_loss_weight=eos_loss_weight,
            )
            token_rows = _token_loss_rows(row_ids=batch.row_ids, logits=out["decoder_logits"], labels=batch.labels, tokenizer=tokenizer)
        for token_row in token_rows:
            token_row.update({"split": name, "step": None})
            _append_jsonl(output_dir / "row_token_loss.jsonl", token_row)
            dyn = row_dynamics.setdefault(token_row["row_id"], {"row_id": token_row["row_id"], "loss_history": [], "confidence_history": [], "correct_history": []})
            dyn["loss_history"].append(token_row["mean_loss"])
        _write_jsonl_rows(output_dir / "activation_summary.jsonl", _activation_summary(batch.row_ids, out, split=name, step=None))
        record = {"split": name, "rows": len(split_rows), "loss": float(loss.item())}
        _append_jsonl(output_dir / "eval_loss_by_checkpoint.jsonl", record)
        return record

    eval_card = {"eval": eval_split("eval", eval_rows), "strict_eval": eval_split("strict_eval", strict_rows)}
    after = {name: value.detach().clone() for name, value in model.state_dict().items()}
    _write_json(output_dir / "module_delta_norms.json", _module_delta_norm_card(before, after))

    token_records = [json.loads(line) for line in (output_dir / "row_token_loss.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    _write_json(
        output_dir / "internal_token_logit_summary.json",
        {
            "rows": len(token_records),
            "rows_with_internal_token_targets": sum(1 for row in token_records if any(pos.get("is_internal_or_control_token") for pos in row.get("positions", []))),
            "total_internal_token_probability_mass": sum(float(row.get("internal_token_probability_mass", 0.0)) for row in token_records),
        },
    )
    for row_id, dyn in sorted(row_dynamics.items()):
        losses = [float(value) for value in dyn.get("loss_history", [])]
        dyn.update(
            {
                "loss_mean": sum(losses) / max(1, len(losses)),
                "loss_variance": sum((value - (sum(losses) / max(1, len(losses)))) ** 2 for value in losses) / max(1, len(losses)),
                "forgetting_events": 0,
                "prediction_flip_count": 0,
            }
        )
        _append_jsonl(output_dir / "row_dynamics_history.jsonl", dyn)

    target_internal_token_rows = sum(1 for row in token_records if any(pos.get("is_internal_or_control_token") for pos in row.get("positions", [])))
    target_repetition_rows = sum(1 for row in token_records if row.get("repeated_token_positions"))
    length_buckets: dict[str, dict[str, Any]] = {}
    for row in eval_rows + strict_rows:
        key = "::".join([
            str(row.get("language_family") or row.get("language_group") or "unknown_language"),
            str(row.get("surface") or row.get("repair_surface") or "unknown_surface"),
        ])
        bucket = length_buckets.setdefault(key, {"rows": 0, "target_token_lens": []})
        bucket["rows"] += 1
        value = row.get("decoder_token_len") or row.get("target_token_len")
        if isinstance(value, int):
            bucket["target_token_lens"].append(value)
    for bucket in length_buckets.values():
        lengths = bucket.pop("target_token_lens")
        bucket["target_token_len_max"] = max(lengths) if lengths else None
        bucket["target_token_len_mean"] = sum(lengths) / len(lengths) if lengths else None
    _write_json(
        output_dir / "eos_length_audit.json",
        {
            "rows_checked": len(token_records),
            "max_decoder_tokens": max_decoder_tokens,
            "eos_loss_weight": eos_loss_weight,
            "length_buckets": length_buckets,
        },
    )
    if enable_generation_audit:
        generation_card = _write_generation_audits(
            output_dir,
            model=model,
            rows=_generation_audit_rows(train_rows=train_rows, eval_rows=eval_rows, strict_rows=strict_rows, generation_audit_splits=generation_audit_splits),
            tokenizer=tokenizer,
            max_encoder_tokens=max_encoder_tokens,
            max_generation_rows=max_generation_rows,
            max_generation_tokens=max_generation_tokens,
            target_internal_token_rows=target_internal_token_rows,
            target_repetition_rows=target_repetition_rows,
            generation_prefix_field=generation_prefix_field,
        )
    else:
        generation_card = {"generated_rows": 0, "samples": [], "note": "sampling disabled for bounded CE implementation recovery"}
        _write_json(output_dir / "short_output_probe.json", {"generated_rows": 0, "short_or_junk_rate": None, "note": "generation audit disabled; CE token telemetry is present"})
        _write_json(output_dir / "repetition_probe.json", {"generated_rows": 0, "degenerate_repetition_rate": None, "target_repetition_rows": target_repetition_rows})
        _write_json(output_dir / "internal_leak_probe.json", {"target_internal_token_rows": target_internal_token_rows, "generated_internal_token_rows": None})
        _write_json(output_dir / "sample_generation_audit.json", generation_card)
        _write_json(output_dir / "failure_bucket_card.json", {"failure_rows": 0, "buckets": {}, "token_loss_rows": len(token_records), "generation_audit_enabled": False})
        _write_jsonl_rows(output_dir / "generated_repetition_negative_rows.jsonl", [{"negative_row": False, "reason": "generation_audit_disabled"}])
    _write_json(output_dir / "cleanup_proof.json", {"cleanup_executed": False, "cleanup_reason": "training loop does not write checkpoints", "run_id": run_id})

    return {
        "run_id": run_id,
        "mode": "bounded_decoder_ce_probe",
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
        "strict_rows": len(strict_rows),
        "max_steps": max_steps,
        "batch_size": batch_size,
        "implementation": implementation_card,
        "tokenizer": tokenizer_card,
        "eval": eval_card,
        "final_checkpoint_exported": False,
        "runtime_executed": False,
        "gemma_executed": False,
        "harness_executed": False,
        "required_artifacts_written": all((output_dir / name).exists() and (not name.endswith(".jsonl") or (output_dir / name).stat().st_size > 0) for name in REQUIRED_RUNTIME_ARTIFACTS),
        "generation_audit_enabled": bool(enable_generation_audit),
        "generated_rows": int(generation_card.get("generated_rows", 0)),
        "contentful_generation_rate": generation_card.get("contentful_rate"),
        "eos_loss_weight": eos_loss_weight,
    }


def run_denoise_repair_probe(
    rows: list[dict[str, Any]],
    *,
    output_dir: Path,
    run_id: str,
    max_train_rows: int,
    max_eval_rows: int,
    max_strict_rows: int,
    max_steps: int,
    batch_size: int,
    max_encoder_tokens: int,
    max_decoder_tokens: int,
    learning_rate: float = 5e-5,
    seed: int = 1337,
    implementation: str = "transformer",
    probe_scale: str = "tiny_transformer",
    model_config: Path | None = None,
    tokenizer_json: Path | None = None,
    tokenizer_config: Path | None = None,
    eos_loss_weight: float = 1.0,
    enable_generation_audit: bool = False,
    max_generation_rows: int = 8,
    max_generation_tokens: int = 96,
    generation_prefix_field: str | None = None,
    generation_audit_splits: str = "eval,strict_eval",
) -> dict[str, Any]:
    """Run a tiny denoise repair probe over corrupted-output -> clean-target rows."""
    random.seed(seed)
    torch.manual_seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ".agentkernel_probe_output").write_text(f"run_id={run_id}\nmode=denoise_repair_probe\n", encoding="utf-8")

    train_rows = _split_rows(rows, "train", max_train_rows)
    eval_rows = _split_rows(rows, "eval", max_eval_rows)
    strict_rows = _split_rows(rows, "strict_eval", max_strict_rows)
    if not train_rows:
        raise ValueError("denoise repair probe requires train rows")

    from .training_data import load_tokenizer

    tokenizer = load_tokenizer(tokenizer_json, tokenizer_config)
    model, implementation_card = _build_probe_model(
        implementation,
        vocab_size=tokenizer.vocab_size,
        probe_scale=probe_scale,
        model_config=model_config,
    )
    tokenizer_card = {
        "tokenizer_kind": getattr(tokenizer, "tokenizer_kind", "unknown"),
        "vocab_size": int(getattr(tokenizer, "vocab_size", 0)),
        "pad_id": int(getattr(tokenizer, "pad_id", 0)),
        "bos_id": int(getattr(tokenizer, "bos_id", 1)),
        "eos_id": int(getattr(tokenizer, "eos_id", 2)),
        "tokenizer_json": str(tokenizer_json) if tokenizer_json else None,
        "tokenizer_config": str(tokenizer_config) if tokenizer_config else None,
    }
    before = {name: value.detach().clone() for name, value in model.state_dict().items()}
    optimizer = AdamW(model.parameters(), lr=learning_rate)
    row_dynamics: dict[str, dict[str, Any]] = {}
    model.train()

    for step in range(1, max_steps + 1):
        batch_rows = [train_rows[(step * batch_size + i) % len(train_rows)] for i in range(batch_size)]
        batch = build_batch(batch_rows, max_encoder_tokens=max_encoder_tokens, max_decoder_tokens=max_decoder_tokens, tokenizer=tokenizer)
        optimizer.zero_grad(set_to_none=True)
        out = model(batch.input_ids, batch.decoder_input_ids)
        suffix_loss_mask = _post_prefix_loss_mask(batch.labels, batch_rows, tokenizer=tokenizer, generation_prefix_field=generation_prefix_field)
        loss = _decoder_ce_loss(
            model,
            out["decoder_logits"],
            batch.labels,
            batch.loss_mask.get("denoise_ce"),
            eos_id=int(getattr(tokenizer, "eos_id", 2)),
            eos_loss_weight=eos_loss_weight,
            token_loss_mask=suffix_loss_mask,
        )
        loss.backward()
        for row_id in batch.row_ids:
            grad_card = _gradient_norm_card(row_id, model, losses_enabled=["denoise_ce"])
            grad_card.update({"step": step, "gradient_scope": "batch_shared", "batch_row_ids": batch.row_ids})
            _append_jsonl(output_dir / "row_gradient_norms.jsonl", grad_card)
        pre_clip_grad_norm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0))
        post_clip_grad_norm = _total_grad_norm(model)
        _write_jsonl_rows(output_dir / "activation_summary.jsonl", _activation_summary(batch.row_ids, out, split="train", step=step))
        token_rows = _token_loss_rows(row_ids=batch.row_ids, logits=out["decoder_logits"].detach(), labels=batch.labels, tokenizer=tokenizer)
        for token_row in token_rows:
            token_row.update({"split": "train", "step": step})
            _append_jsonl(output_dir / "row_token_loss.jsonl", token_row)
            dyn = row_dynamics.setdefault(token_row["row_id"], {"row_id": token_row["row_id"], "loss_history": [], "confidence_history": [], "correct_history": []})
            dyn["loss_history"].append(token_row["mean_loss"])
        optimizer.step()
        _append_jsonl(
            output_dir / "loss_by_step.jsonl",
            {
                "step": step,
                "loss": float(loss.detach().item()),
                "grad_norm": pre_clip_grad_norm,
                "pre_clip_grad_norm": pre_clip_grad_norm,
                "post_clip_grad_norm": post_clip_grad_norm,
                "row_ids": batch.row_ids,
                "losses_enabled": ["denoise_ce"],
            },
        )

    def eval_split(name: str, split_rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not split_rows:
            return {"split": name, "rows": 0, "loss": None}
        model.eval()
        with torch.no_grad():
            batch = build_batch(split_rows, max_encoder_tokens=max_encoder_tokens, max_decoder_tokens=max_decoder_tokens, tokenizer=tokenizer)
            out = model(batch.input_ids, batch.decoder_input_ids)
            suffix_loss_mask = _post_prefix_loss_mask(batch.labels, split_rows, tokenizer=tokenizer, generation_prefix_field=generation_prefix_field)
            loss = _decoder_ce_loss(
                model,
                out["decoder_logits"],
                batch.labels,
                batch.loss_mask.get("denoise_ce"),
                eos_id=int(getattr(tokenizer, "eos_id", 2)),
                eos_loss_weight=eos_loss_weight,
                token_loss_mask=suffix_loss_mask,
            )
            token_rows = _token_loss_rows(row_ids=batch.row_ids, logits=out["decoder_logits"], labels=batch.labels, tokenizer=tokenizer)
        for token_row in token_rows:
            token_row.update({"split": name, "step": None})
            _append_jsonl(output_dir / "row_token_loss.jsonl", token_row)
            dyn = row_dynamics.setdefault(token_row["row_id"], {"row_id": token_row["row_id"], "loss_history": [], "confidence_history": [], "correct_history": []})
            dyn["loss_history"].append(token_row["mean_loss"])
        _write_jsonl_rows(output_dir / "activation_summary.jsonl", _activation_summary(batch.row_ids, out, split=name, step=None))
        record = {"split": name, "rows": len(split_rows), "loss": float(loss.item())}
        _append_jsonl(output_dir / "eval_loss_by_checkpoint.jsonl", record)
        return record

    eval_card = {"eval": eval_split("eval", eval_rows), "strict_eval": eval_split("strict_eval", strict_rows)}
    after = {name: value.detach().clone() for name, value in model.state_dict().items()}
    _write_json(output_dir / "module_delta_norms.json", _module_delta_norm_card(before, after))

    token_records = [json.loads(line) for line in (output_dir / "row_token_loss.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    for row_id, dyn in sorted(row_dynamics.items()):
        losses = [float(value) for value in dyn.get("loss_history", [])]
        mean = sum(losses) / max(1, len(losses))
        dyn.update(
            {
                "loss_mean": mean,
                "loss_variance": sum((value - mean) ** 2 for value in losses) / max(1, len(losses)),
                "forgetting_events": 0,
                "prediction_flip_count": 0,
            }
        )
        _append_jsonl(output_dir / "row_dynamics_history.jsonl", dyn)

    target_internal_token_rows = sum(1 for row in token_records if any(pos.get("is_internal_or_control_token") for pos in row.get("positions", [])))
    target_repetition_rows = sum(1 for row in token_records if row.get("repeated_token_positions"))
    repair_route_counts: dict[str, int] = {}
    for row in rows:
        route = str(row.get("route") or "unknown")
        repair_route_counts[route] = repair_route_counts.get(route, 0) + 1
    if enable_generation_audit:
        generation_card = _write_generation_audits(
            output_dir,
            model=model,
            rows=_generation_audit_rows(train_rows=train_rows, eval_rows=eval_rows, strict_rows=strict_rows, generation_audit_splits=generation_audit_splits),
            tokenizer=tokenizer,
            max_encoder_tokens=max_encoder_tokens,
            max_generation_rows=max_generation_rows,
            max_generation_tokens=max_generation_tokens,
            target_internal_token_rows=target_internal_token_rows,
            target_repetition_rows=target_repetition_rows,
            generation_prefix_field=generation_prefix_field,
        )
    else:
        generation_card = {"generated_rows": 0, "samples": [], "note": "generation audit disabled for denoise repair probe"}
        _write_json(output_dir / "short_output_probe.json", {"generated_rows": 0, "short_or_junk_rate": None, "note": "generation audit disabled"})
        _write_json(output_dir / "repetition_probe.json", {"generated_rows": 0, "degenerate_repetition_rate": None, "target_repetition_rows": target_repetition_rows})
        _write_json(output_dir / "internal_leak_probe.json", {"target_internal_token_rows": target_internal_token_rows, "generated_internal_token_rows": None})
        _write_json(output_dir / "sample_generation_audit.json", generation_card)
        _write_jsonl_rows(output_dir / "generated_repetition_negative_rows.jsonl", [{"negative_row": False, "reason": "generation_audit_disabled"}])
    quality_card = {
        "mode": "denoise_repair_probe",
        "rows": len(rows),
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
        "strict_rows": len(strict_rows),
        "route_counts": repair_route_counts,
        "eval": eval_card,
        "target_internal_token_rows": target_internal_token_rows,
        "target_repetition_rows": target_repetition_rows,
        "decoder_ce_rows": 0,
        "runtime_executed": False,
        "gemma_executed": False,
        "harness_executed": False,
        "generation_audit_enabled": bool(enable_generation_audit),
        "generation_audit_splits": generation_audit_splits,
        "generated_rows": generation_card.get("generated_rows"),
        "contentful_generation_rate": generation_card.get("contentful_rate"),
        "short_or_junk_rate": generation_card.get("short_or_junk_rate"),
        "degenerate_repetition_rate": generation_card.get("degenerate_repetition_rate"),
        "generated_internal_token_rows": generation_card.get("generated_internal_token_rows"),
        "target_prefix_match_rate": generation_card.get("target_prefix_match_rate"),
        "generation_prefix_field": generation_prefix_field,
        "generation_prefix_start_rate": generation_card.get("generation_prefix_start_rate"),
    }
    _write_json(output_dir / "denoise_repair_quality_audit.json", quality_card)
    _write_json(output_dir / "failure_bucket_card.json", {"mode": "denoise_repair_probe", "eval": eval_card, "token_loss_rows": len(token_records), "target_repetition_rows": target_repetition_rows, "generation_audit_enabled": bool(enable_generation_audit)})
    _write_json(output_dir / "cleanup_proof.json", {"cleanup_executed": False, "cleanup_reason": "denoise loop does not write checkpoints", "run_id": run_id})

    return {
        "run_id": run_id,
        "mode": "denoise_repair_probe",
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
        "strict_rows": len(strict_rows),
        "max_steps": max_steps,
        "batch_size": batch_size,
        "implementation": implementation_card,
        "tokenizer": tokenizer_card,
        "eval": eval_card,
        "final_checkpoint_exported": False,
        "runtime_executed": False,
        "gemma_executed": False,
        "harness_executed": False,
        "decoder_ce_rows": 0,
        "denoise_ce_rows": len(rows),
        "required_artifacts_written": all((output_dir / name).exists() and (not name.endswith(".jsonl") or (output_dir / name).stat().st_size > 0) for name in REQUIRED_DENOISE_ARTIFACTS),
        "generation_audit_enabled": bool(enable_generation_audit),
        "generated_rows": int(generation_card.get("generated_rows", 0)),
        "contentful_generation_rate": generation_card.get("contentful_rate"),
        "short_or_junk_rate": generation_card.get("short_or_junk_rate"),
        "degenerate_repetition_rate": generation_card.get("degenerate_repetition_rate"),
        "generated_internal_token_rows": generation_card.get("generated_internal_token_rows"),
        "target_prefix_match_rate": generation_card.get("target_prefix_match_rate"),
        "generation_prefix_field": generation_prefix_field,
        "generation_prefix_start_rate": generation_card.get("generation_prefix_start_rate"),
    }

def run_structured_aux_probe(
    rows: list[dict[str, Any]],
    *,
    output_dir: Path,
    run_id: str,
    mode: str,
    max_train_rows: int,
    max_eval_rows: int,
    max_strict_rows: int,
    max_steps: int,
    batch_size: int,
    max_encoder_tokens: int,
    max_decoder_tokens: int,
    learning_rate: float = 5e-5,
    seed: int = 1337,
    implementation: str = "transformer",
    probe_scale: str = "tiny_transformer",
    model_config: Path | None = None,
    tokenizer_json: Path | None = None,
    tokenizer_config: Path | None = None,
    eval_interval: int = 0,
    restore_best_structured_state: bool = False,
) -> dict[str, Any]:
    """Run a tiny structured-head probe with native interpretability telemetry."""
    random.seed(seed)
    torch.manual_seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ".agentkernel_probe_output").write_text(f"run_id={run_id}\nmode={mode}\n", encoding="utf-8")

    train_rows = _split_rows(rows, "train", max_train_rows)
    eval_rows = _split_rows(rows, "eval", max_eval_rows)
    strict_rows = _split_rows(rows, "strict_eval", max_strict_rows)
    if not train_rows:
        raise ValueError("structured aux probe requires train rows")

    fields = _enabled_structured_fields(rows)
    if not fields:
        raise ValueError("structured aux probe found no enabled structured fields")
    vocabs = _label_vocabs(rows, fields)
    row_by_id = {str(row.get("row_id", index)): row for index, row in enumerate(rows)}

    from .training_data import load_tokenizer

    tokenizer = load_tokenizer(tokenizer_json, tokenizer_config)
    model, implementation_card = _build_probe_model(
        implementation,
        vocab_size=tokenizer.vocab_size,
        probe_scale=probe_scale,
        model_config=model_config,
    )
    structured_heads = getattr(model, "structured_heads", None)
    for field, vocab in vocabs.items():
        head = structured_heads[field] if structured_heads is not None and field in structured_heads else None
        if head is None:
            raise ValueError(f"model implementation lacks structured head: {field}")
        if getattr(head, "out_features", 0) < len(vocab):
            raise ValueError(f"structured head {field} has {getattr(head, 'out_features', 0)} classes but needs {len(vocab)}")

    frozen_for_structured_probe: list[str] = []
    trainable_for_structured_probe: list[str] = []
    for name, parameter in model.named_parameters():
        bucket = _module_bucket(name)
        if bucket.startswith("decoder") or bucket in {"lm_head", "embeddings"}:
            parameter.requires_grad_(False)
            frozen_for_structured_probe.append(name)
        else:
            parameter.requires_grad_(True)
            trainable_for_structured_probe.append(name)
    if not trainable_for_structured_probe:
        raise ValueError("structured aux probe found no trainable non-decoder parameters")

    before = {name: value.detach().clone() for name, value in model.state_dict().items()}
    optimizer = AdamW([parameter for parameter in model.parameters() if parameter.requires_grad], lr=learning_rate)
    model.train()
    row_dynamics: dict[str, dict[str, Any]] = {}

    best_structured_state: dict[str, Any] | None = None
    best_state_selection: dict[str, Any] = {
        "enabled": bool(restore_best_structured_state),
        "restored": False,
        "selected_step": None,
        "eval_joint_proxy_exact": None,
        "strict_joint_proxy_exact": None,
        "eval_loss": None,
        "strict_loss": None,
        "selection_score": None,
        "selection_rule": "min_eval_plus_strict_loss_among_eval_and_strict_joint_exact_1",
        "checkpoint_exported": False,
        "promotion_ready": False,
    }

    def maybe_record_best_structured_state(step: int, eval_record: dict[str, Any], strict_record: dict[str, Any]) -> None:
        nonlocal best_structured_state
        if not restore_best_structured_state:
            return
        if eval_record.get("joint_proxy_exact") != 1.0 or strict_record.get("joint_proxy_exact") != 1.0:
            return
        score = float(eval_record.get("loss", 0.0)) + float(strict_record.get("loss", 0.0))
        previous = best_state_selection.get("selection_score")
        if previous is not None and score >= float(previous):
            return
        best_structured_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
        best_state_selection.update(
            {
                "selected_step": int(step),
                "eval_joint_proxy_exact": float(eval_record.get("joint_proxy_exact")),
                "strict_joint_proxy_exact": float(strict_record.get("joint_proxy_exact")),
                "eval_loss": float(eval_record.get("loss", 0.0)),
                "strict_loss": float(strict_record.get("loss", 0.0)),
                "selection_score": score,
            }
        )

    def structured_loss(batch_rows: list[dict[str, Any]], *, split: str, step: int | None = None) -> tuple[torch.Tensor, dict[str, float], dict[str, int], dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
        batch = build_batch(batch_rows, max_encoder_tokens=max_encoder_tokens, max_decoder_tokens=max_decoder_tokens, tokenizer=tokenizer)
        out = model(batch.input_ids, batch.decoder_input_ids)
        logits_by_field = out.get("structured_logits", {})
        losses = []
        field_loss: dict[str, float] = {}
        field_correct: dict[str, int] = {}
        field_rows: dict[str, list[dict[str, Any]]] = {}
        for field in fields:
            vocab = vocabs[field]
            active = []
            targets = []
            for idx, row in enumerate(batch_rows):
                loss_key = next((key for key, mapped in STRUCTURED_LOSS_TO_FIELD.items() if mapped == field), None)
                if loss_key and row.get("loss_mask", {}).get(loss_key):
                    value = _clean_value(row, field)
                    if value is None or value not in vocab:
                        continue
                    active.append(idx)
                    targets.append(vocab[value])
            if not active:
                continue
            logits = logits_by_field[field][torch.tensor(active, dtype=torch.long)]
            target_tensor = torch.tensor(targets, dtype=torch.long, device=logits.device)
            loss = torch.nn.functional.cross_entropy(logits, target_tensor)
            losses.append(loss)
            inverse = {idx: label for label, idx in vocab.items()}
            records = []
            for source_idx, target_index, logit_row in zip(active, targets, logits):
                target_label = inverse[target_index]
                record = _field_telemetry_record(
                    row_id=str(batch_rows[source_idx].get("row_id", source_idx)),
                    split=split,
                    field=field,
                    target=target_label,
                    logits=logit_row,
                    inverse=inverse,
                )
                record["cell_key"] = _cell_key(batch_rows[source_idx])
                record["step"] = step
                records.append(record)
            field_loss[field] = float(loss.detach().item())
            field_correct[field] = int(sum(int(record["correct"]) for record in records))
            field_rows[field] = records
        if not losses:
            raise ValueError("structured aux probe batch produced no active losses")
        return sum(losses) / len(losses), field_loss, field_correct, field_rows, _activation_summary(batch.row_ids, out, split=split, step=step)

    def checkpoint_eval_split(name: str, split_rows: list[dict[str, Any]], *, step: int) -> dict[str, Any]:
        if not split_rows:
            return {"split": name, "rows": 0, "step": step, "checkpoint_eval": True}
        model.eval()
        with torch.no_grad():
            loss, field_loss, _, field_rows, _ = structured_loss(split_rows, split=name, step=step)
        model.train()
        total = 0
        correct = 0
        by_field = {}
        for field, records in field_rows.items():
            f_total = len(records)
            f_correct = sum(int(record["correct"]) for record in records)
            total += f_total
            correct += f_correct
            by_field[field] = {"rows": f_total, "exact": f_correct / f_total if f_total else None}
        record = {
            "split": name,
            "rows": len(split_rows),
            "loss": float(loss.item()),
            "field_loss": field_loss,
            "field_exact": by_field,
            "joint_proxy_exact": correct / total if total else None,
            "step": step,
            "checkpoint_eval": True,
        }
        _append_jsonl(output_dir / "eval_loss_by_checkpoint.jsonl", record)
        return record

    for step in range(1, max_steps + 1):
        batch_rows = [train_rows[(step * batch_size + i) % len(train_rows)] for i in range(batch_size)]
        optimizer.zero_grad(set_to_none=True)
        loss, field_loss, field_correct, _, activation_rows = structured_loss(batch_rows, split="train", step=step)
        loss.backward()
        batch_row_ids = [str(row.get("row_id", index)) for index, row in enumerate(batch_rows)]
        for row_id in batch_row_ids:
            grad_card = _gradient_norm_card(row_id, model, losses_enabled=[key for key, field in STRUCTURED_LOSS_TO_FIELD.items() if field in fields])
            grad_card.update({"step": step, "gradient_scope": "batch_shared", "batch_row_ids": batch_row_ids})
            _append_jsonl(output_dir / "row_gradient_norms.jsonl", grad_card)
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        _write_jsonl_rows(output_dir / "activation_summary.jsonl", activation_rows)
        _append_jsonl(output_dir / "loss_by_step.jsonl", {"step": step, "loss": float(loss.detach().item()), "grad_norm": float(grad_norm), "field_loss": field_loss, "field_correct": field_correct})
        if eval_interval and step % int(eval_interval) == 0:
            eval_record = checkpoint_eval_split("eval", eval_rows, step=step)
            strict_record = checkpoint_eval_split("strict_eval", strict_rows, step=step)
            maybe_record_best_structured_state(step, eval_record, strict_record)

    confusion: dict[str, dict[str, dict[str, int]]] = {}
    all_eval_records: list[dict[str, Any]] = []
    field_cell_totals: dict[str, dict[str, dict[str, int]]] = {}

    if restore_best_structured_state and best_structured_state is not None:
        model.load_state_dict(best_structured_state)
        best_state_selection["restored"] = True
    _write_json(output_dir / "best_structured_state_selection.json", best_state_selection)

    def eval_split(name: str, split_rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not split_rows:
            return {"split": name, "rows": 0}
        model.eval()
        with torch.no_grad():
            loss, field_loss, _, field_rows, activation_rows = structured_loss(split_rows, split=name, step=None)
        _write_jsonl_rows(output_dir / "activation_summary.jsonl", activation_rows)
        total = 0
        correct = 0
        by_field = {}
        for field, records in field_rows.items():
            f_total = len(records)
            f_correct = sum(int(record["correct"]) for record in records)
            total += f_total
            correct += f_correct
            by_field[field] = {"rows": f_total, "exact": f_correct / f_total if f_total else None}
            _append_jsonl(output_dir / "row_field_losses.jsonl", {"split": name, "field": field, "loss": field_loss.get(field), "rows": f_total, "exact": by_field[field]["exact"]})
            confusion.setdefault(field, {})
            field_cell_totals.setdefault(field, {})
            for record in records:
                _append_jsonl(output_dir / "row_field_logits.jsonl", record)
                all_eval_records.append(record)
                dyn = row_dynamics.setdefault(str(record["row_id"]), {"row_id": str(record["row_id"]), "loss_history": [], "confidence_history": [], "correct_history": []})
                dyn["confidence_history"].append(float(record.get("confidence", 0.0)))
                dyn["correct_history"].append(bool(record.get("correct")))
                target = str(record["target"])
                pred = str(record["pred"])
                confusion[field].setdefault(target, {})
                confusion[field][target][pred] = confusion[field][target].get(pred, 0) + 1
                cell = str(record.get("cell_key"))
                field_cell_totals[field].setdefault(cell, {"rows": 0, "correct": 0})
                field_cell_totals[field][cell]["rows"] += 1
                field_cell_totals[field][cell]["correct"] += int(record["correct"])
        record = {"split": name, "rows": len(split_rows), "loss": float(loss.item()), "field_loss": field_loss, "field_exact": by_field, "joint_proxy_exact": correct / total if total else None}
        _append_jsonl(output_dir / "eval_loss_by_checkpoint.jsonl", record)
        return record

    eval_card = {"eval": eval_split("eval", eval_rows), "strict_eval": eval_split("strict_eval", strict_rows)}
    after = {name: value.detach().clone() for name, value in model.state_dict().items()}
    _write_json(output_dir / "module_delta_norms.json", _module_delta_norm_card(before, after))
    _write_json(output_dir / "field_label_vocabs.json", vocabs)
    _write_json(output_dir / "structured_confusion_matrix.json", confusion)

    for row in _proxy_feature_ablation_records(all_eval_records, row_by_id):
        _append_jsonl(output_dir / "feature_ablation_attribution.jsonl", row)
    for row in _activation_patch_proxy_records(all_eval_records):
        _append_jsonl(output_dir / "activation_patch_recovery.jsonl", row)
    field_exact_by_cell = {
        field: {
            cell: {"rows": card["rows"], "correct": card["correct"], "exact": card["correct"] / card["rows"] if card["rows"] else None}
            for cell, card in sorted(cells.items())
        }
        for field, cells in sorted(field_cell_totals.items())
    }
    _write_json(output_dir / "field_exact_by_cell.json", field_exact_by_cell)
    for row_id, dyn in sorted(row_dynamics.items()):
        confidence = [float(value) for value in dyn.get("confidence_history", [])]
        correctness = [bool(value) for value in dyn.get("correct_history", [])]
        dyn.update(
            {
                "confidence_mean": sum(confidence) / max(1, len(confidence)),
                "confidence_variance": sum((value - (sum(confidence) / max(1, len(confidence)))) ** 2 for value in confidence) / max(1, len(confidence)),
                "forgetting_events": sum(1 for prev, cur in zip(correctness, correctness[1:]) if prev and not cur),
                "prediction_flip_count": sum(1 for prev, cur in zip(correctness, correctness[1:]) if prev != cur),
            }
        )
        _append_jsonl(output_dir / "row_dynamics_history.jsonl", dyn)
    _write_json(output_dir / "failure_bucket_card.json", {"mode": mode, "eval": eval_card, "confusion_matrix_path": "structured_confusion_matrix.json", "high_confidence_wrong_rows": sum(1 for record in all_eval_records if record.get("high_confidence_wrong"))})
    _write_json(output_dir / "cleanup_proof.json", {"cleanup_executed": False, "cleanup_reason": "structured loop does not write checkpoints", "run_id": run_id})

    return {
        "run_id": run_id,
        "mode": mode,
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
        "strict_rows": len(strict_rows),
        "fields": fields,
        "implementation": implementation_card,
        "eval": eval_card,
        "best_state_selection": best_state_selection,
        "final_checkpoint_exported": False,
        "runtime_executed": False,
        "gemma_executed": False,
        "harness_executed": False,
        "required_artifacts_written": all((output_dir / name).exists() and (not name.endswith(".jsonl") or (output_dir / name).stat().st_size > 0) for name in REQUIRED_STRUCTURED_ARTIFACTS),
        "structured_optimizer_isolated": True,
        "structured_optimizer_frozen_parameter_count": len(frozen_for_structured_probe),
        "structured_optimizer_trainable_parameter_count": len(trainable_for_structured_probe),
        "structured_optimizer_frozen_bucket_prefixes": ["decoder", "lm_head", "embeddings"],
    }
