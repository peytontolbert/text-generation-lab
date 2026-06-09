#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Iterator

import torch
import torch.nn.functional as F


_RETRIEVAL_KEY_HASH_BUCKETS = 512
_RETRIEVAL_KEY_HASH_SLOTS = 8
_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS = _RETRIEVAL_KEY_HASH_BUCKETS
_ACTIVE_RETRIEVAL_KEY_HASH_SLOTS = _RETRIEVAL_KEY_HASH_SLOTS
_ACTIVE_RETRIEVAL_KEY_HASH_MODE = "kv"
_ACTIVE_RETRIEVAL_AUX_KEY_HASH_BUCKETS = 0
_ACTIVE_RETRIEVAL_AUX_KEY_HASH_SLOTS = 0
_ACTIVE_RETRIEVAL_AUX_KEY_HASH_MODE = "kv"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _install_paths(repo_root: Path) -> None:
    model_stack = repo_root / "other_repos" / "model-stack"
    for path in (repo_root, model_stack):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)


def _materialize_lazy_modules(model: torch.nn.Module) -> None:
    for module in model.modules():
        ensure_self_attn = getattr(module, "_ensure_self_attn", None)
        if callable(ensure_self_attn):
            ensure_self_attn()


def _iter_rows(path: Path) -> Iterator[dict[str, Any]]:
    if path.is_dir() and any(path.glob("*.parquet")):
        import pyarrow.parquet as pq

        columns = ["retrieval_query_text", "retrieval_doc_text", "task_type", "source_id", "operation", "expected_content"]
        for shard in sorted(path.glob("*.parquet")):
            parquet_file = pq.ParquetFile(shard)
            available = set(parquet_file.schema_arrow.names)
            read_columns = [column for column in columns if column in available]
            for batch in parquet_file.iter_batches(batch_size=2048, columns=read_columns):
                yield from batch.to_pylist()
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _load_tokenizer(manifest: dict[str, Any]):
    tokenizer_module_path = _repo_root() / "scripts" / "sample_agentkernel_lite_encdec.py"
    spec = importlib.util.spec_from_file_location("sample_agentkernel_lite_encdec", tokenizer_module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load sampler script: {tokenizer_module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ByteTokenizer = module.ByteTokenizer
    HuggingFaceTokenizer = module.HuggingFaceTokenizer
    TokenizersBpe = module.TokenizersBpe

    tokenizer_kind = str(manifest.get("tokenizer_kind", "byte") or "byte").lower()
    tokenizer_dir = Path(str(manifest.get("tokenizer_dir", "") or ""))
    if tokenizer_kind == "byte":
        return ByteTokenizer()
    if tokenizer_kind == "agentkernel-bpe":
        return TokenizersBpe(tokenizer_dir / "tokenizer.json")
    return HuggingFaceTokenizer(tokenizer_dir, str(manifest.get("tokenizer_name", "")))


def _token_count(tokenizer, text: str, *, max_tokens: int) -> int:
    try:
        encoded = tokenizer.encode(str(text), max_length=int(max_tokens))
    except TypeError:
        encoded = tokenizer(str(text), max_length=int(max_tokens), padding=False, truncation=True).get("input_ids", [])
    return min(len(encoded), int(max_tokens))


def _dataset_token_stats(
    *,
    tokenizer,
    dataset_manifest: dict[str, Any],
    max_query_tokens: int,
    max_doc_tokens: int,
) -> dict[str, float | int]:
    train_path = Path(str(dataset_manifest.get("train_dataset_path", "") or ""))
    eval_path = Path(str(dataset_manifest.get("eval_dataset_path", "") or ""))
    train_rows = 0
    train_tokens = 0
    if train_path.exists():
        for row in _iter_rows(train_path):
            query = str(row.get("retrieval_query_text", "") or "")
            doc = str(row.get("retrieval_doc_text", "") or "")
            if not query or not doc:
                continue
            train_rows += 1
            train_tokens += _token_count(tokenizer, query, max_tokens=int(max_query_tokens))
            train_tokens += _token_count(tokenizer, doc, max_tokens=int(max_doc_tokens))

    eval_rows = 0
    eval_docs: set[str] = set()
    if eval_path.exists():
        for row in _iter_rows(eval_path):
            query = str(row.get("retrieval_query_text", "") or "")
            doc = str(row.get("retrieval_doc_text", "") or "")
            if not query or not doc:
                continue
            eval_rows += 1
            eval_docs.add(doc.strip())

    unique_eval_cards = len(eval_docs)
    return {
        "train_rows": int(train_rows),
        "train_retrieval_tokens": int(train_tokens),
        "avg_train_retrieval_tokens_per_pair": float(train_tokens) / float(train_rows) if train_rows else 0.0,
        "eval_rows": int(eval_rows),
        "unique_eval_answer_cards": int(unique_eval_cards),
        "bits_per_eval_card_choice": math.log2(max(2, unique_eval_cards)),
    }


def _verified_density_metrics(
    *,
    model_manifest: dict[str, Any],
    tokenizer,
    dataset_manifest: dict[str, Any],
    max_query_tokens: int,
    max_doc_tokens: int,
    evaluated_pairs: int,
    top1_accuracy: float | None,
    answer_top1_accuracy: float | None,
    train_batch_size_override: int = 0,
    total_train_steps_override: int = 0,
) -> dict[str, Any]:
    training = dict(model_manifest.get("training_summary", {}) or {})
    params = int(model_manifest.get("parameter_count") or training.get("parameter_count") or 0)
    completed_steps = int(total_train_steps_override or training.get("completed_steps") or training.get("max_steps") or 0)
    token_stats = _dataset_token_stats(
        tokenizer=tokenizer,
        dataset_manifest=dataset_manifest,
        max_query_tokens=int(max_query_tokens),
        max_doc_tokens=int(max_doc_tokens),
    )
    bits_per_choice = float(token_stats["bits_per_eval_card_choice"])
    exact_correct = float(top1_accuracy or 0.0) * float(evaluated_pairs)
    answer_correct = float(answer_top1_accuracy or 0.0) * float(evaluated_pairs)
    exact_verified_bits = exact_correct * bits_per_choice
    answer_verified_bits = answer_correct * bits_per_choice
    train_batch_size = int(
        train_batch_size_override
        or training.get("batch_size")
        or training.get("train_batch_size")
        or training.get("effective_train_batch_size")
        or 0
    )
    train_tokens_est = float(completed_steps) * float(train_batch_size) * float(token_stats["avg_train_retrieval_tokens_per_pair"])
    return {
        "metric_definition": (
            "verified_bits = correct_eval_retrievals * log2(unique_eval_answer_cards); "
            "answer_verified_bits uses exact-card match plus parsed expected-content equivalence "
            "(for example member_true/member_false against member=...)."
        ),
        "parameter_count": int(params),
        "completed_steps": int(completed_steps),
        "train_batch_size_assumption": int(train_batch_size),
        "estimated_training_retrieval_tokens": float(train_tokens_est),
        "token_stats": token_stats,
        "exact_verified_bits": float(exact_verified_bits),
        "exact_verified_bits_per_million_params": exact_verified_bits / (params / 1_000_000) if params else 0.0,
        "exact_verified_bits_per_training_token": exact_verified_bits / train_tokens_est if train_tokens_est else 0.0,
        "answer_verified_bits": float(answer_verified_bits),
        "answer_verified_bits_per_million_params": answer_verified_bits / (params / 1_000_000) if params else 0.0,
        "answer_verified_bits_per_training_token": answer_verified_bits / train_tokens_est if train_tokens_est else 0.0,
    }


def _load_model(bundle_dir: Path, *, repo_root: Path, device: torch.device):
    _install_paths(repo_root)
    from runtime.checkpoint import load_config, load_pretrained
    from runtime.seq2seq import EncoderDecoderLM

    manifest = json.loads((bundle_dir / "agentkernel_lite_encdec_manifest.json").read_text(encoding="utf-8"))
    model_dir = Path(str(manifest["model_dir"]))
    config = load_config(str(model_dir))
    global _ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS, _ACTIVE_RETRIEVAL_KEY_HASH_SLOTS, _ACTIVE_RETRIEVAL_KEY_HASH_MODE
    global _ACTIVE_RETRIEVAL_AUX_KEY_HASH_BUCKETS, _ACTIVE_RETRIEVAL_AUX_KEY_HASH_SLOTS
    global _ACTIVE_RETRIEVAL_AUX_KEY_HASH_MODE
    _ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS = int(
        getattr(config, "retrieval_key_hash_buckets", 0) or _RETRIEVAL_KEY_HASH_BUCKETS
    )
    _ACTIVE_RETRIEVAL_KEY_HASH_SLOTS = int(
        getattr(config, "retrieval_key_hash_slots", 0) or _RETRIEVAL_KEY_HASH_SLOTS
    )
    _ACTIVE_RETRIEVAL_KEY_HASH_MODE = str(getattr(config, "retrieval_key_hash_mode", "kv") or "kv")
    _ACTIVE_RETRIEVAL_AUX_KEY_HASH_BUCKETS = int(getattr(config, "retrieval_aux_key_hash_buckets", 0) or 0)
    _ACTIVE_RETRIEVAL_AUX_KEY_HASH_SLOTS = int(getattr(config, "retrieval_aux_key_hash_slots", 0) or 0)
    _ACTIVE_RETRIEVAL_AUX_KEY_HASH_MODE = str(getattr(config, "retrieval_aux_key_hash_mode", "kv") or "kv")
    tokenizer = _load_tokenizer(manifest)
    model = EncoderDecoderLM(config, tie_embeddings=True, vocab_size=int(config.vocab_size))
    _materialize_lazy_modules(model)
    load_pretrained(model, str(model_dir), strict=True)
    model.to(device).eval()
    return model, tokenizer, manifest


def _encode_batch(tokenizer, texts: list[str], *, max_tokens: int, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    pad_id = int(getattr(tokenizer, "pad_token_id", 0) or 0)
    ids: list[list[int]] = []
    masks: list[list[int]] = []
    for text in texts:
        row = tokenizer.encode(text, max_length=max_tokens)
        row = row[:max_tokens]
        mask = [1] * len(row)
        while len(row) < max_tokens:
            row.append(pad_id)
            mask.append(0)
        ids.append(row)
        masks.append(mask)
    return (
        torch.tensor(ids, dtype=torch.long, device=device),
        torch.tensor(masks, dtype=torch.long, device=device),
    )


def _stable_bucket_id(raw: str, *, buckets: int = _RETRIEVAL_KEY_HASH_BUCKETS) -> int:
    if buckets <= 1:
        return 0
    import hashlib

    digest = hashlib.blake2b(str(raw).encode("utf-8"), digest_size=8).digest()
    return 1 + (int.from_bytes(digest, byteorder="big", signed=False) % (int(buckets) - 1))


def _retrieval_key_hash_ids_for(
    text: str,
    *,
    device: torch.device,
    buckets: int,
    slots: int,
    mode: str,
) -> torch.Tensor:
    ids: list[int] = []
    buckets = int(buckets or _RETRIEVAL_KEY_HASH_BUCKETS)
    slots = int(slots or _RETRIEVAL_KEY_HASH_SLOTS)
    pairs = [(str(key), str(value)) for key, value in _KEY_VALUE_RE.findall(str(text or ""))]
    mode = str(mode or "kv").strip().lower()
    if mode in {"gsel_parts", "gsel-parts"}:
        values = {key: value for key, value in pairs}
        gsel = values.get("gsel", "")
        parts = gsel.split("|")
        if len(parts) >= 4:
            _kind, domain, field, entity = parts[:4]
            for key, value in (
                ("gsel", gsel),
                ("gsel_full", gsel),
                ("domain", domain),
                ("domain_value", domain),
                ("field", field),
                ("field_value", field),
                ("entity", entity),
                ("entity_value", entity),
            ):
                if value:
                    ids.append(_stable_bucket_id(f"{key}={value}", buckets=buckets))
                    if len(ids) >= slots:
                        break
            ids = ids[:slots]
            while len(ids) < slots:
                ids.append(0)
            return torch.tensor(ids, dtype=torch.long, device=device)
    for key, value in pairs:
        if key == "op" or not value:
            continue
        ids.append(_stable_bucket_id(f"{key}={value}", buckets=buckets))
        ids.append(_stable_bucket_id(value, buckets=buckets))
        if len(ids) >= slots:
            break
    ids = ids[:slots]
    while len(ids) < slots:
        ids.append(0)
    return torch.tensor(ids, dtype=torch.long, device=device)


def _retrieval_key_hash_ids(text: str, *, device: torch.device) -> torch.Tensor:
    return _retrieval_key_hash_ids_for(
        text,
        device=device,
        buckets=int(_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS or _RETRIEVAL_KEY_HASH_BUCKETS),
        slots=int(_ACTIVE_RETRIEVAL_KEY_HASH_SLOTS or _RETRIEVAL_KEY_HASH_SLOTS),
        mode=str(_ACTIVE_RETRIEVAL_KEY_HASH_MODE or "kv"),
    )


def _retrieval_combined_key_hash_ids(text: str, *, device: torch.device) -> torch.Tensor:
    primary = _retrieval_key_hash_ids(text, device=device)
    aux_buckets = int(_ACTIVE_RETRIEVAL_AUX_KEY_HASH_BUCKETS or 0)
    aux_slots = int(_ACTIVE_RETRIEVAL_AUX_KEY_HASH_SLOTS or 0)
    if aux_buckets > 1 and aux_slots > 0:
        aux = _retrieval_key_hash_ids_for(
            text,
            device=device,
            buckets=aux_buckets,
            slots=aux_slots,
            mode=str(_ACTIVE_RETRIEVAL_AUX_KEY_HASH_MODE or "kv"),
        )
        aux = aux[: primary.shape[0]]
        if aux.shape[0] < primary.shape[0]:
            aux = torch.cat([aux, torch.zeros(primary.shape[0] - aux.shape[0], dtype=torch.long, device=device)])
        return torch.stack([primary, aux], dim=0)
    return primary


def _encode_key_batch(texts: list[str], *, device: torch.device) -> torch.Tensor:
    return torch.stack([_retrieval_combined_key_hash_ids(text, device=device) for text in texts], dim=0)


def _mean_pool(hidden: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    weights = mask.to(dtype=hidden.dtype, device=hidden.device).unsqueeze(-1)
    return (hidden * weights).sum(dim=1) / weights.sum(dim=1).clamp_min(1.0)


def _embed(model, tokenizer, texts: list[str], *, max_tokens: int, device: torch.device) -> torch.Tensor:
    ids, mask = _encode_batch(tokenizer, texts, max_tokens=max_tokens, device=device)
    if hasattr(model, "retrieval_query_embedding") and hasattr(model, "retrieval_doc_embedding"):
        # Caller decides whether these are query or doc strings. For retrieval
        # quality we need both asymmetric heads, so this helper remains a
        # fallback for old bundles.
        hidden = model.encode(ids, mask)
        return F.normalize(_mean_pool(hidden, mask), dim=-1)
    hidden = model.encode(ids, mask)
    return F.normalize(_mean_pool(hidden, mask), dim=-1)


def _embed_query(model, tokenizer, texts: list[str], *, max_tokens: int, device: torch.device) -> torch.Tensor:
    ids, mask = _encode_batch(tokenizer, texts, max_tokens=max_tokens, device=device)
    if hasattr(model, "retrieval_query_embedding"):
        keys = _encode_key_batch(texts, device=device)
        aux_keys = None
        if keys.ndim >= 3:
            aux_keys = keys[:, 1, :]
            keys = keys[:, 0, :]
        try:
            return model.retrieval_query_embedding(ids, mask, keys, aux_keys)
        except TypeError:
            try:
                return model.retrieval_query_embedding(ids, mask, keys)
            except TypeError:
                return model.retrieval_query_embedding(ids, mask)
    hidden = model.encode(ids, mask)
    return F.normalize(_mean_pool(hidden, mask), dim=-1)


def _embed_doc(model, tokenizer, texts: list[str], *, max_tokens: int, device: torch.device) -> torch.Tensor:
    ids, mask = _encode_batch(tokenizer, texts, max_tokens=max_tokens, device=device)
    if hasattr(model, "retrieval_doc_embedding"):
        keys = _encode_key_batch(texts, device=device)
        aux_keys = None
        if keys.ndim >= 3:
            aux_keys = keys[:, 1, :]
            keys = keys[:, 0, :]
        try:
            return model.retrieval_doc_embedding(ids, mask, keys, aux_keys)
        except TypeError:
            try:
                return model.retrieval_doc_embedding(ids, mask, keys)
            except TypeError:
                return model.retrieval_doc_embedding(ids, mask)
    hidden = model.encode(ids, mask)
    return F.normalize(_mean_pool(hidden, mask), dim=-1)


def _gsel_parts(text: str) -> tuple[str, str, str, str] | None:
    values = {key: value for key, value in _KEY_VALUE_RE.findall(str(text or ""))}
    parts = str(values.get("gsel", "") or "").split("|")
    if len(parts) < 4:
        return None
    return str(parts[0]), str(parts[1]), str(parts[2]), str(parts[3])


def _non_answer_text_entities(text: str) -> list[str]:
    entities: set[str] = set()
    for key, value in _KEY_VALUE_RE.findall(str(text or "")):
        if str(key) == "answer":
            continue
        entities.update(_ENTITY_RE.findall(str(value or "")))
    if not entities:
        entities.update(_ENTITY_RE.findall(str(text or "")))
    return sorted(entities)


def _ordered_non_answer_text_entities(text: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for key, value in _KEY_VALUE_RE.findall(str(text or "")):
        if str(key) == "answer":
            continue
        for entity in _ENTITY_RE.findall(str(value or "")):
            if entity not in seen:
                seen.add(entity)
                ordered.append(entity)
    if not ordered:
        for entity in _ENTITY_RE.findall(str(text or "")):
            if entity not in seen:
                seen.add(entity)
                ordered.append(entity)
    return ordered


def _factor_key_hash_ids_for(text: str, *, mode: str, device: torch.device) -> torch.Tensor:
    mode = str(mode or "model").strip().lower()
    if mode == "model":
        mode = str(_ACTIVE_RETRIEVAL_KEY_HASH_MODE or "kv").strip().lower()
    if mode in {"kv", "gsel_parts", "gsel-parts"}:
        return _retrieval_key_hash_ids_for(
            text,
            device=device,
            buckets=int(_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS or _RETRIEVAL_KEY_HASH_BUCKETS),
            slots=int(_ACTIVE_RETRIEVAL_KEY_HASH_SLOTS or _RETRIEVAL_KEY_HASH_SLOTS),
            mode=mode,
        )

    ids: list[int] = []
    text_entities = sorted(set(_ENTITY_RE.findall(str(text or ""))))
    text_apis = sorted(set(_API_RE.findall(str(text or ""))))
    text_values = sorted(set(_VALUE_RE.findall(str(text or ""))))
    text_math_assignments = sorted(set(_MATH_ASSIGN_RE.findall(str(text or ""))))
    parts = _gsel_parts(text)
    if mode in {"text_entity", "entity_text"}:
        for entity in text_entities:
            ids.append(_stable_bucket_id(f"text_entity={entity}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            ids.append(_stable_bucket_id(entity, buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
    elif mode in {
        "text_domain_field_entity",
        "domain_field_text_entity",
        "text_domain_field_nonanswer_entity",
        "text_domain_field_subject_entity",
        "text_domain_field_nonanswer_entity_pair",
        "text_gsel_axes_nonanswer_entity_pair",
        "text_multi_axis_nonanswer_entity_pair",
        "text_compose_role_entity_exact",
        "text_routed_multi_axis_compose_exact",
        "text_routed_multi_axis_compose_procedure",
        "text_domain_relation_field_nonanswer_entity",
        "text_domain_field_semantic",
    }:
        values = {key: value for key, value in _KEY_VALUE_RE.findall(str(text or ""))}
        gsel = str(values.get("gsel", "") or "")
        gsel_parts = gsel.split("|")
        if mode == "text_domain_relation_field_nonanswer_entity" and len(gsel_parts) >= 4:
            ids.append(_stable_bucket_id(f"domain={gsel_parts[1]}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            ids.append(_stable_bucket_id(f"relation={gsel_parts[2]}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            ids.append(_stable_bucket_id(f"field={gsel_parts[3]}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            ids.append(_stable_bucket_id(gsel_parts[3], buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
        elif len(gsel_parts) >= 3:
            ids.append(_stable_bucket_id(f"domain={gsel_parts[1]}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            ids.append(_stable_bucket_id(f"field={gsel_parts[2]}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
        entities = (
            _non_answer_text_entities(text)
            if mode in {
                "text_domain_field_nonanswer_entity",
                "text_domain_field_subject_entity",
                "text_domain_field_nonanswer_entity_pair",
                "text_gsel_axes_nonanswer_entity_pair",
                "text_multi_axis_nonanswer_entity_pair",
                "text_routed_multi_axis_compose_exact",
                "text_routed_multi_axis_compose_procedure",
                "text_domain_relation_field_nonanswer_entity",
            }
            else text_entities
        )
        for entity in entities:
            ids.append(_stable_bucket_id(f"text_entity={entity}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            ids.append(_stable_bucket_id(entity, buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            if mode == "text_domain_field_nonanswer_entity_pair" and len(gsel_parts) >= 3:
                ids.append(
                    _stable_bucket_id(
                        f"binding={gsel_parts[1]}|{gsel_parts[2]}|{entity}",
                        buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS,
                    )
                )
            if mode == "text_gsel_axes_nonanswer_entity_pair" and len(gsel_parts) >= 3:
                axes = "|".join(part for part in gsel_parts[1:] if part)
                if axes:
                    ids.append(
                        _stable_bucket_id(
                            f"binding_axes={axes}|{entity}",
                            buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS,
                        )
                    )
            if mode in {
                "text_multi_axis_nonanswer_entity_pair",
                "text_routed_multi_axis_compose_exact",
                "text_routed_multi_axis_compose_procedure",
            } and len(gsel_parts) >= 3:
                axes = "|".join(part for part in gsel_parts[1:] if part)
                if axes:
                    ids.append(_stable_bucket_id(f"binding_axes={axes}|{entity}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
                    ids.append(_stable_bucket_id(f"binding_kind_axes={gsel_parts[0]}|{axes}|{entity}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
                ids.append(
                    _stable_bucket_id(
                        f"binding={gsel_parts[1]}|{gsel_parts[2]}|{entity}",
                        buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS,
                    )
                )
        if mode in {
            "text_compose_role_entity_exact",
            "text_routed_multi_axis_compose_exact",
            "text_routed_multi_axis_compose_procedure",
        } and len(gsel_parts) >= 4 and str(gsel_parts[0]).startswith("compose2"):
            ordered_entities = _ordered_non_answer_text_entities(text)
            entity = ordered_entities[0] if ordered_entities else ""
            domain, relation, field = gsel_parts[1], gsel_parts[2], gsel_parts[3]
            ids = [
                _stable_bucket_id(f"compose_domain={domain}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS),
                _stable_bucket_id(f"compose_relation={relation}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS),
                _stable_bucket_id(f"compose_field={field}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS),
            ]
            if entity:
                ids.extend(
                    [
                        _stable_bucket_id(f"compose_entity={entity}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS),
                        _stable_bucket_id(f"compose_binding={domain}|{relation}|{field}|{entity}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS),
                        _stable_bucket_id(f"compose_role_binding={relation}|{field}|{entity}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS),
                        _stable_bucket_id(f"compose_domain_entity={domain}|{entity}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS),
                        _stable_bucket_id(f"compose_field_entity={field}|{entity}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS),
                    ]
                )
        if mode == "text_routed_multi_axis_compose_procedure" and gsel_parts and str(gsel_parts[0]) in {
            "abstractionsgrp",
            "apigrp",
            "mathgrp",
        }:
            values = {key: value for key, value in _KEY_VALUE_RE.findall(str(text or ""))}
            op = str(values.get("op", "") or "")
            family = str(values.get("family", "") or "")
            domain = str(values.get("domain", "") or "")
            axes = "|".join(part for part in gsel_parts if part)
            ids = [
                _stable_bucket_id(f"proc_kind={gsel_parts[0]}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS),
                _stable_bucket_id(f"proc_axes={axes}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS),
            ]
            for label, value in (("op", op), ("family", family), ("domain", domain)):
                if value:
                    ids.append(_stable_bucket_id(f"proc_{label}={value}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            for api in text_apis:
                ids.append(_stable_bucket_id(f"proc_api={api}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            for assignment in text_math_assignments:
                ids.append(_stable_bucket_id(f"proc_math={assignment}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            answer_value = str(values.get("answer", "") or "")
            stop = {
                "ak_op_schema",
                "ak_op_math_identity",
                "ak_op_code_api_semantics",
                "answer",
                "collision_key",
                "compute",
                "domain",
                "family",
                "for",
                "gsel",
                "mod",
                "op",
                "query",
                "statement",
            }
            for token in re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\b|\b\d+\b", str(text or "").lower()):
                if token in stop or token == answer_value.lower() or re.fullmatch(r"[a-z]+_v\d+", token):
                    continue
                if token.startswith("gdom_") or token.startswith("api_") or len(token) >= 2:
                    ids.append(_stable_bucket_id(f"proc_token={token}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
        if mode == "text_domain_field_semantic":
            for api in text_apis:
                ids.append(_stable_bucket_id(f"text_api={api}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
                ids.append(_stable_bucket_id(api, buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            for assignment in text_math_assignments:
                ids.append(_stable_bucket_id(f"text_math={assignment}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
                ids.append(_stable_bucket_id(assignment, buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            for value in text_values:
                ids.append(_stable_bucket_id(f"text_value={value}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
    if parts is not None:
        values = {key: value for key, value in _KEY_VALUE_RE.findall(str(text or ""))}
        gsel = str(values.get("gsel", "") or "")
        all_parts = gsel.split("|")
        kind, domain, field, entity = parts
        if mode in {"gsel_full", "full"}:
            ids.append(_stable_bucket_id(f"gsel={gsel}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
        elif mode in {"gsel_all_parts", "all_parts"}:
            if gsel:
                ids.append(_stable_bucket_id(f"gsel={gsel}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            for index, value in enumerate(all_parts):
                if value:
                    ids.append(_stable_bucket_id(f"gsel_part_{index}={value}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
                    ids.append(_stable_bucket_id(value, buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
        elif mode in {"gsel_no_full_parts", "no_full_parts"}:
            for index, value in enumerate(all_parts):
                if value:
                    ids.append(_stable_bucket_id(f"gsel_part_{index}={value}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
                    ids.append(_stable_bucket_id(value, buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
        elif mode in {"gsel_entity", "entity"}:
            ids.append(_stable_bucket_id(f"entity={entity}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            ids.append(_stable_bucket_id(entity, buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
        elif mode in {"gsel_domain_field", "domain_field"}:
            ids.append(_stable_bucket_id(f"domain={domain}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            ids.append(_stable_bucket_id(f"field={field}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
        elif mode in {"gsel_domain_field_entity", "domain_field_entity"}:
            ids.append(_stable_bucket_id(f"domain={domain}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            ids.append(_stable_bucket_id(f"field={field}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            ids.append(_stable_bucket_id(f"entity={entity}", buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
            ids.append(_stable_bucket_id(entity, buckets=_ACTIVE_RETRIEVAL_KEY_HASH_BUCKETS))
    slots = int(_ACTIVE_RETRIEVAL_KEY_HASH_SLOTS or _RETRIEVAL_KEY_HASH_SLOTS)
    ids = ids[:slots]
    while len(ids) < slots:
        ids.append(0)
    return torch.tensor(ids, dtype=torch.long, device=device)


def _key_factor_embeddings(
    model,
    texts: list[str],
    *,
    mode: str,
    device: torch.device,
) -> torch.Tensor | None:
    table = getattr(model, "retrieval_key_hash_embed", None)
    if table is None:
        return None
    key_ids = torch.stack([_factor_key_hash_ids_for(text, mode=mode, device=device) for text in texts], dim=0)
    key_ids = key_ids.to(device=device)
    key_mask = key_ids.ne(0).to(dtype=table.weight.dtype, device=device).unsqueeze(-1)
    if int(key_mask.sum().detach().cpu().item()) <= 0:
        return None
    vectors = table(key_ids)
    pooled = (vectors * key_mask).sum(dim=1) / key_mask.sum(dim=1).clamp_min(1.0)
    return F.normalize(pooled.float(), dim=-1)


def _add_key_factor_scores(
    scores: torch.Tensor,
    model,
    queries: list[str],
    docs: list[str],
    *,
    mode: str,
    weight: float,
    device: torch.device,
) -> torch.Tensor:
    if float(weight) == 0.0:
        return scores
    query_factors = _key_factor_embeddings(model, queries, mode=mode, device=device)
    doc_factors = _key_factor_embeddings(model, docs, mode=mode, device=device)
    if query_factors is None or doc_factors is None:
        return scores
    return scores + (float(weight) * (query_factors @ doc_factors.transpose(0, 1))).to(dtype=scores.dtype)


_KEY_VALUE_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*?)=([^\s;]+)")
_ENTITY_RE = re.compile(r"\b(gdom_\d+_e\d+)\b")
_API_RE = re.compile(r"\b(api_\d+)\b")
_VALUE_RE = re.compile(r"\b([a-z]+_v\d+)\b")
_MATH_ASSIGN_RE = re.compile(r"\b([ab]=\d+)\b")
_PRIMARY_STRUCTURED_KEY_FIELDS = ("bind_key", "lookup_key", "fact_key", "rule_key", "composition_key")


def _structured_key_values(text: str) -> dict[str, str]:
    return {str(key): str(value) for key, value in _KEY_VALUE_RE.findall(str(text or ""))}


def _doc_matches_expected_content(expected_content: str, predicted_doc: str) -> bool:
    expected = str(expected_content or "").strip()
    doc = str(predicted_doc or "")
    if not expected:
        return False
    if expected in doc:
        return True
    expected_lower = expected.lower()
    doc_keys = _structured_key_values(doc)
    if expected_lower in {"member_true", "member_false"}:
        return doc_keys.get("member", "").lower() == expected_lower.rsplit("_", 1)[-1]
    if expected_lower.startswith("count_"):
        count = expected_lower.split("_", 1)[1]
        return doc_keys.get("count", "").lower() == count
    if expected_lower.startswith("answer_"):
        return doc_keys.get("answer", "").lower() == expected_lower.split("_", 1)[1]
    return False


def _structured_key_matches(query: str, doc_keys: list[dict[str, str]]) -> list[bool]:
    query_keys = {
        key: value
        for key, value in _structured_key_values(query).items()
        if key not in {"op"} and value
    }
    primary_keys = [key for key in _PRIMARY_STRUCTURED_KEY_FIELDS if key in query_keys]
    match_fields = primary_keys if primary_keys else sorted(query_keys)
    matches: list[bool] = []
    for keys in doc_keys:
        matches.append(bool(match_fields) and all(keys.get(key) == query_keys[key] for key in match_fields))
    return matches


def _structured_key_rerank_scores(
    queries: list[str],
    docs: list[str],
    *,
    device: torch.device,
    dtype: torch.dtype,
    match_bonus: float,
    mismatch_penalty: float,
    hard_filter: bool = False,
    hard_filter_penalty: float = 1.0e6,
) -> torch.Tensor:
    doc_keys = [_structured_key_values(doc) for doc in docs]
    rows: list[list[float]] = []
    for query in queries:
        query_keys = {
            key: value
            for key, value in _structured_key_values(query).items()
            if key not in {"op"} and value
        }
        all_match = _structured_key_matches(query, doc_keys)
        has_exact_key_match = any(all_match)
        row: list[float] = []
        normalizer = max(1, len(query_keys))
        for index, keys in enumerate(doc_keys):
            adjustment = 0.0
            if bool(hard_filter) and has_exact_key_match and not all_match[index]:
                adjustment -= float(hard_filter_penalty)
            for key, value in query_keys.items():
                if key not in keys:
                    continue
                if keys[key] == value:
                    adjustment += float(match_bonus) / normalizer
                else:
                    adjustment -= float(mismatch_penalty) / normalizer
            row.append(adjustment)
        rows.append(row)
    return torch.tensor(rows, dtype=dtype, device=device)


def _new_hard_filter_stats() -> dict[str, int]:
    return {
        "queries_with_exact_key_candidate": 0,
        "queries_without_exact_key_candidate": 0,
        "queries_with_multiple_exact_key_candidates": 0,
        "exact_key_candidate_total": 0,
        "exact_key_candidate_max": 0,
        "correct_in_exact_key_candidates": 0,
        "correct_missing_from_exact_key_candidates": 0,
        "neural_top1_masked_by_hard_filter": 0,
        "top1_changed_by_hard_filter": 0,
        "top1_corrected_by_hard_filter": 0,
        "top1_damaged_by_hard_filter": 0,
    }


def _update_hard_filter_stats(
    stats: dict[str, int],
    *,
    query: str,
    docs: list[str],
    doc_keys: list[dict[str, str]] | None = None,
    candidate_allowed: list[bool] | None = None,
    pre_filter_top1: int,
    post_filter_top1: int,
    correct: set[int],
) -> None:
    keys = doc_keys if doc_keys is not None else [_structured_key_values(doc) for doc in docs]
    matches = _structured_key_matches(query, keys)
    if candidate_allowed is not None:
        matches = [bool(match) and bool(candidate_allowed[index]) for index, match in enumerate(matches)]
    candidate_count = sum(1 for match in matches if match)
    stats["exact_key_candidate_total"] += int(candidate_count)
    stats["exact_key_candidate_max"] = max(int(stats.get("exact_key_candidate_max", 0)), int(candidate_count))
    if candidate_count:
        stats["queries_with_exact_key_candidate"] += 1
        if candidate_count > 1:
            stats["queries_with_multiple_exact_key_candidates"] += 1
        if any(int(candidate) in correct for candidate, match in enumerate(matches) if match):
            stats["correct_in_exact_key_candidates"] += 1
        else:
            stats["correct_missing_from_exact_key_candidates"] += 1
    else:
        stats["queries_without_exact_key_candidate"] += 1
        return
    if 0 <= int(pre_filter_top1) < len(matches) and not matches[int(pre_filter_top1)]:
        stats["neural_top1_masked_by_hard_filter"] += 1
    if int(pre_filter_top1) != int(post_filter_top1):
        stats["top1_changed_by_hard_filter"] += 1
        pre_correct = int(pre_filter_top1) in correct
        post_correct = int(post_filter_top1) in correct
        if post_correct and not pre_correct:
            stats["top1_corrected_by_hard_filter"] += 1
        elif pre_correct and not post_correct:
            stats["top1_damaged_by_hard_filter"] += 1


def _normalize_structured_key_args(args: argparse.Namespace) -> None:
    if bool(getattr(args, "structured_key_hard_filter", 0)):
        setattr(args, "structured_key_rerank", 1)


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    _normalize_structured_key_args(args)
    repo_root = Path(args.repo_root).resolve()
    device = torch.device(str(args.device))
    model, tokenizer, manifest = _load_model(Path(args.bundle_dir).resolve(), repo_root=repo_root, device=device)
    if str(args.dataset_manifest).strip():
        dataset_manifest = json.loads(Path(args.dataset_manifest).read_text(encoding="utf-8"))
    else:
        dataset_manifest = json.loads(Path(str(manifest["dataset_manifest_path"])).read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    split = str(args.dataset_split).strip().lower()
    if split == "train":
        dataset_path = Path(str(dataset_manifest["train_dataset_path"]))
    elif split == "eval":
        dataset_path = Path(str(dataset_manifest["eval_dataset_path"]))
    else:
        raise ValueError(f"unknown dataset split: {args.dataset_split}")
    for row in _iter_rows(dataset_path):
        query = str(row.get("retrieval_query_text", "") or "").strip()
        doc = str(row.get("retrieval_doc_text", "") or "").strip()
        if query and doc:
            rows.append(row)
            if int(args.limit) > 0 and len(rows) >= int(args.limit):
                break
    if not rows:
        return {"bundle_dir": str(args.bundle_dir), "retrieval_pairs": 0}

    if bool(args.full_corpus):
        return _evaluate_full_corpus(args, model=model, tokenizer=tokenizer, rows=rows, split=split, dataset_manifest=dataset_manifest, model_manifest=manifest, device=device)

    top1 = 0
    answer_top1 = 0
    mrr_total = 0.0
    batches = 0
    evaluated = 0
    by_operation: dict[str, dict[str, Any]] = {}
    details: list[dict[str, Any]] = []
    hard_filter_stats = _new_hard_filter_stats()
    with torch.no_grad():
        for offset in range(0, len(rows), int(args.batch_size)):
            batch = rows[offset : offset + int(args.batch_size)]
            if len(batch) < 2:
                continue
            queries = [str(row["retrieval_query_text"]) for row in batch]
            docs = [str(row["retrieval_doc_text"]) for row in batch]
            query_embeddings = _embed_query(
                model,
                tokenizer,
                queries,
                max_tokens=int(args.max_query_tokens),
                device=device,
            )
            doc_embeddings = _embed_doc(
                model,
                tokenizer,
                docs,
                max_tokens=int(args.max_doc_tokens),
                device=device,
            )
            scores = query_embeddings @ doc_embeddings.transpose(0, 1)
            scores = _add_key_factor_scores(
                scores,
                model,
                queries,
                docs,
                mode=str(args.key_factor_mode),
                weight=float(args.key_factor_weight),
                device=device,
            )
            if bool(args.operation_gated):
                query_ops = [str(row.get("operation", "") or "") for row in batch]
                op_mask = torch.tensor(
                    [[query_op == doc_op for doc_op in query_ops] for query_op in query_ops],
                    dtype=torch.bool,
                    device=scores.device,
                )
                scores = scores.masked_fill(~op_mask, torch.finfo(scores.dtype).min)
            pre_structured_scores = scores
            if bool(args.structured_key_rerank):
                scores = scores + _structured_key_rerank_scores(
                    queries,
                    docs,
                    device=scores.device,
                    dtype=scores.dtype,
                    match_bonus=float(args.structured_key_match_bonus),
                    mismatch_penalty=float(args.structured_key_mismatch_penalty),
                    hard_filter=bool(args.structured_key_hard_filter),
                    hard_filter_penalty=float(args.structured_key_hard_filter_penalty),
                )
            ranks = torch.argsort(scores, dim=1, descending=True)
            pre_structured_ranks = torch.argsort(pre_structured_scores, dim=1, descending=True)
            docs_normalized = [str(doc).strip() for doc in docs]
            doc_keys = [_structured_key_values(doc) for doc in docs] if bool(args.structured_key_hard_filter) else None
            for index in range(scores.shape[0]):
                row = batch[index]
                operation = str(row.get("operation", "") or "")
                if not operation:
                    query_text = str(row.get("retrieval_query_text", "") or "")
                    operation = query_text.split(" ", 1)[0].split("=", 1)[1] if query_text.startswith("op=") else "unknown"
                op_stats = by_operation.setdefault(operation, {"evaluated_pairs": 0, "top1": 0, "mrr_total": 0.0})
                correct = {
                    candidate
                    for candidate, doc in enumerate(docs_normalized)
                    if doc == docs_normalized[index]
                }
                predicted_index = int(ranks[index, 0].detach().cpu().item())
                if bool(args.structured_key_rerank) and bool(args.structured_key_hard_filter):
                    query_operation = str(row.get("operation", "") or "")
                    allowed = [query_operation == str(candidate.get("operation", "") or "") for candidate in batch] if bool(args.operation_gated) else None
                    _update_hard_filter_stats(
                        hard_filter_stats,
                        query=str(row.get("retrieval_query_text", "") or ""),
                        docs=docs,
                        doc_keys=doc_keys,
                        candidate_allowed=allowed,
                        pre_filter_top1=int(pre_structured_ranks[index, 0].detach().cpu().item()),
                        post_filter_top1=predicted_index,
                        correct=correct,
                    )
                is_top1 = predicted_index in correct
                if is_top1:
                    top1 += 1
                    op_stats["top1"] += 1
                expected_content = str(row.get("expected_content", "") or "")
                predicted_doc = str(batch[predicted_index].get("retrieval_doc_text", "") or "")
                is_answer_top1 = bool(is_top1) or _doc_matches_expected_content(expected_content, predicted_doc)
                if is_answer_top1:
                    answer_top1 += 1
                    op_stats["answer_top1"] = int(op_stats.get("answer_top1", 0)) + 1
                rank = min(
                    int(position) + 1
                    for position, candidate in enumerate(ranks[index].detach().cpu().tolist())
                    if int(candidate) in correct
                )
                op_stats["evaluated_pairs"] += 1
                op_stats["mrr_total"] += 1.0 / rank
                if str(args.output_details_jsonl).strip():
                    predicted_row = batch[predicted_index]
                    score_row = scores[index].detach().float().cpu()
                    correct_score = max(float(score_row[candidate].item()) for candidate in correct)
                    predicted_score = float(score_row[predicted_index].item())
                    details.append(
                        {
                            "batch_offset": int(offset),
                            "index_in_batch": int(index),
                            "operation": operation,
                            "source_id": str(row.get("source_id", "") or ""),
                            "query": str(row.get("retrieval_query_text", "") or ""),
                            "expected_doc": str(row.get("retrieval_doc_text", "") or ""),
                            "expected_content": str(row.get("expected_content", "") or ""),
                            "predicted_source_id": str(predicted_row.get("source_id", "") or ""),
                            "predicted_doc": str(predicted_row.get("retrieval_doc_text", "") or ""),
                            "rank": int(rank),
                            "top1": bool(is_top1),
                            "answer_top1": bool(is_answer_top1),
                            "correct_score": correct_score,
                            "predicted_score": predicted_score,
                            "score_margin": correct_score - predicted_score,
                        }
                    )
                mrr_total += 1.0 / rank
            evaluated += int(scores.shape[0])
            batches += 1
    by_operation_out = {
        operation: {
            "evaluated_pairs": int(stats["evaluated_pairs"]),
            "top1_accuracy": float(stats["top1"]) / float(stats["evaluated_pairs"]) if stats["evaluated_pairs"] else None,
            "answer_top1_accuracy": float(stats.get("answer_top1", 0)) / float(stats["evaluated_pairs"]) if stats["evaluated_pairs"] else None,
            "mean_reciprocal_rank": float(stats["mrr_total"]) / float(stats["evaluated_pairs"]) if stats["evaluated_pairs"] else None,
        }
        for operation, stats in sorted(by_operation.items())
    }
    if str(args.output_details_jsonl).strip():
        details_path = Path(str(args.output_details_jsonl))
        with details_path.open("w", encoding="utf-8") as handle:
            for detail in details:
                handle.write(json.dumps(detail, sort_keys=True) + "\n")
    top1_accuracy = top1 / evaluated if evaluated else None
    answer_top1_accuracy = answer_top1 / evaluated if evaluated else None
    return {
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "dataset_manifest": str(Path(str(dataset_manifest["manifest_path"])).resolve())
        if dataset_manifest.get("manifest_path")
        else "",
        "dataset_split": split,
        "retrieval_pairs": len(rows),
        "evaluated_pairs": evaluated,
        "batches": batches,
        "batch_size": int(args.batch_size),
        "top1_accuracy": top1_accuracy,
        "answer_top1_accuracy": answer_top1_accuracy,
        "mean_reciprocal_rank": mrr_total / evaluated if evaluated else None,
        "verified_density": _verified_density_metrics(
            model_manifest=manifest,
            tokenizer=tokenizer,
            dataset_manifest=dataset_manifest,
            max_query_tokens=int(args.max_query_tokens),
            max_doc_tokens=int(args.max_doc_tokens),
            evaluated_pairs=int(evaluated),
            top1_accuracy=top1_accuracy,
            answer_top1_accuracy=answer_top1_accuracy,
            train_batch_size_override=int(args.density_train_batch_size),
            total_train_steps_override=int(args.density_total_train_steps),
        ),
        "by_operation": by_operation_out,
        "duplicate_doc_text_counts_as_correct": True,
        "operation_gated": bool(args.operation_gated),
        "key_factor_mode": str(args.key_factor_mode),
        "key_factor_weight": float(args.key_factor_weight),
        "structured_key_rerank": bool(args.structured_key_rerank),
        "structured_key_hard_filter": bool(args.structured_key_hard_filter),
        "structured_key_hard_filter_penalty": float(args.structured_key_hard_filter_penalty),
        "structured_key_hard_filter_stats": hard_filter_stats
        if bool(args.structured_key_rerank) and bool(args.structured_key_hard_filter)
        else {},
        "full_corpus": False,
    }


def _evaluate_full_corpus(
    args: argparse.Namespace,
    *,
    model: torch.nn.Module,
    tokenizer,
    rows: list[dict[str, Any]],
    split: str,
    dataset_manifest: dict[str, Any],
    model_manifest: dict[str, Any],
    device: torch.device,
) -> dict[str, Any]:
    docs = [str(row["retrieval_doc_text"]) for row in rows]
    docs_normalized = [doc.strip() for doc in docs]
    doc_ops = [str(row.get("operation", "") or "") for row in rows]
    doc_embeddings_parts: list[torch.Tensor] = []
    with torch.no_grad():
        for offset in range(0, len(docs), int(args.batch_size)):
            doc_embeddings_parts.append(
                _embed_doc(
                    model,
                    tokenizer,
                    docs[offset : offset + int(args.batch_size)],
                    max_tokens=int(args.max_doc_tokens),
                    device=device,
                )
            )
        doc_embeddings = torch.cat(doc_embeddings_parts, dim=0)
        doc_keys = [_structured_key_values(doc) for doc in docs] if bool(args.structured_key_hard_filter) else None

        top1 = 0
        answer_top1 = 0
        mrr_total = 0.0
        evaluated = 0
        batches = 0
        by_operation: dict[str, dict[str, Any]] = {}
        details: list[dict[str, Any]] = []
        hard_filter_stats = _new_hard_filter_stats()
        for offset in range(0, len(rows), int(args.batch_size)):
            batch = rows[offset : offset + int(args.batch_size)]
            queries = [str(row["retrieval_query_text"]) for row in batch]
            query_embeddings = _embed_query(
                model,
                tokenizer,
                queries,
                max_tokens=int(args.max_query_tokens),
                device=device,
            )
            scores = query_embeddings @ doc_embeddings.transpose(0, 1)
            scores = _add_key_factor_scores(
                scores,
                model,
                queries,
                docs,
                mode=str(args.key_factor_mode),
                weight=float(args.key_factor_weight),
                device=device,
            )
            if bool(args.operation_gated):
                query_ops = [str(row.get("operation", "") or "") for row in batch]
                op_mask = torch.tensor(
                    [[query_op == doc_op for doc_op in doc_ops] for query_op in query_ops],
                    dtype=torch.bool,
                    device=scores.device,
                )
                scores = scores.masked_fill(~op_mask, torch.finfo(scores.dtype).min)
            pre_structured_scores = scores
            if bool(args.structured_key_rerank):
                scores = scores + _structured_key_rerank_scores(
                    queries,
                    docs,
                    device=scores.device,
                    dtype=scores.dtype,
                    match_bonus=float(args.structured_key_match_bonus),
                    mismatch_penalty=float(args.structured_key_mismatch_penalty),
                    hard_filter=bool(args.structured_key_hard_filter),
                    hard_filter_penalty=float(args.structured_key_hard_filter_penalty),
                )
            ranks = torch.argsort(scores, dim=1, descending=True)
            pre_structured_ranks = torch.argsort(pre_structured_scores, dim=1, descending=True)
            for index in range(scores.shape[0]):
                row = batch[index]
                operation = str(row.get("operation", "") or "")
                if not operation:
                    query_text = str(row.get("retrieval_query_text", "") or "")
                    operation = query_text.split(" ", 1)[0].split("=", 1)[1] if query_text.startswith("op=") else "unknown"
                op_stats = by_operation.setdefault(operation, {"evaluated_pairs": 0, "top1": 0, "mrr_total": 0.0})
                expected_doc = str(row.get("retrieval_doc_text", "") or "").strip()
                correct = {candidate for candidate, doc in enumerate(docs_normalized) if doc == expected_doc}
                predicted_index = int(ranks[index, 0].detach().cpu().item())
                if bool(args.structured_key_rerank) and bool(args.structured_key_hard_filter):
                    query_operation = str(row.get("operation", "") or "")
                    allowed = [query_operation == doc_op for doc_op in doc_ops] if bool(args.operation_gated) else None
                    _update_hard_filter_stats(
                        hard_filter_stats,
                        query=str(row.get("retrieval_query_text", "") or ""),
                        docs=docs,
                        doc_keys=doc_keys,
                        candidate_allowed=allowed,
                        pre_filter_top1=int(pre_structured_ranks[index, 0].detach().cpu().item()),
                        post_filter_top1=predicted_index,
                        correct=correct,
                    )
                is_top1 = predicted_index in correct
                if is_top1:
                    top1 += 1
                    op_stats["top1"] += 1
                expected_content = str(row.get("expected_content", "") or "")
                predicted_doc = str(rows[predicted_index].get("retrieval_doc_text", "") or "")
                is_answer_top1 = bool(is_top1) or _doc_matches_expected_content(expected_content, predicted_doc)
                if is_answer_top1:
                    answer_top1 += 1
                    op_stats["answer_top1"] = int(op_stats.get("answer_top1", 0)) + 1
                rank = min(
                    int(position) + 1
                    for position, candidate in enumerate(ranks[index].detach().cpu().tolist())
                    if int(candidate) in correct
                )
                op_stats["evaluated_pairs"] += 1
                op_stats["mrr_total"] += 1.0 / rank
                if str(args.output_details_jsonl).strip():
                    predicted_row = rows[predicted_index]
                    score_row = scores[index].detach().float().cpu()
                    correct_score = max(float(score_row[candidate].item()) for candidate in correct)
                    predicted_score = float(score_row[predicted_index].item())
                    details.append(
                        {
                            "batch_offset": int(offset),
                            "index_in_batch": int(index),
                            "operation": operation,
                            "source_id": str(row.get("source_id", "") or ""),
                            "query": str(row.get("retrieval_query_text", "") or ""),
                            "expected_doc": str(row.get("retrieval_doc_text", "") or ""),
                            "expected_content": str(row.get("expected_content", "") or ""),
                            "predicted_source_id": str(predicted_row.get("source_id", "") or ""),
                            "predicted_doc": str(predicted_row.get("retrieval_doc_text", "") or ""),
                            "rank": int(rank),
                            "top1": bool(is_top1),
                            "answer_top1": bool(is_answer_top1),
                            "correct_score": correct_score,
                            "predicted_score": predicted_score,
                            "score_margin": correct_score - predicted_score,
                        }
                    )
                mrr_total += 1.0 / rank
            evaluated += int(scores.shape[0])
            batches += 1

    by_operation_out = {
        operation: {
            "evaluated_pairs": int(stats["evaluated_pairs"]),
            "top1_accuracy": float(stats["top1"]) / float(stats["evaluated_pairs"]) if stats["evaluated_pairs"] else None,
            "answer_top1_accuracy": float(stats.get("answer_top1", 0)) / float(stats["evaluated_pairs"]) if stats["evaluated_pairs"] else None,
            "mean_reciprocal_rank": float(stats["mrr_total"]) / float(stats["evaluated_pairs"]) if stats["evaluated_pairs"] else None,
        }
        for operation, stats in sorted(by_operation.items())
    }
    if str(args.output_details_jsonl).strip():
        details_path = Path(str(args.output_details_jsonl))
        with details_path.open("w", encoding="utf-8") as handle:
            for detail in details:
                handle.write(json.dumps(detail, sort_keys=True) + "\n")
    top1_accuracy = top1 / evaluated if evaluated else None
    answer_top1_accuracy = answer_top1 / evaluated if evaluated else None
    return {
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "dataset_manifest": str(Path(str(dataset_manifest["manifest_path"])).resolve())
        if dataset_manifest.get("manifest_path")
        else "",
        "dataset_split": split,
        "retrieval_pairs": len(rows),
        "evaluated_pairs": evaluated,
        "batches": batches,
        "batch_size": int(args.batch_size),
        "top1_accuracy": top1_accuracy,
        "answer_top1_accuracy": answer_top1_accuracy,
        "mean_reciprocal_rank": mrr_total / evaluated if evaluated else None,
        "verified_density": _verified_density_metrics(
            model_manifest=model_manifest,
            tokenizer=tokenizer,
            dataset_manifest=dataset_manifest,
            max_query_tokens=int(args.max_query_tokens),
            max_doc_tokens=int(args.max_doc_tokens),
            evaluated_pairs=int(evaluated),
            top1_accuracy=top1_accuracy,
            answer_top1_accuracy=answer_top1_accuracy,
            train_batch_size_override=int(args.density_train_batch_size),
            total_train_steps_override=int(args.density_total_train_steps),
        ),
        "by_operation": by_operation_out,
        "duplicate_doc_text_counts_as_correct": True,
        "operation_gated": bool(args.operation_gated),
        "key_factor_mode": str(args.key_factor_mode),
        "key_factor_weight": float(args.key_factor_weight),
        "structured_key_rerank": bool(args.structured_key_rerank),
        "structured_key_hard_filter": bool(args.structured_key_hard_filter),
        "structured_key_hard_filter_penalty": float(args.structured_key_hard_filter_penalty),
        "structured_key_hard_filter_stats": hard_filter_stats
        if bool(args.structured_key_rerank) and bool(args.structured_key_hard_filter)
        else {},
        "full_corpus": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--dataset-manifest", default="")
    parser.add_argument("--dataset-split", choices=("train", "eval"), default="eval")
    parser.add_argument("--repo-root", default=str(_repo_root()))
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--limit", type=int, default=1024)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-query-tokens", type=int, default=64)
    parser.add_argument("--max-doc-tokens", type=int, default=256)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-details-jsonl", default="")
    parser.add_argument("--operation-gated", type=int, default=0)
    parser.add_argument("--full-corpus", type=int, default=0)
    parser.add_argument("--structured-key-rerank", type=int, choices=(0, 1), default=0)
    parser.add_argument("--structured-key-match-bonus", type=float, default=0.05)
    parser.add_argument("--structured-key-mismatch-penalty", type=float, default=0.10)
    parser.add_argument("--structured-key-hard-filter", type=int, choices=(0, 1), default=0)
    parser.add_argument("--structured-key-hard-filter-penalty", type=float, default=1.0e6)
    parser.add_argument(
        "--key-factor-mode",
        choices=(
            "model",
            "kv",
            "gsel_parts",
            "gsel_full",
            "gsel_all_parts",
            "gsel_no_full_parts",
            "gsel_entity",
            "gsel_domain_field",
            "gsel_domain_field_entity",
            "text_entity",
            "text_domain_field_entity",
            "text_domain_field_nonanswer_entity",
            "text_domain_field_subject_entity",
            "text_domain_field_nonanswer_entity_pair",
            "text_gsel_axes_nonanswer_entity_pair",
            "text_multi_axis_nonanswer_entity_pair",
            "text_compose_role_entity_exact",
            "text_routed_multi_axis_compose_exact",
            "text_routed_multi_axis_compose_procedure",
            "text_domain_relation_field_nonanswer_entity",
            "text_domain_field_semantic",
        ),
        default="model",
    )
    parser.add_argument("--key-factor-weight", type=float, default=0.0)
    parser.add_argument("--density-train-batch-size", type=int, default=0)
    parser.add_argument("--density-total-train-steps", type=int, default=0)
    args = parser.parse_args()
    _normalize_structured_key_args(args)
    result = evaluate(args)
    if str(args.output_json).strip():
        Path(args.output_json).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
