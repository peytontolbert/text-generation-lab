from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

import torch


MAX_CONTEXT_ROWS_FOR_ENCODER = 64
MAX_CONTEXT_TEXT_CHARS = 512
FORBIDDEN_MODEL_KEY_EXACT = frozenset({
    "answer", "correct", "correct_label", "decoder_text", "expected_output",
    "expected_patch", "gold", "gold_label", "label", "negative_chunk_ids",
    "observation", "patch_text", "positive_chunk_ids", "reward", "row_id",
    "state_t_plus_1", "target", "target_ref", "target_text", "verifier_result",
})
FORBIDDEN_MODEL_KEY_PREFIXES = ("answer_", "correct_", "expected_", "gold_", "observation_", "reward_")


def _assert_model_visible_key(key: str, *, prefix: str) -> None:
    normalized = str(key).strip().lower()
    if (
        normalized in FORBIDDEN_MODEL_KEY_EXACT
        or normalized.endswith("_id")
        or normalized.endswith("_ids")
        or normalized.endswith("_label")
        or normalized.startswith(FORBIDDEN_MODEL_KEY_PREFIXES)
    ):
        raise ValueError(f"forbidden model-visible field {prefix}.{key}")


def _truncate_with_eos(ids: list[int], *, bos_id: int, eos_id: int, max_length: int) -> list[int]:
    if max_length < 2:
        raise ValueError("max_length must allow both BOS and EOS")
    body = list(ids)
    if not body or body[0] != bos_id:
        body.insert(0, bos_id)
    if body[-1] == eos_id:
        body = body[:-1]
    return body[: max_length - 1] + [eos_id]


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
        return _truncate_with_eos(
            [self.bos_id] + body,
            bos_id=self.bos_id,
            eos_id=self.eos_id,
            max_length=max_length,
        )

    def untruncated_length(self, text: str) -> int:
        return len(text.encode("utf-8", errors="replace")) + 2

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
        return _truncate_with_eos(
            list(encoded),
            bos_id=self.bos_id,
            eos_id=self.eos_id,
            max_length=max_length,
        )

    def untruncated_length(self, text: str) -> int:
        return len(self._tokenizer.encode(text, add_special_tokens=True).ids)

    def decode(self, ids: list[int]) -> str:
        return self._tokenizer.decode([int(idx) for idx in ids if int(idx) != self.pad_id])


def load_tokenizer(tokenizer_json: Path | None = None, tokenizer_config: Path | None = None) -> ByteTokenizer | AgentKernelBPETokenizer:
    if tokenizer_json is None:
        return ByteTokenizer()
    return AgentKernelBPETokenizer(tokenizer_json, tokenizer_config)


def _append_structured(parts: list[str], prefix: str, payload: dict[str, Any]) -> None:
    for key in sorted(payload):
        _assert_model_visible_key(str(key), prefix=prefix)
        if key in {"source_ref", "path"}:
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


def _append_context_rows(parts: list[str], rows: Any) -> None:
    if not isinstance(rows, list) or not rows:
        return
    parts.append(f"context.rows.count={len(rows)}")
    for index, row in enumerate(rows[:MAX_CONTEXT_ROWS_FOR_ENCODER]):
        if not isinstance(row, dict):
            continue
        prefix = f"context.{index}"
        # Opaque chunk IDs are loss-side retrieval labels, never model evidence.
        for key in ("role", "source_type", "path", "token_count", "chunk_ordinal"):
            value = row.get(key)
            if isinstance(value, (str, int, float, bool)):
                parts.append(f"{prefix}.{key}={value}")
        text = row.get("text")
        if isinstance(text, str) and text:
            snippet = " ".join(text.split())[:MAX_CONTEXT_TEXT_CHARS]
            parts.append(f"{prefix}.text={snippet}")


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
    if row.get("task_type"):
        parts.append(f"task_type={row.get('task_type')}")
    if isinstance(row.get("prompt_text"), str) and row.get("prompt_text"):
        parts.append(f"prompt_text={row.get('prompt_text')}")
    if isinstance(row.get("query_text"), str) and row.get("query_text"):
        parts.append(f"query_text={row.get('query_text')}")
    if isinstance(row.get("input_text"), str) and row.get("input_text"):
        parts.append(f"input_text={row.get('input_text')}")
    if isinstance(row.get("corrupted_output"), str):
        parts.append(f"corrupted_output={row.get('corrupted_output')}")
    if isinstance(row.get("verifier_failure"), str):
        parts.append(f"verifier_failure={row.get('verifier_failure')}")
    _append_structured(parts, "state", state)
    transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    # Episode-step rows expose only pre-action state/action context to the encoder.
    # Observation, verifier/reward, and state_t_plus_1 are targets/telemetry and must stay hidden.
    episode_state = transition.get("state_t") if isinstance(transition.get("state_t"), dict) else {}
    episode_action = transition.get("action_t") if isinstance(transition.get("action_t"), dict) else {}
    _append_structured(parts, "episode.state", episode_state)
    _append_structured(parts, "episode.action", episode_action)
    model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
    _append_structured(parts, "model", model_input)
    # Preserve task-closure evidence exactly in compiler order. The compiler/ranker
    # is responsible for placing local files, tests, traces, and graph evidence first.
    _append_context_rows(parts, row.get("context_rows"))
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
                _assert_model_visible_key(str(key), prefix=f"graph.node.{node_type}.features")
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
    if isinstance(row.get("target_text"), str):
        return row["target_text"]
    return str(target.get("target_ref") or row.get("target_ref") or target.get("label") or "")


def _foundational_row_text(row: dict[str, Any]) -> str:
    """Render only the source-backed masked code supplied as model evidence."""
    value = row.get("input_text")
    if not isinstance(value, str) or not value:
        raise ValueError("foundational row requires non-empty input_text")
    return value


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


def build_batch(rows: list[dict[str, Any]], *, max_encoder_tokens: int = 2048, max_decoder_tokens: int = 256, tokenizer: ByteTokenizer | AgentKernelBPETokenizer | None = None, foundational_code_ce: bool = False) -> ManifestBatch:
    tok = tokenizer or ByteTokenizer()
    renderer = _foundational_row_text if foundational_code_ce else _row_text
    enc = [tok.encode(renderer(row), max_length=max_encoder_tokens) for row in rows]
    tgt = []
    for index, row in enumerate(rows):
        target_text = _target_text(row)
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        generative_target = bool(loss_mask.get("decoder_ce") or loss_mask.get("denoise_ce"))
        if generative_target and not target_text.strip():
            raise ValueError(f"row {row.get('row_id', index)} has an empty generative target")
        target_ids = tok.encode(target_text, max_length=max_decoder_tokens + 1)
        if generative_target and len(target_ids) > max_decoder_tokens:
            raise ValueError(
                f"row {row.get('row_id', index)} target exceeds max_decoder_tokens={max_decoder_tokens}"
            )
        tgt.append(target_ids if len(target_ids) <= max_decoder_tokens else tok.encode(target_text, max_length=max_decoder_tokens))
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
