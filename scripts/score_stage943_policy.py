#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import torch


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {name}: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--targets-jsonl", required=True)
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--module-state-pt", required=True)
    parser.add_argument("--router-state-pt", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-query-tokens", type=int, default=128)
    parser.add_argument("--max-doc-tokens", type=int, default=128)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-predictions-jsonl", default="")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    stage926 = _load_module(repo_root / "scripts/train_stage926_cached_residual_value_head.py", "stage926")
    stage935 = _load_module(repo_root / "scripts/train_stage935_multihead_value_module.py", "stage935")
    helper = stage926._load_stage924()
    retrieval_eval = helper._load_retrieval_eval(repo_root)
    device = torch.device(str(args.device))
    rows = helper._rows_by_split(helper._iter_jsonl(Path(args.targets_jsonl)))
    module_state = torch.load(str(args.module_state_pt), map_location=device)
    router_state = torch.load(str(args.router_state_pt), map_location=device)
    operations = list(module_state["operations"])
    alphas = {str(k): float(v) for k, v in module_state["alphas"].items()}

    base_model, tokenizer, _ = retrieval_eval._load_model(Path(args.bundle_dir).resolve(), repo_root=repo_root, device=device)
    for parameter in base_model.parameters():
        parameter.requires_grad_(False)
    query_texts = {split: [str(row.get("query_text", "") or "") for row in split_rows] for split, split_rows in rows.items()}
    docs = {split: helper._unique_docs(split_rows) for split, split_rows in rows.items()}
    doc_to_index = {split: {doc: idx for idx, doc in enumerate(split_docs)} for split, split_docs in docs.items()}
    query_cache = {split: helper._make_text_cache(retrieval_eval, tokenizer, texts, max_tokens=int(args.max_query_tokens), device=device) for split, texts in query_texts.items()}
    doc_cache = {split: helper._make_text_cache(retrieval_eval, tokenizer, split_docs, max_tokens=int(args.max_doc_tokens), device=device) for split, split_docs in docs.items()}
    with torch.no_grad():
        embed_dim = int(helper._embed_query_from_cache(base_model, query_cache["train"], 0).shape[-1])

    module = stage935.MultiHeadValue(operations, embed_dim * 4 + 2, 32, stage926.ResidualHead).to(device)
    module.load_state_dict(module_state["module_state_dict"])
    module.eval()

    router = torch.nn.Linear(len(router_state["mean"]) + 1 + len(router_state["ops"]), 1).to(device)
    router.load_state_dict(router_state["state_dict"])
    router.eval()
    router_mean = router_state["mean"].to(device)
    router_std = router_state["std"].to(device)
    router_threshold = float(router_state["threshold"])
    router_ops = list(router_state["ops"])

    by_split: dict[str, dict[str, Any]] = {}
    prediction_rows = []
    with torch.no_grad():
        for split, split_rows in rows.items():
            for row_index, row in enumerate(split_rows):
                candidates = list(row.get("candidates", []) or [])
                if not candidates:
                    continue
                op = str(row.get("operation", "") or "unknown")
                features = stage926._features(helper, base_model, row_index, row, query_cache[split], doc_cache[split], doc_to_index[split])
                head_scores = module(op, features).detach().cpu()
                base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates])
                alpha = float(alphas.get(op, 0.0))
                blend_scores = base_scores + alpha * head_scores
                base_order = sorted(range(len(candidates)), key=lambda idx: (-float(base_scores[idx]), idx))
                policy_order = sorted(range(len(candidates)), key=lambda idx: (-float(blend_scores[idx]), idx))
                base_idx = int(base_order[0])
                policy_idx = int(policy_order[0])
                final_idx = policy_idx
                source = "stage938_specialist"
                accept_override = bool(policy_idx != base_idx)
                router_probability = None
                if op == "composition":
                    override = int(policy_idx != base_idx)
                    margin = float(blend_scores[policy_idx]) - float(blend_scores[base_idx]) if override else 0.0
                    head_delta = float(head_scores[policy_idx]) - float(head_scores[base_idx]) if override else 0.0
                    base_gap = float(base_scores[base_idx]) - float(base_scores[policy_idx]) if override else 0.0
                    raw = torch.tensor(
                        [
                            1.0,
                            float(override),
                            margin,
                            head_delta,
                            base_gap,
                            float(base_scores[base_idx]),
                            float(base_scores[policy_idx]),
                            float(head_scores[base_idx]),
                            float(head_scores[policy_idx]),
                        ]
                        + [1.0 if name == op else 0.0 for name in router_ops],
                        dtype=torch.float32,
                        device=device,
                    )
                    raw[1:9] = (raw[1:9] - router_mean) / router_std
                    router_probability = float(torch.sigmoid(router(raw).squeeze()).detach().cpu())
                    accept_override = bool(override) and router_probability >= router_threshold
                    final_idx = policy_idx if accept_override else base_idx
                    source = "stage943_composition_router" if accept_override else "base_preserved_by_composition_router"
                final_answer, final_exact = _hit(candidates[final_idx])
                stats = by_split.setdefault(split, {}).setdefault(op, {"examples": 0, "answer": 0, "exact": 0, "accepted_overrides": 0})
                stats["examples"] += 1
                stats["answer"] += final_answer
                stats["exact"] += final_exact
                stats["accepted_overrides"] += int(accept_override)
                prediction_rows.append({
                    "split": split,
                    "row_index": row_index,
                    "query_index": row.get("query_index"),
                    "operation": op,
                    "source": source,
                    "base_top_index": base_idx,
                    "policy_top_index": policy_idx,
                    "final_top_index": final_idx,
                    "accepted_override": accept_override,
                    "router_probability": router_probability,
                    "answer": final_answer,
                    "exact": final_exact,
                })

    def pack(split: str) -> dict[str, Any]:
        by_op = by_split[split]
        return {
            "examples": sum(v["examples"] for v in by_op.values()),
            "answer_correct": sum(v["answer"] for v in by_op.values()),
            "exact_correct": sum(v["exact"] for v in by_op.values()),
            "by_operation": by_op,
        }

    summary = {
        "artifact_kind": "stage943_loadable_policy_scorer",
        "module_state_pt": str(args.module_state_pt),
        "router_state_pt": str(args.router_state_pt),
        "router_threshold": router_threshold,
        "train": pack("train"),
        "calibration": pack("calibration"),
        "eval": pack("eval"),
        "expected_answer_exact": [252, 235],
        "implied_full_answer_exact": [pack("eval")["answer_correct"] + 230, pack("eval")["exact_correct"] + 229],
        "caveat": "Loadable scorer for candidate-ranking policy, not direct generation.",
    }
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_json).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if str(args.output_predictions_jsonl):
        out = Path(args.output_predictions_jsonl)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as handle:
            for item in prediction_rows:
                handle.write(json.dumps(item, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
