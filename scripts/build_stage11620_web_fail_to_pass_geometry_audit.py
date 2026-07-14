#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from collections import Counter
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
STAGE = 11620
NAME = "stage11620_web_fail_to_pass_geometry_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_fail_to_pass_geometry_audit.json"

CONTROLLED_ROWS = ART / "stage11615_web_mutation_rows_anticheat_audit/web_mutation_rows_admitted_train_support.jsonl"
WEB_HELDOUT = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"
RUNTIMES = {
    "stage11507_selected": ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json",
    "stage11617_rejected": ART / "stage11617_web_fail_to_pass_support_probe/runtime_model/runtime_model_bundle.json",
}
SOURCES = [
    "decoder_first_step",
    "encoder_option_retrieval",
    "encoder_option_retrieval_verifier_conditioned",
    "encoder_option_retrieval_evidence_judgment_head",
    "encoder_option_retrieval_semantic_candidate_head",
    "encoder_option_retrieval_web_task_candidate_head",
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
    out.setdefault("prompt_text", out.get("input_text") or out.get("prompt") or "")
    out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or "")
    if not isinstance(out.get("loss_mask"), dict):
        out["loss_mask"] = {"decoder_ce": True, "bounded_choice_aux": True}
    source = dict(out.get("standalone_projection_source") or {})
    source.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = source
    if "target" not in out or not isinstance(out.get("target"), dict):
        out["target"] = {
            "decoder_text": out.get("decoder_text"),
            "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text"),
            "semantic_value": out.get("target_semantic_value") or out.get("semantic_target_value"),
        }
    return out


def load_runtime(runtime: Path) -> tuple[Any, Any, dict[str, Any]]:
    bundle = load_json(runtime)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(runtime, model=model)
    model.to(DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def option_role_by_label(row: dict[str, Any]) -> dict[str, str]:
    opts = (row.get("standalone_projection_source") or {}).get("opaque_options") or []
    out: dict[str, str] = {}
    for opt in opts:
        if not isinstance(opt, dict):
            continue
        label = str(opt.get("label") or "")
        role = str(opt.get("semantic_role") or opt.get("value") or "")
        if label:
            out[label] = role
    return out


def summarize_card(card: dict[str, Any], rows_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    misses: list[dict[str, Any]] = []
    predictions_by_role: Counter[str] = Counter()
    targets_by_role: Counter[str] = Counter()
    correct_by_task: Counter[str] = Counter()
    total_by_task: Counter[str] = Counter()
    for row_card in card.get("row_cards") or []:
        row_id = str(row_card.get("row_id") or "")
        row = rows_by_id.get(row_id, {})
        label_to_role = option_role_by_label(row)
        target = str(row_card.get("bounded_choice_target_label") or "")
        pred = str(row_card.get("constrained_choice_top1_label") or "")
        target_role = label_to_role.get(target, "")
        pred_role = label_to_role.get(pred, "")
        task = str(row.get("task_type") or row_card.get("task_type") or "unknown")
        targets_by_role[target_role] += 1
        predictions_by_role[pred_role] += 1
        total_by_task[task] += 1
        if row_card.get("constrained_choice_match") is True:
            correct_by_task[task] += 1
        else:
            misses.append({
                "row_id": row_id,
                "task_type": task,
                "target": target,
                "predicted": pred,
                "target_role": target_role,
                "predicted_role": pred_role,
                "full_vocab_top1_text": row_card.get("full_vocab_top1_text"),
                "target_rank_full_vocab": row_card.get("target_rank_full_vocab"),
            })
    return {
        "rows": card.get("rows"),
        "correct": card.get("constrained_choice_correct"),
        "accuracy": card.get("constrained_choice_top1_accuracy"),
        "coverage": card.get("constrained_choice_coverage"),
        "targets_by_role": dict(targets_by_role),
        "predictions_by_role": dict(predictions_by_role),
        "correct_by_task": dict(correct_by_task),
        "total_by_task": dict(total_by_task),
        "misses": misses,
    }


def run_audit(runtime_name: str, runtime: Path, rowset_name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    model, tokenizer, init_card = load_runtime(runtime)
    rows_by_id = {str(row.get("row_id")): row for row in rows}
    result: dict[str, Any] = {"runtime_initialization": init_card, "sources": {}}
    for source in SOURCES:
        subdir = OUT / runtime_name / rowset_name / source
        try:
            card = _write_bounded_choice_eval_audit(
                subdir,
                model=model,
                rows=rows,
                tokenizer=tokenizer,
                max_encoder_tokens=768,
                max_decoder_tokens=16,
                split_name=f"{rowset_name}_{source}",
                bounded_choice_aux_source=source,
                eval_batch_size=8,
            )
            result["sources"][source] = summarize_card(card, rows_by_id)
        except Exception as exc:
            result["sources"][source] = {"error": f"{type(exc).__name__}: {exc}"}
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    controlled = [normalize_row(row) for row in load_jsonl(CONTROLLED_ROWS)]
    web_heldout = [normalize_row(row) for row in load_jsonl(WEB_HELDOUT)]
    rowsets = {
        "controlled_fail_to_pass_support": controlled,
        "web_heldout": web_heldout,
    }
    results: dict[str, Any] = {}
    for runtime_name, runtime in RUNTIMES.items():
        results[runtime_name] = {}
        for rowset_name, rows in rowsets.items():
            results[runtime_name][rowset_name] = run_audit(runtime_name, runtime, rowset_name, rows)

    controlled_best = {
        runtime_name: {
            source: payload.get("correct")
            for source, payload in runtime_payload["controlled_fail_to_pass_support"]["sources"].items()
            if "correct" in payload
        }
        for runtime_name, runtime_payload in results.items()
    }
    diagnosis = []
    if controlled_best.get("stage11617_rejected", {}).get("encoder_option_retrieval_web_task_candidate_head") == 0:
        diagnosis.append("The trained Web task-candidate head scores its own controlled FAIL_TO_PASS support at 0/36.")
    if controlled_best.get("stage11617_rejected", {}).get("decoder_first_step", -1) > 0:
        diagnosis.append("Decoder token logits have some controlled-row signal, but the product scorer path is misaligned.")
    if controlled_best.get("stage11507_selected", {}).get("encoder_option_retrieval_verifier_conditioned", -1) > controlled_best.get("stage11617_rejected", {}).get("encoder_option_retrieval_web_task_candidate_head", -1):
        diagnosis.append("The new Web head is worse than the older retrieval-style scorer on controlled support, so the intervention is harmful.")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "device": str(DEVICE),
        "row_counts": {name: len(rows) for name, rows in rowsets.items()},
        "results": results,
        "controlled_support_correct_by_runtime_and_source": controlled_best,
        "diagnosis": diagnosis,
        "decision": "scorer_row_geometry_mismatch_confirmed" if diagnosis else "geometry_audit_inconclusive",
        "next_actions": [
            "Do not promote or reuse Stage11617.",
            "Do not train further on the same controlled rows with the Web task-candidate head until the support rows are learnable under a controlled overfit diagnostic.",
            "If continuing this lane, first run a head-only overfit sanity check on only the 36 controlled rows and evaluate the same 36 rows; if it cannot exceed chance, repair candidate feature/target metadata before any heldout run.",
            "If the overfit sanity check succeeds but heldout remains poor, materialize more diverse Llama/OpenHands FAIL_TO_PASS roots before promotion attempts.",
        ],
        "source_artifacts": {
            "controlled_rows": rel(CONTROLLED_ROWS),
            "web_heldout": rel(WEB_HELDOUT),
            **{f"runtime_{name}": rel(path) for name, path in RUNTIMES.items()},
        },
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    compact = {
        runtime_name: {
            rowset_name: {
                source: payload.get("correct", payload.get("error"))
                for source, payload in rowset_payload["sources"].items()
            }
            for rowset_name, rowset_payload in runtime_payload.items()
        }
        for runtime_name, runtime_payload in results.items()
    }
    print(json.dumps({"decision": summary["decision"], "diagnosis": diagnosis, "compact": compact}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
