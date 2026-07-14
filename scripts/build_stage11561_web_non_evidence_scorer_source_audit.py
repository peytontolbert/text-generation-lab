#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit

ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11561
NAME = "stage11561_web_non_evidence_scorer_source_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_non_evidence_scorer_source_audit.json"

RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
ROWSETS = {
    "web_heldout": ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl",
    "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "old_canary_strict": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
}
SOURCES = [
    "encoder_option_retrieval",
    "encoder_option_retrieval_conditioned",
    "encoder_option_retrieval_verifier_conditioned",
    "encoder_option_retrieval_evidence_role_map",
    "encoder_option_retrieval_dynamic_productized",
    "encoder_option_retrieval_role_bias",
    "encoder_option_retrieval_pairwise",
    "encoder_option_retrieval_evidence_pairwise_gated",
    "encoder_option_retrieval_evidence_ledger_head",
    "encoder_option_retrieval_evidence_role_head",
    "encoder_option_retrieval_evidence_judgment_head",
    "encoder_option_retrieval_evidence_conditioned_gated",
    "encoder_option_retrieval_evidence_fact_text",
    "encoder_option_retrieval_evidence_fact_pairwise",
    "encoder_option_retrieval_semantic_candidate_head",
]

torch.set_num_threads(max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8"))))
try:
    torch.set_num_interop_threads(max(1, min(4, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))))
except RuntimeError:
    pass
DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out.setdefault("prompt_text", out.get("input_text") or "")
    out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or "")
    if not isinstance(out.get("loss_mask"), dict):
        out["loss_mask"] = {"decoder_ce": True}
    standalone = dict(out.get("standalone_projection_source") or {})
    standalone.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = standalone
    if "target" not in out or not isinstance(out.get("target"), dict):
        out["target"] = {"decoder_text": out.get("decoder_text"), "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text")}
    return out


def task_name(row_id: str) -> str:
    parts = str(row_id).split("::")
    if not parts:
        return "unknown"
    task = parts[-1]
    if task in {"heldout_v1", "train_v1", "strict_candidate_explicit_ledger_v1"} and len(parts) >= 2:
        task = parts[-2]
    return task


def family(row_id: str) -> str:
    rid = str(row_id)
    if "llama_stack" in rid:
        return "llama_stack"
    if "openhands" in rid:
        return "openhands"
    if "mcp_typescript" in rid or "mcp_" in rid:
        return "mcp"
    if "sep_automation" in rid:
        return "sep"
    if "stage10938" in rid:
        return "residual10938"
    if "rust" in rid or "rust-analyzer" in rid:
        return "rust"
    return "other"


def load_runtime() -> tuple[Any, Any, dict[str, Any]]:
    bundle = load_json(RUNTIME)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME, model=model)
    model.to(DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def summarize(card: dict[str, Any]) -> dict[str, Any]:
    rows = card.get("row_cards") or []
    correct = sum(1 for r in rows if r.get("constrained_choice_match") is True)
    misses = [r for r in rows if r.get("constrained_choice_match") is False]
    by_task: dict[str, dict[str, int]] = {}
    by_family: dict[str, dict[str, int]] = {}
    for r in rows:
        ok = r.get("constrained_choice_match") is True
        for bucket, key in [(by_task, task_name(str(r.get("row_id") or ""))), (by_family, family(str(r.get("row_id") or "")) )]:
            bucket.setdefault(key, {"rows": 0, "correct": 0})
            bucket[key]["rows"] += 1
            bucket[key]["correct"] += int(ok)
    return {
        "rows": len(rows),
        "correct": correct,
        "accuracy": correct / len(rows) if rows else None,
        "coverage": card.get("constrained_choice_coverage"),
        "by_task": by_task,
        "by_family": by_family,
        "misses": [{"row_id": r.get("row_id"), "target": r.get("bounded_choice_target_label"), "predicted": r.get("constrained_choice_top1_label"), "full_vocab_top1_text": r.get("full_vocab_top1_text"), "target_rank_full_vocab": r.get("target_rank_full_vocab")} for r in misses],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rowsets = {name: [normalize_row(r) for r in load_jsonl(path)] for name, path in ROWSETS.items()}
    model, tokenizer, init_card = load_runtime()
    results: dict[str, Any] = {}
    for source in SOURCES:
        results[source] = {}
        for name, rows in rowsets.items():
            try:
                card = _write_bounded_choice_eval_audit(
                    OUT / source,
                    model=model,
                    rows=rows,
                    tokenizer=tokenizer,
                    max_encoder_tokens=768,
                    max_decoder_tokens=16,
                    split_name=name,
                    bounded_choice_aux_source=source,
                    eval_batch_size=8,
                )
                results[source][name] = summarize(card)
            except Exception as exc:
                results[source][name] = {"error": repr(exc)}
    candidates = {}
    for source, res in results.items():
        web = res.get("web_heldout", {})
        strict = res.get("filtered_strict", {})
        old = res.get("old_canary_strict", {})
        residual = res.get("residual_bank", {})
        if not any("error" in x for x in [web, strict, old, residual]):
            if strict.get("correct", 0) >= 22 and old.get("correct", 0) >= 23 and residual.get("correct", 0) >= 7 and web.get("correct", 0) > 35:
                candidates[source] = {"web": web.get("correct"), "residual": residual.get("correct"), "strict": strict.get("correct"), "old": old.get("correct")}
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "scorer_source_candidate_found" if candidates else "no_existing_scorer_source_promoted",
        "runtime": rel(RUNTIME),
        "device": str(DEVICE),
        "results": results,
        "promotion_candidates": candidates,
        "source_artifacts": {name: rel(path) for name, path in ROWSETS.items()},
        "runtime_initialization": init_card,
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({
        "decision": summary["decision"],
        "promotion_candidates": candidates,
        "compact": {source: {k: v.get("correct") if isinstance(v, dict) else None for k, v in res.items()} for source, res in results.items()},
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
