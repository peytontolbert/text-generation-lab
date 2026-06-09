#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
EVAL_SCRIPT = ROOT / "legacy_src/scripts/evaluate_agentkernel_lite_retrieval_embeddings.py"


def _load_eval_module():
    spec = importlib.util.spec_from_file_location("ak_eval", EVAL_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {EVAL_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install_model_stack(repo_root: Path) -> None:
    for path in (repo_root, repo_root / "other_repos/model-stack"):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)


def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo-root", default="legacy_src")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--temperature", type=float, default=0.05)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--max-query-tokens", type=int, default=96)
    parser.add_argument("--max-doc-tokens", type=int, default=256)
    parser.add_argument("--train-doc-head", type=int, default=0)
    parser.add_argument("--fixed-doc-bank", type=int, default=1)
    parser.add_argument("--teacher-distill-weight", type=float, default=0.0)
    parser.add_argument("--teacher-temperature", type=float, default=0.05)
    parser.add_argument("--details-jsonl", default="")
    parser.add_argument("--miss-weight", type=float, default=1.0)
    parser.add_argument("--correct-weight", type=float, default=1.0)
    parser.add_argument("--fragile-correct-margin", type=float, default=0.0)
    parser.add_argument("--fragile-correct-weight", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=694)
    args = parser.parse_args()

    torch.manual_seed(int(args.seed))
    ak_eval = _load_eval_module()
    repo_root = (ROOT / args.repo_root).resolve()
    _install_model_stack(repo_root)
    device = torch.device(args.device)

    bundle_dir = (ROOT / args.bundle_dir).resolve()
    output_dir = (ROOT / args.output_dir).resolve()
    model, tokenizer, manifest = ak_eval._load_model(bundle_dir, repo_root=repo_root, device=device)
    dataset_manifest = json.loads((ROOT / args.dataset_manifest).read_text(encoding="utf-8"))
    rows = [
        row
        for row in _iter_jsonl(Path(dataset_manifest["eval_dataset_path"]))
        if row.get("retrieval_query_text") and row.get("retrieval_doc_text")
    ]
    details_by_id: dict[str, dict[str, Any]] = {}
    if str(args.details_jsonl).strip():
        details_by_id = {
            str(row.get("unit_id")): row
            for row in _iter_jsonl((ROOT / str(args.details_jsonl)).resolve())
        }

    by_operation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_operation[str(row.get("operation", "") or "unknown")].append(row)

    # Freeze everything except the asymmetric retrieval projections requested
    # for this diagnostic.
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    trainable_names = []
    for name, parameter in model.named_parameters():
        if name == "retrieval_query_head.weight" or (bool(args.train_doc_head) and name == "retrieval_doc_head.weight"):
            parameter.requires_grad_(True)
            trainable_names.append(name)
    if not trainable_names:
        raise RuntimeError("retrieval_query_head.weight was not found")

    doc_banks: dict[str, torch.Tensor] = {}
    teacher_logits: dict[str, torch.Tensor] = {}
    query_texts: dict[str, list[str]] = {}
    doc_texts: dict[str, list[str]] = {}
    labels: dict[str, torch.Tensor] = {}
    row_weights: dict[str, torch.Tensor] = {}
    with torch.no_grad():
        for operation, op_rows in by_operation.items():
            docs = [str(row["retrieval_doc_text"]) for row in op_rows]
            doc_texts[operation] = docs
            doc_banks[operation] = ak_eval._embed_doc(
                model,
                tokenizer,
                docs,
                max_tokens=int(args.max_doc_tokens),
                device=device,
            ).detach()
            query_texts[operation] = [str(row["retrieval_query_text"]) for row in op_rows]
            teacher_queries = ak_eval._embed_query(
                model,
                tokenizer,
                query_texts[operation],
                max_tokens=int(args.max_query_tokens),
                device=device,
            )
            teacher_logits[operation] = (
                teacher_queries @ doc_banks[operation].transpose(0, 1)
            ).detach()
            labels[operation] = torch.arange(len(op_rows), dtype=torch.long, device=device)
            weights: list[float] = []
            for row in op_rows:
                source_id = str(row.get("source_id") or row.get("example_id") or "")
                detail = details_by_id.get(source_id, {})
                if not detail:
                    weights.append(1.0)
                    continue
                if not bool(detail.get("answer_top1")):
                    weights.append(float(args.miss_weight))
                    continue
                margin = detail.get("margin_to_best_wrong")
                if (
                    margin is not None
                    and float(args.fragile_correct_margin) > 0.0
                    and float(margin) <= float(args.fragile_correct_margin)
                ):
                    weights.append(float(args.fragile_correct_weight))
                else:
                    weights.append(float(args.correct_weight))
            row_weights[operation] = torch.tensor(weights, dtype=torch.float32, device=device)

    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=float(args.learning_rate), weight_decay=0.0)
    losses: list[float] = []
    model.train()
    operations = sorted(query_texts)
    for step in range(1, int(args.steps) + 1):
        total_loss = None
        for operation in operations:
            queries = query_texts[operation]
            operation_loss = None
            for offset in range(0, len(queries), int(args.batch_size)):
                batch_queries = queries[offset : offset + int(args.batch_size)]
                batch_labels = labels[operation][offset : offset + len(batch_queries)]
                query_matrix = ak_eval._embed_query(
                    model,
                    tokenizer,
                    batch_queries,
                    max_tokens=int(args.max_query_tokens),
                    device=device,
                )
                if bool(args.fixed_doc_bank):
                    doc_matrix = doc_banks[operation]
                else:
                    doc_matrix = ak_eval._embed_doc(
                        model,
                        tokenizer,
                        doc_texts[operation],
                        max_tokens=int(args.max_doc_tokens),
                        device=device,
                    )
                raw_logits = query_matrix @ doc_matrix.transpose(0, 1)
                logits = raw_logits / float(args.temperature)
                per_row_loss = F.cross_entropy(logits, batch_labels, reduction="none")
                batch_weights = row_weights[operation][offset : offset + len(batch_queries)]
                loss = (per_row_loss * batch_weights).sum() / batch_weights.sum().clamp_min(1.0)
                if float(args.teacher_distill_weight) > 0.0:
                    teacher_slice = teacher_logits[operation][offset : offset + len(batch_queries)]
                    teacher_probs = F.softmax(teacher_slice / float(args.teacher_temperature), dim=-1)
                    student_log_probs = F.log_softmax(raw_logits / float(args.teacher_temperature), dim=-1)
                    distill = F.kl_div(student_log_probs, teacher_probs, reduction="batchmean")
                    loss = loss + float(args.teacher_distill_weight) * distill
                operation_loss = loss if operation_loss is None else operation_loss + loss
            total_loss = operation_loss if total_loss is None else total_loss + operation_loss
        assert total_loss is not None
        optimizer.zero_grad(set_to_none=True)
        total_loss.backward()
        optimizer.step()
        losses.append(float(total_loss.detach().cpu().item()))
        if step % 25 == 0 or step == 1:
            print(json.dumps({"step": step, "loss": losses[-1]}, sort_keys=True), flush=True)

    from runtime.checkpoint import load_config, save_pretrained

    source_model_dir = Path(str(manifest["model_dir"]))
    config = load_config(str(source_model_dir))
    model_dir = output_dir / "model"
    tokenizer_dir = output_dir / "tokenizer"
    output_dir.mkdir(parents=True, exist_ok=True)
    save_pretrained(model.eval().cpu(), config, str(model_dir))
    _copy_tree(Path(str(manifest["tokenizer_dir"])), tokenizer_dir)

    checkpoint_dir = output_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = checkpoint_dir / f"step_{int(args.steps):08d}.pt"
    torch.save(
        {
            "step": int(args.steps),
            "model_state_dict": {key: value.detach().cpu() for key, value in model.state_dict().items()},
            "losses": losses,
            "eval_history": [],
            "include_optimizer": False,
        },
        checkpoint_path,
    )
    (checkpoint_dir / "latest.json").write_text(
        json.dumps({"step": int(args.steps), "path": str(checkpoint_path)}, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    out_manifest = dict(manifest)
    out_manifest.update(
        {
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_manifest.json"),
            "model_dir": str(model_dir),
            "tokenizer_dir": str(tokenizer_dir),
            "dataset_manifest_path": str((ROOT / args.dataset_manifest).resolve()),
            "training_summary": {
                **dict(manifest.get("training_summary", {}) or {}),
                "stage694_objective": "query_head_only_fixed_doc_memory_bank_listwise",
                "stage694_train_doc_head": bool(args.train_doc_head),
                "stage694_fixed_doc_bank": bool(args.fixed_doc_bank),
                "stage694_teacher_distill_weight": float(args.teacher_distill_weight),
                "stage694_teacher_temperature": float(args.teacher_temperature),
                "stage694_source_bundle": str(bundle_dir),
                "stage694_details_jsonl": str(args.details_jsonl),
                "stage694_miss_weight": float(args.miss_weight),
                "stage694_correct_weight": float(args.correct_weight),
                "stage694_fragile_correct_margin": float(args.fragile_correct_margin),
                "stage694_fragile_correct_weight": float(args.fragile_correct_weight),
                "completed_steps": int(args.steps),
                "max_steps": int(args.steps),
                "learning_rate": float(args.learning_rate),
                "retrieval_temperature": float(args.temperature),
                "last_loss": losses[-1] if losses else None,
                "mean_loss": sum(losses) / len(losses) if losses else None,
                "trainable_parameter_names": trainable_names,
                "trainable_parameter_count_before_export": sum(
                    p.numel() for p in model.parameters() if p.requires_grad
                ),
                "checkpoint_dir": str(checkpoint_dir),
                "initialized_from": str(bundle_dir),
            },
            "timestamp": int(time.time()),
        }
    )
    out_manifest["parameter_count"] = int(sum(p.numel() for p in model.parameters()))
    manifest_path = output_dir / "agentkernel_lite_encdec_manifest.json"
    manifest_path.write_text(json.dumps(out_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "artifact_kind": "stage694_query_head_memory_bank_bundle",
                "bundle_dir": str(output_dir),
                "checkpoint": str(checkpoint_path),
                "steps": int(args.steps),
                "last_loss": losses[-1] if losses else None,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
