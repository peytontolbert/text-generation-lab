from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import torch
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


def _has_internal_token(text: str) -> bool:
    markers = ["<MTC", "POLICY_", "<COPY", "INTERNAL", "decoder_control"]
    return any(marker in text for marker in markers)


def _target_text(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    return str(target.get("decoder_text") or row.get("decoder_text") or target.get("target_ref") or row.get("target_ref") or "")


def _clean_value(row: dict[str, Any], field: str) -> str | None:
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


def _build_probe_model(implementation: str, *, vocab_size: int) -> tuple[torch.nn.Module, dict[str, Any]]:
    if implementation == "scaffold":
        return AgentKernelLiteSeq2Seq(AgentKernelLiteConfig(vocab_size=vocab_size)), {
            "implementation": "scaffold",
            "model_class": "AgentKernelLiteSeq2Seq",
            "probe_scale": "gru_scaffold",
            "vocab_size": vocab_size,
        }
    if implementation == "transformer":
        from .modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq

        # Tiny execution probes verify the recovered transformer code path without
        # allocating the full 100M target. Full-size target execution remains a
        # separate authorization problem and should use the recovered target config.
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
    tokenizer_json: Path | None = None,
    tokenizer_config: Path | None = None,
) -> dict[str, Any]:
    """Run a tiny bounded decoder CE probe.

    This implementation is intentionally narrow: decoder CE only, no runtime,
    no final checkpoint export, no Gemma/harness/scoring, and no source/body
    emission. Temporary checkpoint handling is owned by the caller's cleanup
    policy; this function does not save checkpoints.
    """
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
    model, implementation_card = _build_probe_model(implementation, vocab_size=tokenizer.vocab_size)
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

    for step in range(1, max_steps + 1):
        batch_rows = [train_rows[(step * batch_size + i) % len(train_rows)] for i in range(batch_size)]
        batch = build_batch(batch_rows, max_encoder_tokens=max_encoder_tokens, max_decoder_tokens=max_decoder_tokens, tokenizer=tokenizer)
        optimizer.zero_grad(set_to_none=True)
        out = model(batch.input_ids, batch.decoder_input_ids)
        loss = model.decoder_ce_loss(out["decoder_logits"], batch.labels, batch.loss_mask.get("decoder_ce"))
        loss.backward()
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        _append_jsonl(
            output_dir / "loss_by_step.jsonl",
            {
                "step": step,
                "loss": float(loss.detach().item()),
                "grad_norm": float(grad_norm),
                "row_ids": batch.row_ids,
            },
        )

    confusion: dict[str, dict[str, dict[str, int]]] = {}

    def eval_split(name: str, split_rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not split_rows:
            return {"split": name, "rows": 0, "loss": None}
        model.eval()
        with torch.no_grad():
            batch = build_batch(split_rows, max_encoder_tokens=max_encoder_tokens, max_decoder_tokens=max_decoder_tokens, tokenizer=tokenizer)
            out = model(batch.input_ids, batch.decoder_input_ids)
            loss = model.decoder_ce_loss(out["decoder_logits"], batch.labels, batch.loss_mask.get("decoder_ce"))
        record = {"split": name, "rows": len(split_rows), "loss": float(loss.item())}
        _append_jsonl(output_dir / "eval_loss_by_checkpoint.jsonl", record)
        return record

    eval_card = {
        "eval": eval_split("eval", eval_rows),
        "strict_eval": eval_split("strict_eval", strict_rows),
    }

    after = {name: value.detach().clone() for name, value in model.state_dict().items()}
    _write_json(output_dir / "module_delta_norms.json", _module_delta_norms(before, after))

    token_rows = []
    for row in train_rows[: min(8, len(train_rows))]:
        text = _target_text(row)
        token_rows.append({"row_id": row.get("row_id"), "target_chars": len(text), "internal_token_present": _has_internal_token(text)})
    for row in token_rows:
        _append_jsonl(output_dir / "row_token_loss.jsonl", row)

    _write_json(output_dir / "eos_length_audit.json", {"rows_checked": len(token_rows), "max_decoder_tokens": max_decoder_tokens})
    _write_json(output_dir / "short_output_probe.json", {"generated_rows": 0, "short_or_junk_rate": None, "note": "generation audit not implemented in tiny CE train loop"})
    _write_json(output_dir / "repetition_probe.json", {"generated_rows": 0, "degenerate_repetition_rate": None})
    _write_json(output_dir / "internal_leak_probe.json", {"target_internal_token_rows": sum(int(r["internal_token_present"]) for r in token_rows), "generated_internal_token_rows": None})
    _write_json(output_dir / "sample_generation_audit.json", {"generated_rows": 0, "samples": [], "note": "sampling disabled for bounded CE implementation recovery"})
    _write_json(output_dir / "failure_bucket_card.json", {"failure_rows": 0, "buckets": {}})
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
        "required_artifacts_written": all((output_dir / name).exists() for name in REQUIRED_RUNTIME_ARTIFACTS),
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
    tokenizer_json: Path | None = None,
    tokenizer_config: Path | None = None,
) -> dict[str, Any]:
    """Run a tiny structured-head probe behind the trainer execution gate."""
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

    from .training_data import load_tokenizer

    tokenizer = load_tokenizer(tokenizer_json, tokenizer_config)
    model, implementation_card = _build_probe_model(implementation, vocab_size=tokenizer.vocab_size)
    for field, vocab in vocabs.items():
        head = getattr(model, "structured_heads", {}).get(field) if hasattr(model, "structured_heads") else None
        if head is None:
            raise ValueError(f"model implementation lacks structured head: {field}")
        if getattr(head, "out_features", 0) < len(vocab):
            raise ValueError(f"structured head {field} has {getattr(head, 'out_features', 0)} classes but needs {len(vocab)}")

    before = {name: value.detach().clone() for name, value in model.state_dict().items()}
    optimizer = AdamW(model.parameters(), lr=learning_rate)
    model.train()

    def structured_loss(batch_rows: list[dict[str, Any]]) -> tuple[torch.Tensor, dict[str, float], dict[str, int], dict[str, list[dict[str, Any]]]]:
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
            row_records = []
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
            pred = logits.argmax(dim=-1).detach().cpu().tolist()
            field_loss[field] = float(loss.detach().item())
            field_correct[field] = int(sum(int(p == t) for p, t in zip(pred, targets)))
            inverse = {idx: label for label, idx in vocab.items()}
            for source_idx, p, t, logit_row in zip(active, pred, targets, logits.detach().cpu()):
                sorted_logits = torch.sort(logit_row, descending=True).values
                margin = float((sorted_logits[0] - sorted_logits[1]).item()) if sorted_logits.numel() > 1 else 0.0
                row_records.append({
                    "row_id": str(batch_rows[source_idx].get("row_id", source_idx)),
                    "field": field,
                    "target": inverse[t],
                    "pred": inverse.get(p, str(p)),
                    "correct": bool(p == t),
                    "margin": margin,
                })
            field_rows[field] = row_records
        if not losses:
            raise ValueError("structured aux probe batch produced no active losses")
        return sum(losses) / len(losses), field_loss, field_correct, field_rows

    for step in range(1, max_steps + 1):
        batch_rows = [train_rows[(step * batch_size + i) % len(train_rows)] for i in range(batch_size)]
        optimizer.zero_grad(set_to_none=True)
        loss, field_loss, field_correct, _ = structured_loss(batch_rows)
        loss.backward()
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        _append_jsonl(output_dir / "loss_by_step.jsonl", {"step": step, "loss": float(loss.detach().item()), "grad_norm": float(grad_norm), "field_loss": field_loss, "field_correct": field_correct})

    confusion: dict[str, dict[str, dict[str, int]]] = {}

    def eval_split(name: str, split_rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not split_rows:
            return {"split": name, "rows": 0}
        model.eval()
        with torch.no_grad():
            loss, field_loss, _, field_rows = structured_loss(split_rows)
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
            for record in records:
                record = dict(record)
                record["split"] = name
                _append_jsonl(output_dir / "row_field_logits.jsonl", record)
                target = str(record["target"])
                pred = str(record["pred"])
                confusion[field].setdefault(target, {})
                confusion[field][target][pred] = confusion[field][target].get(pred, 0) + 1
        record = {"split": name, "rows": len(split_rows), "loss": float(loss.item()), "field_loss": field_loss, "field_exact": by_field, "joint_proxy_exact": correct / total if total else None}
        _append_jsonl(output_dir / "eval_loss_by_checkpoint.jsonl", record)
        return record

    eval_card = {"eval": eval_split("eval", eval_rows), "strict_eval": eval_split("strict_eval", strict_rows)}
    after = {name: value.detach().clone() for name, value in model.state_dict().items()}
    _write_json(output_dir / "module_delta_norms.json", _module_delta_norms(before, after))
    _write_json(output_dir / "field_label_vocabs.json", vocabs)
    _write_json(output_dir / "structured_confusion_matrix.json", confusion)
    _write_json(output_dir / "failure_bucket_card.json", {"mode": mode, "eval": eval_card, "confusion_matrix_path": "structured_confusion_matrix.json"})
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
        "final_checkpoint_exported": False,
        "runtime_executed": False,
        "gemma_executed": False,
        "harness_executed": False,
    }
