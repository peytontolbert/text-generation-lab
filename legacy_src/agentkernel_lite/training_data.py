from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

import torch


class ByteTokenizer:
    """UTF-8 byte tokenizer used by fallback recovery probes."""

    tokenizer_kind = "byte_fallback_v1"
    pad_id = 0
    bos_id = 1
    eos_id = 2
    offset = 3
    vocab_size = 259

    def encode(self, text: str, *, max_length: int) -> list[int]:
        body = [b + self.offset for b in text.encode("utf-8", errors="replace")]
        ids = [self.bos_id] + body[: max(0, max_length - 2)] + [self.eos_id]
        return ids[:max_length]

    def decode(self, ids: list[int]) -> str:
        values = []
        for idx in ids:
            if idx in {self.pad_id, self.bos_id, self.eos_id}:
                continue
            if idx >= self.offset:
                values.append(idx - self.offset)
        return bytes(values).decode("utf-8", errors="replace")


class AgentKernelBPETokenizer:
    """Thin wrapper around recovered AgentKernel byte-level BPE tokenizer JSON."""

    def __init__(self, tokenizer_json: Path, tokenizer_config: Path | None = None) -> None:
        from tokenizers import Tokenizer

        self.tokenizer_json = Path(tokenizer_json)
        self.tokenizer_config = Path(tokenizer_config) if tokenizer_config else None
        self._tokenizer = Tokenizer.from_file(str(self.tokenizer_json))
        config: dict[str, Any] = {}
        if self.tokenizer_config and self.tokenizer_config.is_file():
            config = json.loads(self.tokenizer_config.read_text(encoding="utf-8"))
        model = self._tokenizer.get_vocab()
        self.vocab_size = int(config.get("vocab_size") or len(model))
        self.pad_id = int(config.get("pad_token_id", 0))
        self.bos_id = int(config.get("bos_token_id", 1))
        self.eos_id = int(config.get("eos_token_id", 2))
        self.tokenizer_kind = str(config.get("tokenizer_kind") or "agentkernel_bytelevel_bpe_v1")

    def encode(self, text: str, *, max_length: int) -> list[int]:
        encoded = self._tokenizer.encode(text, add_special_tokens=True).ids
        if not encoded or encoded[0] != self.bos_id:
            encoded = [self.bos_id] + encoded
        if encoded[-1] != self.eos_id:
            encoded = encoded + [self.eos_id]
        return encoded[:max_length]

    def decode(self, ids: list[int]) -> str:
        return self._tokenizer.decode([int(idx) for idx in ids if int(idx) != self.pad_id])


def load_tokenizer(tokenizer_json: Path | None = None, tokenizer_config: Path | None = None) -> ByteTokenizer | AgentKernelBPETokenizer:
    if tokenizer_json is None:
        return ByteTokenizer()
    return AgentKernelBPETokenizer(tokenizer_json, tokenizer_config)


def _append_structured(parts: list[str], prefix: str, payload: dict[str, Any]) -> None:
    for key in sorted(payload):
        if key.endswith("_id") or key in {"row_id", "target", "decoder_text", "source_ref", "path"}:
            continue
        value = payload[key]
        if isinstance(value, (str, int, float, bool)):
            parts.append(f"{prefix}.{key}={value}")
        elif isinstance(value, list):
            scalar_values = [item for item in value if isinstance(item, (str, int, float, bool))]
            if scalar_values:
                parts.append(f"{prefix}.{key}.count={len(scalar_values)}")
                for item in scalar_values[:12]:
                    parts.append(f"{prefix}.{key}.item={item}")


def _row_text(row: dict[str, Any]) -> str:
    state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
    parts: list[str] = []
    if row.get("language_family"):
        parts.append(f"language={row.get('language_family')}")
    if row.get("route"):
        parts.append(f"route={row.get('route')}")
    if row.get("objective_family"):
        parts.append(f"objective={row.get('objective_family')}")
    if row.get("surface"):
        parts.append(f"surface={row.get('surface')}")
    _append_structured(parts, "state", state)
    model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
    _append_structured(parts, "model", model_input)
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    if query.get("query_kind"):
        parts.append(f"query.kind={query.get('query_kind')}")
    _append_structured(parts, "query", query.get("features") if isinstance(query.get("features"), dict) else {})
    graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    if nodes:
        node_type_counts: dict[str, int] = {}
        feature_counts: dict[str, int] = {}
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = str(node.get("node_type", "unknown"))
            node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1
            features = node.get("features") if isinstance(node.get("features"), dict) else {}
            for key, value in features.items():
                feature_key = f"{node_type}.{key}.{value}"
                feature_counts[feature_key] = feature_counts.get(feature_key, 0) + 1
        for key, value in sorted(node_type_counts.items()):
            parts.append(f"graph.node_type_count.{key}={value}")
        for key, value in sorted(feature_counts.items())[:80]:
            parts.append(f"graph.node_feature_count.{key}={value}")
    if edges:
        edge_type_counts: dict[str, int] = {}
        for edge in edges:
            if isinstance(edge, dict):
                edge_type = str(edge.get("edge_type", "unknown"))
                edge_type_counts[edge_type] = edge_type_counts.get(edge_type, 0) + 1
        for key, value in sorted(edge_type_counts.items()):
            parts.append(f"graph.edge_type_count.{key}={value}")
    return " | ".join(parts)


def _target_text(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    if isinstance(target.get("decoder_text"), str):
        return target["decoder_text"]
    if isinstance(row.get("decoder_text"), str):
        return row["decoder_text"]
    return str(target.get("target_ref") or row.get("target_ref") or target.get("label") or "")


@dataclass
class ManifestBatch:
    input_ids: torch.Tensor
    decoder_input_ids: torch.Tensor
    labels: torch.Tensor
    loss_mask: dict[str, torch.Tensor]
    row_ids: list[str]


def _pad(seqs: list[list[int]], *, pad_id: int) -> torch.Tensor:
    max_len = max(len(seq) for seq in seqs) if seqs else 1
    out = torch.full((len(seqs), max_len), pad_id, dtype=torch.long)
    for i, seq in enumerate(seqs):
        out[i, : len(seq)] = torch.tensor(seq, dtype=torch.long)
    return out


def build_batch(rows: list[dict[str, Any]], *, max_encoder_tokens: int = 256, max_decoder_tokens: int = 256, tokenizer: ByteTokenizer | AgentKernelBPETokenizer | None = None) -> ManifestBatch:
    tok = tokenizer or ByteTokenizer()
    enc = [tok.encode(_row_text(row), max_length=max_encoder_tokens) for row in rows]
    tgt = [tok.encode(_target_text(row), max_length=max_decoder_tokens) for row in rows]
    labels = _pad(tgt, pad_id=tok.pad_id)
    decoder_input_ids = labels[:, :-1].contiguous()
    shifted_labels = labels[:, 1:].contiguous()
    masks: dict[str, torch.Tensor] = {}
    loss_keys = set()
    for row in rows:
        if isinstance(row.get("loss_mask"), dict):
            loss_keys.update(row["loss_mask"].keys())
    for key in sorted(loss_keys):
        masks[key] = torch.tensor([bool(row.get("loss_mask", {}).get(key, False)) for row in rows], dtype=torch.bool)
    return ManifestBatch(
        input_ids=_pad(enc, pad_id=tok.pad_id),
        decoder_input_ids=decoder_input_ids,
        labels=shifted_labels,
        loss_mask=masks,
        row_ids=[str(row.get("row_id", i)) for i, row in enumerate(rows)],
    )
