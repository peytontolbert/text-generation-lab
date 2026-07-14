#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer, build_batch
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle

DEFAULT_MANIFEST = ROOT / "runs/local/artifacts/stage10378_balanced_residual_probe_execution_request/balanced_residual_probe_manifest.jsonl"
DEFAULT_RUNTIME = ROOT / "runs/local/artifacts/stage10379_balanced_residual_probe/runtime_model/runtime_model_bundle.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score a runtime bundle on the unchanged 47-row frontier.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--runtime-bundle", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stage-name", default="stage10395_generic_language_conditioned_frontier_eval")
    parser.add_argument(
        "--policy",
        default="baseline_language_conditioned",
        choices=["baseline_language_conditioned", "python_verifier_drop_extension_v1"],
    )
    return parser.parse_args()


def load_rows(manifest_path: Path) -> list[dict[str, object]]:
    rows = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("split") == "strict_eval":
            rows.append(row)
    rows.sort(key=lambda row: str(row["row_id"]))
    return rows


def load_runtime(runtime_bundle: Path) -> tuple[AgentKernelLiteTransformerSeq2Seq, object]:
    bundle = json.loads(runtime_bundle.read_text(encoding="utf-8"))
    metadata = bundle["metadata"]
    model_config = json.loads(Path(str(metadata["model_config"])).read_text(encoding="utf-8"))
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(model_config)
    model = AgentKernelLiteTransformerSeq2Seq(config)
    _load_runtime_model_bundle(runtime_bundle, model=model)
    from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer

    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    model.eval()
    return model, tokenizer


def option_pairs(row: dict[str, object]) -> list[tuple[str, str]]:
    options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    return [(str(option["label"]), str(option["value"])) for option in options]


def header_prefix(row: dict[str, object]) -> str:
    prompt = str(row.get("prompt_text") or "")
    return prompt.split("\nEvidence:\n", 1)[0].strip()


def perspective(row: dict[str, object]) -> str:
    prompt = str(row.get("prompt_text") or "")
    for line in prompt.splitlines():
        if line.startswith("Perspective: "):
            return line.split(": ", 1)[1].strip()
    return ""


def language(row: dict[str, object]) -> str:
    return str(row.get("language_family") or "unknown")


def variant_name(row: dict[str, object]) -> str:
    return "task_role_templated" if language(row) == "rust" else "raw_value"


def drop_extension(value: str) -> str:
    return str(Path(value).with_suffix(""))


def variant_name_for_policy(row: dict[str, object], policy: str) -> str:
    if policy == "baseline_language_conditioned":
        return variant_name(row)
    if policy == "python_verifier_drop_extension_v1":
        if language(row) == "rust":
            return "task_role_templated"
        if language(row) == "python" and perspective(row) == "verifier_outcome":
            return "drop_extension"
        return "raw_value"
    raise ValueError(f"unsupported policy: {policy}")


def variant_text(row: dict[str, object], value: str, selected_variant: str) -> str:
    if selected_variant == "raw_value":
        return value
    if selected_variant == "drop_extension":
        return drop_extension(value)
    row_perspective = perspective(row)
    header = header_prefix(row)
    if selected_variant == "header_only":
        return f"{header}\nCandidate under review: {value}" if header else f"Candidate under review: {value}"
    if selected_variant == "task_templated":
        return f"Perspective={row_perspective}\nCandidate answer under review: {value}"
    if row_perspective == "evidence_citation":
        return f"Perspective=evidence_citation\nVisible fact role under review: {value}"
    if row_perspective == "verifier_outcome":
        return f"Perspective=verifier_outcome\nVerifier or test target under review: {value}"
    if row_perspective == "abstention_insufficient_evidence":
        return f"Perspective=abstention_insufficient_evidence\nCandidate answer under review: {value}"
    return f"Perspective={row_perspective}\nCandidate under review: {value}"


def encode_option_texts(model: AgentKernelLiteTransformerSeq2Seq, tokenizer: object, texts: list[str], device: torch.device) -> torch.Tensor:
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
    tokenizer: object,
    row: dict[str, object],
    *,
    policy: str,
) -> dict[str, object]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    query = out["pooled"][0:1]
    retrieval_query_head = getattr(model, "retrieval_query_head", None)
    retrieval_doc_head = getattr(model, "retrieval_doc_head", None)
    if retrieval_query_head is not None:
        query = retrieval_query_head(query)
    selected_variant = variant_name_for_policy(row, policy)
    pairs = option_pairs(row)
    texts = [variant_text(row, value, selected_variant) for _, value in pairs]
    option_vectors = encode_option_texts(model, tokenizer, texts, query.device)
    if retrieval_doc_head is not None:
        option_vectors = retrieval_doc_head(option_vectors)
    query = F.normalize(query.float(), dim=-1)
    option_vectors = F.normalize(option_vectors.float(), dim=-1)
    logits = torch.matmul(query, option_vectors.transpose(0, 1)).squeeze(0)
    scored = [
        {"label": label, "value": value, "logit": float(logits[idx].item())}
        for idx, (label, value) in enumerate(pairs)
    ]
    scored.sort(key=lambda item: item["logit"], reverse=True)
    pred = scored[0]["label"]
    target = str(row["decoder_text"])
    return {
        "row_id": row["row_id"],
        "language_family": language(row),
        "perspective": perspective(row),
        "selected_variant": selected_variant,
        "target": target,
        "pred": pred,
        "correct": pred == target,
        "top3": scored[:3],
    }


def main() -> None:
    args = parse_args()
    rows = load_rows(args.manifest)
    model, tokenizer = load_runtime(args.runtime_bundle)
    row_cards = [score_row(model, tokenizer, row, policy=args.policy) for row in rows]
    correct = sum(1 for row in row_cards if row["correct"])
    payload = {
        "stage_name": args.stage_name,
        "policy": args.policy,
        "runtime_bundle": str(args.runtime_bundle),
        "manifest": str(args.manifest),
        "rows": len(row_cards),
        "correct": correct,
        "accuracy": correct / len(row_cards),
        "row_cards": row_cards,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(args.output))


if __name__ == "__main__":
    main()
