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
STAGE = 11589
NAME = "stage11589_web_successor_scorer_source_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_successor_scorer_source_audit.json"
RUNTIMES = {
    "stage11507_selected": ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json",
    "stage11586_rejected": ART / "stage11586_web_task_aware_contrast_probe/runtime_model/runtime_model_bundle.json",
}
ROWSETS = {
    "web_successor_strict": ART / "stage11586_web_task_aware_contrast_probe_request/web_task_aware_contrast_successor_strict_rows.jsonl",
    "web_heldout": ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl",
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
}
SOURCES = [
    "encoder_option_retrieval_evidence_judgment_head",
    "encoder_option_retrieval_verifier_conditioned",
    "encoder_option_retrieval_conditioned",
    "encoder_option_retrieval",
    "encoder_option_retrieval_dynamic_productized",
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
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out.setdefault("prompt_text", out.get("input_text") or "")
    out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or "")
    source = dict(out.get("standalone_projection_source") or {})
    source.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = source
    if not isinstance(out.get("target"), dict):
        out["target"] = {"decoder_text": out.get("decoder_text"), "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text")}
    return out


def load_runtime(path: Path) -> tuple[Any, Any, dict[str, Any]]:
    bundle = load_json(path)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(path, model=model)
    model.to(DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def metric(card: dict[str, Any]) -> dict[str, Any]:
    pred_counts: dict[str, int] = {}
    target_counts: dict[str, int] = {}
    for row in card.get("row_cards") or []:
        pred = str(row.get("constrained_choice_top1_label"))
        target = str(row.get("bounded_choice_target_label"))
        pred_counts[pred] = pred_counts.get(pred, 0) + 1
        target_counts[target] = target_counts.get(target, 0) + 1
    return {
        "rows": card.get("rows"),
        "correct": card.get("constrained_choice_correct"),
        "coverage": card.get("constrained_choice_coverage"),
        "accuracy": card.get("constrained_choice_top1_accuracy"),
        "pred_counts": pred_counts,
        "target_counts": target_counts,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rowsets = {name: [normalize_row(row) for row in load_jsonl(path)] for name, path in ROWSETS.items()}
    results: dict[str, Any] = {}
    init_cards: dict[str, Any] = {}
    for runtime_name, runtime_path in RUNTIMES.items():
        model, tokenizer, init_card = load_runtime(runtime_path)
        init_cards[runtime_name] = init_card
        results[runtime_name] = {}
        for source in SOURCES:
            results[runtime_name][source] = {}
            for rowset_name, rows in rowsets.items():
                try:
                    card = _write_bounded_choice_eval_audit(
                        OUT / runtime_name / source,
                        model=model,
                        rows=rows,
                        tokenizer=tokenizer,
                        max_encoder_tokens=768,
                        max_decoder_tokens=16,
                        split_name=rowset_name,
                        bounded_choice_aux_source=source,
                        eval_batch_size=8,
                    )
                    results[runtime_name][source][rowset_name] = metric(card)
                except Exception as exc:  # keep unsupported sources visible instead of failing the audit
                    results[runtime_name][source][rowset_name] = {"error": type(exc).__name__, "message": str(exc)}
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "device": str(DEVICE),
        "decision": "scorer_source_audit_complete_no_training",
        "results": results,
        "runtime_initialization": init_cards,
        "source_artifacts": {"runtimes": {k: rel(v) for k, v in RUNTIMES.items()}, "rowsets": {k: rel(v) for k, v in ROWSETS.items()}},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    compact = {
        runtime: {
            source: {
                rowset: {"correct": card.get("correct"), "rows": card.get("rows"), "pred_counts": card.get("pred_counts"), "error": card.get("error")}
                for rowset, card in source_results.items()
            }
            for source, source_results in runtime_results.items()
        }
        for runtime, runtime_results in results.items()
    }
    print(json.dumps({"decision": summary["decision"], "compact": compact}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
