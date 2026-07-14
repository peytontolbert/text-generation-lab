#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import (
    _bounded_choice_option_logits,
    _load_runtime_model_bundle,
    _move_manifest_batch,
    build_batch,
)

ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10940
NAME = "stage10940_explicit_verifier_ledger_margin_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "explicit_verifier_ledger_margin_audit.json"
ROWS_JSONL = OUT_DIR / "row_option_scores.jsonl"

RUNTIME_BUNDLE = ARTIFACTS / "stage10936_explicit_verifier_ledger_support_probe" / "runtime_model" / "runtime_model_bundle.json"
ROWS_JSON = ARTIFACTS / "stage10938_explicit_verifier_ledger_strict_candidates" / "strict_candidate_rows.jsonl"
MAX_ENCODER_TOKENS = 768
MAX_DECODER_TOKENS = 8
OPTION_SOURCE = "encoder_option_retrieval"

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
EVAL_DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any]]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    model.to(EVAL_DEVICE)
    model.eval()
    return model, tokenizer, init_card


def semantic_value(row: dict[str, Any], label: str) -> str | None:
    for option in (row.get("standalone_projection_source") or {}).get("opaque_options") or []:
        if str(option.get("label") or "") == label:
            return str(option.get("value") or "")
    return None


def margin_record(row: dict[str, Any], option_pairs: list[tuple[str, int]], option_logits: torch.Tensor) -> dict[str, Any]:
    probs = torch.softmax(option_logits.float().cpu(), dim=-1)
    scored = []
    for idx, (label, _token_id) in enumerate(option_pairs):
        scored.append(
            {
                "label": label,
                "semantic_value": semantic_value(row, label),
                "logit": float(option_logits[idx].item()),
                "probability": float(probs[idx].item()),
            }
        )
    scored.sort(key=lambda item: item["logit"], reverse=True)
    target_label = str(row.get("target_text") or "")
    target = next((item for item in scored if item["label"] == target_label), None)
    top1 = scored[0] if scored else None
    top2 = scored[1] if len(scored) > 1 else None
    candidate_surface = next((item for item in scored if item["semantic_value"] == "candidate_change_surface"), None)
    verifier_surface = next((item for item in scored if item["semantic_value"] == "verifier_and_test_constraint"), None)
    return {
        "row_id": row.get("row_id"),
        "language_family": row.get("language_family"),
        "repo_id": row.get("repo_id"),
        "task_type": row.get("task_type"),
        "target_label": target_label,
        "target_semantic_value": semantic_value(row, target_label),
        "top1_label": top1["label"] if top1 else None,
        "top1_semantic_value": top1["semantic_value"] if top1 else None,
        "top1_probability": top1["probability"] if top1 else None,
        "top2_label": top2["label"] if top2 else None,
        "top2_semantic_value": top2["semantic_value"] if top2 else None,
        "top2_probability": top2["probability"] if top2 else None,
        "top1_minus_top2": (top1["probability"] - top2["probability"]) if top1 and top2 else None,
        "target_probability": target["probability"] if target else None,
        "target_rank": next((idx + 1 for idx, item in enumerate(scored) if item["label"] == target_label), None),
        "candidate_change_surface_probability": candidate_surface["probability"] if candidate_surface else None,
        "verifier_and_test_constraint_probability": verifier_surface["probability"] if verifier_surface else None,
        "candidate_minus_verifier_probability": (
            (candidate_surface["probability"] - verifier_surface["probability"])
            if candidate_surface is not None and verifier_surface is not None
            else None
        ),
        "scored_options": scored,
    }


def main() -> None:
    rows = load_jsonl(ROWS_JSON)
    model, tokenizer, init_card = load_runtime()
    batch = build_batch(rows, max_encoder_tokens=MAX_ENCODER_TOKENS, max_decoder_tokens=MAX_DECODER_TOKENS, tokenizer=tokenizer)
    batch = _move_manifest_batch(batch, EVAL_DEVICE)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
        first_step_logits = out["decoder_logits"][:, 0, :].detach()
        pooled = out.get("pooled")

    row_records = []
    for idx, row in enumerate(rows):
        option_logits, option_pairs, error = _bounded_choice_option_logits(
            row=row,
            tokenizer=tokenizer,
            source=OPTION_SOURCE,
            first_step_logits_row=first_step_logits[idx],
            pooled_row=(pooled[idx] if isinstance(pooled, torch.Tensor) else None),
            model=model,
            untied_head=getattr(model, "bounded_choice_probe_head", None),
        )
        if option_logits is None:
            row_records.append(
                {
                    "row_id": row.get("row_id"),
                    "language_family": row.get("language_family"),
                    "repo_id": row.get("repo_id"),
                    "task_type": row.get("task_type"),
                    "error": error,
                }
            )
            continue
        row_records.append(margin_record(row, option_pairs, option_logits))

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in row_records:
        grouped[str(record.get("repo_id") or "unknown")].append(record)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Audit option-level encoder_option_retrieval scores on the explicit-verifier-ledger successor slice.",
            "Use the scored margins to distinguish missing-evidence problems from scorer-boundary problems on candidate_change_surface versus verifier_and_test_constraint.",
        ],
        "runtime_bundle": rel(RUNTIME_BUNDLE),
        "runtime_initialization": init_card,
        "rows": row_records,
        "by_repo": {repo: entries for repo, entries in sorted(grouped.items())},
        "findings": [
            "If candidate_change_surface still outranks verifier_and_test_constraint on the rebuilt rows, the remaining blocker is scorer geometry rather than missing visible evidence.",
            "If full-vocab top-1 reaches the verifier label while encoder_option_retrieval prefers candidate_change_surface, the best next move is scorer-focused support rather than broad decoder replay.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "row_scores_jsonl": rel(ROWS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    write_jsonl(ROWS_JSONL, row_records)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
