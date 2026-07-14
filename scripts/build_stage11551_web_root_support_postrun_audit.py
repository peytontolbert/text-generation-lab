#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
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
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit

ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11551
NAME = "stage11551_web_root_support_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_root_support_postrun_audit.json"

RUNTIME = ART / "stage11550_web_root_support_from_stage11507_probe/runtime_model/runtime_model_bundle.json"
REQUEST = ART / "stage11550_web_root_support_from_stage11507_probe_request/web_root_support_from_stage11507_probe_request.json"
FILTERED_VALIDATION = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl"
FILTERED_STRICT = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
OLD_VALIDATION = ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl"
OLD_STRICT = ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL = ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl"
WEB_HELDOUT = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"
WEB_TRAIN = ART / "stage11550_web_root_support_from_stage11507_probe_request/web_root_support_from_stage11507_probe_manifest.jsonl"
GEMMA_WEB = ART / "stage11549_web_root_heldout_same_manifest_gemma_comparison/web_root_heldout_gemma_rows.jsonl"
BASE_WEB = SUMMARIES / "stage11548_web_root_heldout_stage11507_score_audit.json"
BASE_FRONTIER = SUMMARIES / "stage11508_preservation_strengthened_evidence_judgment_postrun_audit.json"

PRODUCT_SCORER = "encoder_option_retrieval_evidence_judgment_head"
SCORERS = [
    PRODUCT_SCORER,
    "encoder_option_retrieval",
    "encoder_option_retrieval_semantic_candidate_head",
    "decoder_first_step",
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


def load_json_opt(path: Path) -> Any:
    return load_json(path) if path.exists() else {}


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
        out["target"] = {
            "decoder_text": out.get("decoder_text"),
            "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text"),
        }
    return out


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


def metric_from_card(card: dict[str, Any], rows_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    row_cards = []
    misses = []
    for row in card.get("row_cards") or []:
        original = rows_by_id.get(str(row.get("row_id"))) or {}
        item = {
            "row_id": row.get("row_id"),
            "root_id": original.get("root_id"),
            "repo_family": original.get("repo_family"),
            "task_type": original.get("task_type"),
            "target": row.get("bounded_choice_target_label"),
            "predicted": row.get("constrained_choice_top1_label"),
            "correct": row.get("constrained_choice_match"),
            "full_vocab_top1_text": row.get("full_vocab_top1_text"),
            "target_rank_full_vocab": row.get("target_rank_full_vocab"),
        }
        row_cards.append(item)
        if row.get("constrained_choice_match") is not True:
            misses.append(item)
    return {
        "rows": card.get("rows"),
        "correct": card.get("constrained_choice_correct"),
        "scored_rows": card.get("constrained_choice_rows"),
        "unscored_rows": card.get("constrained_choice_unscored_rows"),
        "coverage": card.get("constrained_choice_coverage"),
        "accuracy": card.get("constrained_choice_top1_accuracy"),
        "coverage_corrected_accuracy": card.get("constrained_choice_coverage_corrected_top1_accuracy"),
        "misses": misses,
        "row_cards": row_cards,
    }


def group_metric(row_cards: list[dict[str, Any]], group: str) -> dict[str, dict[str, Any]]:
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"rows": 0, "correct": 0})
    for row in row_cards:
        key = str(row.get(group) or "unknown")
        buckets[key]["rows"] += 1
        if row.get("correct") is True:
            buckets[key]["correct"] += 1
    return {key: {**value, "accuracy": value["correct"] / value["rows"] if value["rows"] else 0.0} for key, value in sorted(buckets.items())}


def score(model: Any, tokenizer: Any, rows: list[dict[str, Any]], split: str, scorer: str) -> dict[str, Any]:
    rows_by_id = {str(row.get("row_id")): row for row in rows}
    card = _write_bounded_choice_eval_audit(
        OUT,
        model=model,
        rows=rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=16,
        split_name=f"{split}_{scorer}",
        bounded_choice_aux_source=scorer,
        eval_batch_size=8,
    )
    metric = metric_from_card(card, rows_by_id)
    metric["by_repo_family"] = group_metric(metric["row_cards"], "repo_family")
    metric["by_task_type"] = group_metric(metric["row_cards"], "task_type")
    return metric


def gemma_metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    correct = sum(1 for row in rows if row.get("gemma12b_correct") is True)
    return {"rows": len(rows), "correct": correct, "accuracy": correct / len(rows) if rows else 0.0}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rowsets = {
        "filtered_validation": [normalize_row(row) for row in load_jsonl(FILTERED_VALIDATION)],
        "filtered_strict": [normalize_row(row) for row in load_jsonl(FILTERED_STRICT)],
        "old_canary_validation": [normalize_row(row) for row in load_jsonl(OLD_VALIDATION)],
        "old_canary_strict": [normalize_row(row) for row in load_jsonl(OLD_STRICT)],
        "residual_bank": [normalize_row(row) for row in load_jsonl(RESIDUAL)],
        "web_train_support": [normalize_row(row) for row in load_jsonl(WEB_TRAIN) if row.get("split") == "train"],
        "web_heldout": [normalize_row(row) for row in load_jsonl(WEB_HELDOUT)],
    }
    model, tokenizer, init_card = load_runtime()
    scored = {scorer: {name: score(model, tokenizer, rows, name, scorer) for name, rows in rowsets.items()} for scorer in SCORERS}
    product = scored[PRODUCT_SCORER]
    gemma_web = gemma_metric(load_jsonl(GEMMA_WEB))
    base_web = load_json_opt(BASE_WEB).get("hundred_m") or {}
    gates = {
        "filtered_strict_preserved_22_of_22": product["filtered_strict"]["correct"] == 22,
        "old_canary_strict_preserved_23_of_23": product["old_canary_strict"]["correct"] == 23,
        "filtered_validation_at_least_20_of_22": (product["filtered_validation"]["correct"] or 0) >= 20,
        "old_validation_at_least_21_of_23": (product["old_canary_validation"]["correct"] or 0) >= 21,
        "residual_at_least_stage11507_7_of_10": (product["residual_bank"]["correct"] or 0) >= 7,
        "web_heldout_improves_over_stage11507_35_of_66": (product["web_heldout"]["correct"] or 0) > 35,
        "web_heldout_beats_gemma_52_of_66": (product["web_heldout"]["correct"] or 0) > gemma_web["correct"],
        "web_heldout_full_coverage": product["web_heldout"]["coverage"] == 1.0,
    }
    promoted = (
        gates["filtered_strict_preserved_22_of_22"]
        and gates["old_canary_strict_preserved_23_of_23"]
        and gates["filtered_validation_at_least_20_of_22"]
        and gates["old_validation_at_least_21_of_23"]
        and gates["residual_at_least_stage11507_7_of_10"]
        and gates["web_heldout_beats_gemma_52_of_66"]
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "web_root_support_probe_promoted" if promoted else "web_root_support_probe_diagnostic_only",
        "runtime_initialization": init_card,
        "runtime_weights_sha256": init_card.get("weights_sha256"),
        "request": load_json_opt(REQUEST),
        "product_scorer": PRODUCT_SCORER,
        "product": {name: {key: value for key, value in metric.items() if key != "row_cards"} for name, metric in product.items()},
        "scored": {scorer: {name: {key: value for key, value in metric.items() if key != "row_cards"} for name, metric in split_scores.items()} for scorer, split_scores in scored.items()},
        "comparison": {
            "stage11507_web_correct": base_web.get("correct"),
            "stage11550_web_correct": product["web_heldout"]["correct"],
            "stage11550_web_accuracy": product["web_heldout"]["accuracy"],
            "gemma_web_correct": gemma_web["correct"],
            "gemma_web_accuracy": gemma_web["accuracy"],
            "delta_stage11550_minus_gemma": (product["web_heldout"]["accuracy"] or 0.0) - gemma_web["accuracy"],
        },
        "gates": gates,
        "claim_boundary": [
            "Diagnostic Web support probe. Do not promote unless all gates pass.",
            "Train and heldout are root-disjoint, but repo-family overlap exists; this is not repo-family-heldout Web generalization.",
            "This remains compact bounded-choice maintainer scoring, not freeform repair.",
        ],
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME),
            "request": rel(REQUEST),
            "web_heldout": rel(WEB_HELDOUT),
            "gemma_web": rel(GEMMA_WEB),
            "stage11507_web": rel(BASE_WEB),
            "stage11507_frontier": rel(BASE_FRONTIER),
        },
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "comparison": summary["comparison"], "gates": gates, "product": summary["product"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
