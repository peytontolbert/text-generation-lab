#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from collections import defaultdict
from pathlib import Path
import sys
from typing import Any, Iterator

import torch


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _install_paths(repo_root: Path) -> None:
    model_stack = repo_root / "other_repos" / "model-stack"
    for path in (repo_root, model_stack):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)


def _iter_rows(path: Path) -> Iterator[dict[str, Any]]:
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

    tokenizer_kind = str(manifest.get("tokenizer_kind", "byte") or "byte").lower()
    tokenizer_dir = Path(str(manifest.get("tokenizer_dir", "") or ""))
    if tokenizer_kind == "byte":
        return module.ByteTokenizer()
    if tokenizer_kind == "agentkernel-bpe":
        return module.TokenizersBpe(tokenizer_dir / "tokenizer.json")
    return module.HuggingFaceTokenizer(tokenizer_dir, str(manifest.get("tokenizer_name", "")))


def _materialize_lazy_modules(model: torch.nn.Module) -> None:
    for module in model.modules():
        ensure_self_attn = getattr(module, "_ensure_self_attn", None)
        if callable(ensure_self_attn):
            ensure_self_attn()


def _load_model(bundle_dir: Path, *, repo_root: Path, device: torch.device):
    _install_paths(repo_root)
    from runtime.checkpoint import load_config, load_pretrained
    from runtime.seq2seq import EncoderDecoderLM

    manifest = json.loads((bundle_dir / "agentkernel_lite_encdec_manifest.json").read_text(encoding="utf-8"))
    model_dir = Path(str(manifest["model_dir"]))
    config = load_config(str(model_dir))
    tokenizer = _load_tokenizer(manifest)
    model = EncoderDecoderLM(config, tie_embeddings=True, vocab_size=int(config.vocab_size))
    _materialize_lazy_modules(model)
    load_pretrained(model, str(model_dir), strict=True)
    model.to(device).eval()
    return model, tokenizer, manifest


def _encode_batch(tokenizer: Any, texts: list[str], *, max_tokens: int, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    pad_id = int(getattr(tokenizer, "pad_token_id", 0) or 0)
    ids: list[list[int]] = []
    masks: list[list[int]] = []
    for text in texts:
        row = tokenizer.encode(text, max_length=max_tokens)[:max_tokens]
        mask = [1] * len(row)
        while len(row) < max_tokens:
            row.append(pad_id)
            mask.append(0)
        ids.append(row)
        masks.append(mask)
    return torch.tensor(ids, dtype=torch.long, device=device), torch.tensor(masks, dtype=torch.bool, device=device)


def _operation(row: dict[str, Any]) -> str:
    op = str(row.get("operation", "") or "")
    if op:
        return op
    query = str(row.get("retrieval_query_text", "") or "")
    return query.split(" ", 1)[0].split("=", 1)[1] if query.startswith("op=") else "unknown"


def _update_counts(counts: dict[str, list[int]], op: str, selected: torch.Tensor, mask: torch.Tensor, num_experts: int) -> None:
    if op not in counts:
        counts[op] = [0 for _ in range(num_experts)]
    selected_cpu = selected.detach().cpu()
    mask_cpu = mask.detach().cpu()
    for expert in selected_cpu[mask_cpu].tolist():
        counts[op][int(expert)] += 1


def _entropy(probs: list[float]) -> float:
    import math

    return -sum(p * math.log2(p) for p in probs if p > 0.0)


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    device = torch.device(str(args.device))
    model, tokenizer, _manifest = _load_model(Path(args.bundle_dir).resolve(), repo_root=Path(args.repo_root).resolve(), device=device)
    dataset_manifest = json.loads(Path(args.dataset_manifest).read_text(encoding="utf-8"))
    dataset_path = Path(str(dataset_manifest["eval_dataset_path"] if args.dataset_split == "eval" else dataset_manifest["train_dataset_path"]))
    rows = [row for row in _iter_rows(dataset_path) if row.get("retrieval_query_text") and row.get("retrieval_doc_text")]
    if int(args.limit) > 0:
        rows = rows[: int(args.limit)]

    adapters = [(name, module) for name, module in model.named_modules() if hasattr(module, "router") and hasattr(module, "num_experts")]
    if not adapters:
        return {"bundle_dir": str(args.bundle_dir), "router_modules": [], "message": "no routed modules found"}
    num_experts = int(getattr(adapters[0][1], "num_experts"))
    counts_by_side: dict[str, dict[str, list[int]]] = {"query": {}, "doc": {}}
    totals_by_side: dict[str, int] = {"query": 0, "doc": 0}
    current: dict[str, Any] = {"side": "", "mask": None, "operations": []}

    hooks = []
    for _name, module in adapters:
        def _hook(mod, inputs, _output):
            x = inputs[0]
            mask = current["mask"]
            if mask is None or x.ndim != 3 or tuple(x.shape[:2]) != tuple(mask.shape):
                return
            logits = mod.router(x)
            selected = logits.argmax(dim=-1)
            for row_idx, op in enumerate(current["operations"]):
                row_mask = mask[row_idx]
                _update_counts(counts_by_side[current["side"]], op, selected[row_idx], row_mask, int(mod.num_experts))
                totals_by_side[current["side"]] += int(row_mask.sum().detach().cpu().item())

        hooks.append(module.register_forward_hook(_hook))

    try:
        with torch.no_grad():
            for offset in range(0, len(rows), int(args.batch_size)):
                batch = rows[offset : offset + int(args.batch_size)]
                operations = [_operation(row) for row in batch]
                for side, text_key, max_tokens in (
                    ("query", "retrieval_query_text", int(args.max_query_tokens)),
                    ("doc", "retrieval_doc_text", int(args.max_doc_tokens)),
                ):
                    texts = [str(row[text_key]) for row in batch]
                    ids, mask = _encode_batch(tokenizer, texts, max_tokens=max_tokens, device=device)
                    current["side"] = side
                    current["mask"] = mask
                    current["operations"] = operations
                    if side == "query" and hasattr(model, "retrieval_query_embedding"):
                        model.retrieval_query_embedding(ids, mask.long())
                    elif side == "doc" and hasattr(model, "retrieval_doc_embedding"):
                        model.retrieval_doc_embedding(ids, mask.long())
                    else:
                        model.encode(ids, mask.long())
    finally:
        for hook in hooks:
            hook.remove()

    by_side: dict[str, Any] = {}
    for side, op_counts in counts_by_side.items():
        by_operation: dict[str, Any] = {}
        total_counts = [0 for _ in range(num_experts)]
        for op, counts in sorted(op_counts.items()):
            total = sum(counts)
            probs = [count / total if total else 0.0 for count in counts]
            by_operation[op] = {
                "tokens": total,
                "expert_counts": counts,
                "expert_probs": probs,
                "entropy_bits": _entropy(probs),
                "top_expert": max(range(num_experts), key=lambda idx: counts[idx]) if total else None,
            }
            for idx, count in enumerate(counts):
                total_counts[idx] += count
        total = sum(total_counts)
        total_probs = [count / total if total else 0.0 for count in total_counts]
        by_side[side] = {
            "tokens": total,
            "expert_counts": total_counts,
            "expert_probs": total_probs,
            "entropy_bits": _entropy(total_probs),
            "by_operation": by_operation,
        }

    return {
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "dataset_manifest": str(Path(args.dataset_manifest).resolve()),
        "dataset_split": str(args.dataset_split),
        "evaluated_pairs": len(rows),
        "router_modules": [name for name, _module in adapters],
        "num_experts": num_experts,
        "by_side": by_side,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--dataset-split", choices=("train", "eval"), default="eval")
    parser.add_argument("--repo-root", default="/data/agentkernel")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-query-tokens", type=int, default=96)
    parser.add_argument("--max-doc-tokens", type=int, default=96)
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()
    result = analyze(args)
    if str(args.output_json).strip():
        Path(args.output_json).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
