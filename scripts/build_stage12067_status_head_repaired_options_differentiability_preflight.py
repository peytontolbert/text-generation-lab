#!/usr/bin/env python3
"""Preflight Stage12062 status-head batches for differentiable loss."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.training_data import build_batch, load_tokenizer
from legacy_src.agentkernel_lite.training_loop import (
    _bounded_choice_aux_loss,
    _bounded_choice_contrastive_margin_loss,
    _bounded_choice_same_role_listwise_loss,
    _bounded_choice_verifier_value_listwise_loss,
    _bounded_decoder_train_batch_rows,
    _bounded_choice_transition_candidate_feature_dim,
    _build_probe_model,
    _decoder_ce_loss,
    _load_runtime_model_bundle,
    _move_manifest_batch,
    _preferred_execution_device,
)

ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
NAME = "stage12067_status_head_repaired_options_differentiability_preflight"
OUT = ART / NAME
SUMMARY = OUT / "status_head_repaired_options_differentiability_preflight.json"
MANIFEST = ART / "stage12066_transition_status_head_ablation_repaired_options_request/transition_status_head_ablation_repaired_options_manifest.jsonl"
INIT_RUNTIME = ART / "stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"

SOURCE = "encoder_option_retrieval_transition_status_head"
BATCH_SIZE = 8
MAX_STEPS = 384
MAX_ENCODER_TOKENS = 768
MAX_DECODER_TOKENS = 16
AUX_WEIGHT = 3.0
CONTRAST_WEIGHT = 0.0
SAME_ROLE_WEIGHT = 0.0
VERIFIER_VALUE_WEIGHT = 0.0
DECODER_WEIGHT = 0.0
EOS_WEIGHT = 1.0


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def split_of(row: dict[str, Any]) -> str:
    return str(row.get("split") or row.get("package_split") or "")


def attach_status_head(model: torch.nn.Module) -> str:
    if not hasattr(model, "bounded_choice_transition_status_head"):
        input_dim = _bounded_choice_transition_candidate_feature_dim(model)
        hidden_dim = int(getattr(getattr(model, "config", None), "retrieval_head_dim", 0) or 0) or int(getattr(getattr(model, "config", None), "d_model", 0) or 0)
        if input_dim <= 0 or hidden_dim <= 0:
            raise RuntimeError("invalid status head dimensions")
        model.bounded_choice_transition_status_head = nn.Sequential(
            nn.Linear(input_dim, hidden_dim, bias=True),
            nn.SiLU(),
            nn.Linear(hidden_dim, 1, bias=True),
        ).to(next(model.parameters()).device)
    for name, parameter in model.named_parameters():
        parameter.requires_grad_(name.startswith("bounded_choice_transition_status_head."))
    trainable = [name for name, parameter in model.named_parameters() if parameter.requires_grad]
    if not trainable:
        raise RuntimeError("no trainable status-head parameters")
    return "bounded_choice_transition_status_head"


def component_card(name: str, loss: torch.Tensor | None, card: dict[str, Any] | None, weight: float) -> dict[str, Any]:
    return {
        "name": name,
        "present": loss is not None,
        "weight": weight,
        "requires_grad": bool(getattr(loss, "requires_grad", False)) if loss is not None else False,
        "value": float(loss.detach().item()) if loss is not None else None,
        "card": card,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SUM.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8"))))
    rows = read_jsonl(MANIFEST)
    train_rows = [row for row in rows if split_of(row) == "train"]
    tokenizer = load_tokenizer(TOKENIZER_JSON, TOKENIZER_CONFIG)
    model, implementation_card = _build_probe_model(
        "transformer",
        vocab_size=tokenizer.vocab_size,
        probe_scale="target_100m",
        model_config=MODEL_CONFIG,
    )
    implementation_card = dict(implementation_card)
    implementation_card["runtime_initialization"] = _load_runtime_model_bundle(INIT_RUNTIME, model=model)
    device = _preferred_execution_device()
    model.to(device)
    trainable_prefix = attach_status_head(model)
    model.train()

    bad_batches: list[dict[str, Any]] = []
    checked_batches: list[dict[str, Any]] = []
    for step in range(1, MAX_STEPS + 1):
        batch_rows = _bounded_decoder_train_batch_rows(train_rows, step=step, batch_size=BATCH_SIZE, sampler="cyclic")
        batch = build_batch(batch_rows, max_encoder_tokens=MAX_ENCODER_TOKENS, max_decoder_tokens=MAX_DECODER_TOKENS, tokenizer=tokenizer)
        batch = _move_manifest_batch(batch, device)
        out = model(batch.input_ids, batch.decoder_input_ids)
        decoder = _decoder_ce_loss(model, out["decoder_logits"], batch.labels, batch.loss_mask.get("decoder_ce"), eos_id=int(getattr(tokenizer, "eos_id", 2)), eos_loss_weight=EOS_WEIGHT)
        aux, aux_card = _bounded_choice_aux_loss(
            first_step_logits=out["decoder_logits"][:, 0, :] if "decoder_logits" in out else None,
            pooled=out.get("pooled"), rows=batch_rows, tokenizer=tokenizer, source=SOURCE, model=model, untied_head=getattr(model, "bounded_choice_probe_head", None),
        )
        contrast, contrast_card = _bounded_choice_contrastive_margin_loss(
            first_step_logits=out["decoder_logits"][:, 0, :] if "decoder_logits" in out else None,
            pooled=out.get("pooled"), rows=batch_rows, tokenizer=tokenizer, source=SOURCE, model=model, untied_head=getattr(model, "bounded_choice_probe_head", None), margin=0.05,
        )
        verifier_value, verifier_value_card = _bounded_choice_verifier_value_listwise_loss(
            first_step_logits=out["decoder_logits"][:, 0, :] if "decoder_logits" in out else None,
            pooled=out.get("pooled"), rows=batch_rows, tokenizer=tokenizer, source=SOURCE, model=model, untied_head=getattr(model, "bounded_choice_probe_head", None),
        )
        same_role, same_role_card = _bounded_choice_same_role_listwise_loss(
            first_step_logits=out["decoder_logits"][:, 0, :] if "decoder_logits" in out else None,
            pooled=out.get("pooled"), rows=batch_rows, tokenizer=tokenizer, source=SOURCE, model=model, untied_head=getattr(model, "bounded_choice_probe_head", None),
        )
        loss = decoder * DECODER_WEIGHT
        if aux is not None and AUX_WEIGHT > 0:
            loss = loss + (AUX_WEIGHT * aux)
        if contrast is not None and CONTRAST_WEIGHT > 0:
            loss = loss + (CONTRAST_WEIGHT * contrast)
        if verifier_value is not None and VERIFIER_VALUE_WEIGHT > 0:
            loss = loss + (VERIFIER_VALUE_WEIGHT * verifier_value)
        if same_role is not None and SAME_ROLE_WEIGHT > 0:
            loss = loss + (SAME_ROLE_WEIGHT * same_role)
        components = [
            component_card("decoder_ce", decoder, None, DECODER_WEIGHT),
            component_card("bounded_choice_aux", aux, aux_card, AUX_WEIGHT),
            component_card("bounded_choice_contrast", contrast, contrast_card, CONTRAST_WEIGHT),
            component_card("bounded_choice_verifier_value_listwise", verifier_value, verifier_value_card, VERIFIER_VALUE_WEIGHT),
            component_card("bounded_choice_same_role_listwise", same_role, same_role_card, SAME_ROLE_WEIGHT),
        ]
        row_ids = [str(row.get("row_id")) for row in batch_rows]
        card = {
            "step": step,
            "loss_requires_grad": bool(getattr(loss, "requires_grad", False)),
            "loss_value": float(loss.detach().item()),
            "row_ids": row_ids,
            "components": components,
        }
        checked_batches.append({
            "step": step,
            "loss_requires_grad": card["loss_requires_grad"],
            "aux_applicable_rows": (aux_card or {}).get("applicable_rows"),
            "aux_skipped_rows": (aux_card or {}).get("skipped_rows"),
            "row_ids": row_ids,
        })
        if not card["loss_requires_grad"]:
            bad_batches.append(card)
            break
    passed = not bad_batches
    payload = {
        "stage": 12067,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "decision": "status_head_batches_differentiable" if passed else "status_head_batches_have_non_differentiable_loss",
        "passed": passed,
        "device": str(device),
        "source": SOURCE,
        "trainable_prefix": trainable_prefix,
        "checked_steps": len(checked_batches),
        "planned_steps": MAX_STEPS,
        "first_bad_batch": bad_batches[0] if bad_batches else None,
        "checked_batch_tail": checked_batches[-5:],
        "row_counts": {"train_rows": len(train_rows), "all_rows": len(rows)},
        "interpretation": "Stage12068 repaired-options status-head ablation can be run because all planned batches have a differentiable weighted loss." if passed else "Stage12068 should not run until this repaired-options preflight passes; repair remaining bad batches first.",
        "source_artifacts": {"manifest": rel(MANIFEST), "init_runtime": rel(INIT_RUNTIME), "failed_stage12064": "runs/summaries/stage12064_transition_status_head_ablation_failure_decision.json", "repaired_request": "runs/summaries/stage12066_transition_status_head_ablation_repaired_options_request.json"},
        "outputs": {"summary": rel(SUMMARY), "summary_mirror": f"runs/summaries/{NAME}.json"},
    }
    write_json(SUMMARY, payload)
    write_json(SUM / f"{NAME}.json", payload)
    print(json.dumps({"passed": passed, "checked_steps": len(checked_batches), "first_bad_step": bad_batches[0]["step"] if bad_batches else None}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
