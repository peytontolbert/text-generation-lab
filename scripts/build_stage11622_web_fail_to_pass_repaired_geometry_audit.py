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
STAGE = 11622
NAME = "stage11622_web_fail_to_pass_repaired_geometry_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_fail_to_pass_repaired_geometry_audit.json"

REPAIRED_ROWS = ART / "stage11621_web_fail_to_pass_row_geometry_repair/web_fail_to_pass_geometry_repaired_train_support.jsonl"
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
        if isinstance(opt, dict) and opt.get("label"):
            out[str(opt.get("label"))] = str(opt.get("semantic_role") or opt.get("value") or "")
    return out


def summarize(card: dict[str, Any], rows_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    target_roles: Counter[str] = Counter()
    predicted_roles: Counter[str] = Counter()
    correct_by_task: Counter[str] = Counter()
    total_by_task: Counter[str] = Counter()
    misses = []
    for row_card in card.get("row_cards") or []:
        row = rows_by_id.get(str(row_card.get("row_id") or ""), {})
        roles = option_role_by_label(row)
        target = str(row_card.get("bounded_choice_target_label") or "")
        predicted = str(row_card.get("constrained_choice_top1_label") or "")
        task = str(row.get("task_type") or "unknown")
        target_role = roles.get(target, "")
        predicted_role = roles.get(predicted, "")
        target_roles[target_role] += 1
        predicted_roles[predicted_role] += 1
        total_by_task[task] += 1
        if row_card.get("constrained_choice_match") is True:
            correct_by_task[task] += 1
        else:
            misses.append({
                "row_id": row_card.get("row_id"),
                "task_type": task,
                "target": target,
                "predicted": predicted,
                "target_role": target_role,
                "predicted_role": predicted_role,
                "full_vocab_top1_text": row_card.get("full_vocab_top1_text"),
                "target_rank_full_vocab": row_card.get("target_rank_full_vocab"),
            })
    return {
        "rows": card.get("rows"),
        "correct": card.get("constrained_choice_correct"),
        "accuracy": card.get("constrained_choice_top1_accuracy"),
        "coverage": card.get("constrained_choice_coverage"),
        "target_roles": dict(target_roles),
        "predicted_roles": dict(predicted_roles),
        "correct_by_task": dict(correct_by_task),
        "total_by_task": dict(total_by_task),
        "misses": misses,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [normalize_row(row) for row in load_jsonl(REPAIRED_ROWS)]
    rows_by_id = {str(row.get("row_id")): row for row in rows}
    results: dict[str, Any] = {}
    for runtime_name, runtime in RUNTIMES.items():
        model, tokenizer, init_card = load_runtime(runtime)
        results[runtime_name] = {"runtime_initialization": init_card, "sources": {}}
        for source in SOURCES:
            try:
                card = _write_bounded_choice_eval_audit(
                    OUT / runtime_name / source,
                    model=model,
                    rows=rows,
                    tokenizer=tokenizer,
                    max_encoder_tokens=768,
                    max_decoder_tokens=16,
                    split_name=f"repaired_{source}",
                    bounded_choice_aux_source=source,
                    eval_batch_size=8,
                )
                results[runtime_name]["sources"][source] = summarize(card, rows_by_id)
            except Exception as exc:
                results[runtime_name]["sources"][source] = {"error": f"{type(exc).__name__}: {exc}"}
    compact = {
        runtime: {source: payload.get("correct", payload.get("error")) for source, payload in data["sources"].items()}
        for runtime, data in results.items()
    }
    selected_base = compact.get("stage11507_selected", {}).get("encoder_option_retrieval_evidence_judgment_head")
    repaired_is_learnable_enough = isinstance(selected_base, int) and selected_base > 0
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "device": str(DEVICE),
        "row_count": len(rows),
        "results": results,
        "compact": compact,
        "decision": "repaired_rows_are_measurable_but_need_guarded_overfit_diagnostic" if repaired_is_learnable_enough else "repaired_rows_still_not_product_scorer_measurable",
        "claim_boundary": [
            "This is a scorer geometry audit, not a training result.",
            "Rows remain controlled bug-injection train support only.",
        ],
        "source_artifacts": {
            "repaired_rows": rel(REPAIRED_ROWS),
            **{f"runtime_{name}": rel(path) for name, path in RUNTIMES.items()},
        },
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "compact": compact}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
