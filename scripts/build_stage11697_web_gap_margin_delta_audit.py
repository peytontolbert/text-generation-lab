#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.training_loop import (
    _bounded_choice_option_logits,
    _move_manifest_batch,
    build_batch,
)

BASE = ROOT / "scripts/build_stage11688_routed_web_identity_scorer_audit.py"
spec = importlib.util.spec_from_file_location("stage11688_base_for_11697", BASE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to load {BASE}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11697_web_gap_margin_delta_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_gap_margin_delta_audit.json"
ROW_CARDS = OUT / "web_gap_margin_delta_rows.jsonl"

BASELINE_RUNTIME = ART / "stage11685_counterfactual_identity_semantic_head_fixed_probe/runtime_model/runtime_model_bundle.json"
PROBE_RUNTIME = ART / "stage11695_web_identity_gap_topup_probe/runtime_model/runtime_model_bundle.json"
BRIDGED_ROWS = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridged_rows.jsonl"
GAP_ROWS = ART / "stage11692_web_bridged_miss_family_audit/web_bridged_gemma_margin_rows.jsonl"

SCORER = "encoder_option_retrieval_semantic_candidate_head"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def target_label(row: dict[str, Any]) -> str:
    return str(row.get("bounded_choice_target_label") or row.get("target_text") or (row.get("target") or {}).get("bounded_choice_target_label") or "").strip()


def option_role(row: dict[str, Any], label: str) -> str:
    for opt in row.get("opaque_options") or []:
        if isinstance(opt, dict) and str(opt.get("label")) == str(label):
            obj = opt.get("canonical_candidate_object") if isinstance(opt.get("canonical_candidate_object"), dict) else {}
            semantic = opt.get("semantic_candidate") if isinstance(opt.get("semantic_candidate"), dict) else {}
            return str(opt.get("role") or obj.get("role") or semantic.get("role") or "unknown")
    return "missing"


def option_value(row: dict[str, Any], label: str) -> str:
    for opt in row.get("opaque_options") or []:
        if isinstance(opt, dict) and str(opt.get("label")) == str(label):
            obj = opt.get("canonical_candidate_object") if isinstance(opt.get("canonical_candidate_object"), dict) else {}
            return str(obj.get("value") or opt.get("text") or opt.get("value") or "")
    return ""


def load_runtime(runtime_path: Path) -> tuple[Any, Any, dict[str, Any], dict[str, Any]]:
    old = base.base.RUNTIME
    try:
        base.base.RUNTIME = runtime_path
        return base.load_runtime(runtime_path)
    finally:
        base.base.RUNTIME = old


def score_rows(runtime_path: Path, rows: list[dict[str, Any]], split_name: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    model, tokenizer, init, bundle = load_runtime(runtime_path)
    model_device = next(model.parameters()).device
    scored: list[dict[str, Any]] = []
    for row in rows:
        nrow = base.base.normalize_row(row)
        batch = build_batch([nrow], max_encoder_tokens=768, max_decoder_tokens=16, tokenizer=tokenizer)
        batch = _move_manifest_batch(batch, model_device)
        with torch.no_grad():
            out = model(batch.input_ids, batch.decoder_input_ids)
            first_step = out["decoder_logits"][0, 0, :]
            pooled = out.get("pooled")
            pooled_row = pooled[0] if isinstance(pooled, torch.Tensor) else None
            option_logits, option_pairs, _ = _bounded_choice_option_logits(
                row=nrow,
                tokenizer=tokenizer,
                source=SCORER,
                first_step_logits_row=first_step,
                pooled_row=pooled_row,
                model=model,
                untied_head=getattr(model, "bounded_choice_probe_head", None),
            )
        target = target_label(nrow)
        if option_logits is None or not option_pairs:
            scored.append({"row_id": nrow.get("row_id"), "split": split_name, "scored": False, "target_label": target})
            continue
        logits = option_logits.detach().float().cpu()
        pairs = [(str(label), int(token_id)) for label, token_id in option_pairs]
        order = torch.argsort(logits, descending=True)
        pred_idx = int(order[0].item())
        pred_label = pairs[pred_idx][0]
        target_idx = next((idx for idx, (label, _tid) in enumerate(pairs) if label == target), None)
        top2_idx = int(order[1].item()) if order.numel() > 1 else pred_idx
        target_logit = float(logits[target_idx].item()) if target_idx is not None else None
        pred_logit = float(logits[pred_idx].item())
        top_wrong_logit = None
        for idx_tensor in order:
            idx = int(idx_tensor.item())
            if idx != target_idx:
                top_wrong_logit = float(logits[idx].item())
                break
        top_k = [
            {
                "label": pairs[int(idx.item())][0],
                "logit": float(logits[int(idx.item())].item()),
                "role": option_role(nrow, pairs[int(idx.item())][0]),
                "value": option_value(nrow, pairs[int(idx.item())][0]),
            }
            for idx in order[: min(5, order.numel())]
        ]
        scored.append(
            {
                "row_id": nrow.get("row_id"),
                "split": split_name,
                "scored": True,
                "target_label": target,
                "target_role": option_role(nrow, target),
                "target_value": option_value(nrow, target),
                "predicted_label": pred_label,
                "predicted_role": option_role(nrow, pred_label),
                "predicted_value": option_value(nrow, pred_label),
                "correct": pred_label == target,
                "target_logit": target_logit,
                "predicted_logit": pred_logit,
                "top_wrong_logit": top_wrong_logit,
                "target_minus_predicted_margin": None if target_logit is None else target_logit - pred_logit,
                "target_minus_top_wrong_margin": None if target_logit is None or top_wrong_logit is None else target_logit - top_wrong_logit,
                "top1_label": pred_label,
                "top2_label": pairs[top2_idx][0],
                "top_k": top_k,
            }
        )
    return scored, {"init": init, "bundle": bundle}


def mean(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    bridged_by_id = {str(row.get("row_id")): row for row in load_jsonl(BRIDGED_ROWS)}
    gap_ids = [str(row.get("row_id")) for row in load_jsonl(GAP_ROWS)]
    rows = [bridged_by_id[row_id] for row_id in gap_ids if row_id in bridged_by_id]
    baseline, baseline_meta = score_rows(BASELINE_RUNTIME, rows, "stage11685_baseline")
    probe, probe_meta = score_rows(PROBE_RUNTIME, rows, "stage11695_probe")
    probe_by_id = {str(row["row_id"]): row for row in probe}
    joined: list[dict[str, Any]] = []
    for base_row in baseline:
        row_id = str(base_row["row_id"])
        probe_row = probe_by_id.get(row_id, {})
        delta_margin = None
        if base_row.get("target_minus_top_wrong_margin") is not None and probe_row.get("target_minus_top_wrong_margin") is not None:
            delta_margin = float(probe_row["target_minus_top_wrong_margin"]) - float(base_row["target_minus_top_wrong_margin"])
        joined.append(
            {
                "row_id": row_id,
                "task_type": bridged_by_id[row_id].get("task_type") if row_id in bridged_by_id else None,
                "repo_id": bridged_by_id[row_id].get("repo_id") if row_id in bridged_by_id else None,
                "target_label": base_row.get("target_label"),
                "target_role": base_row.get("target_role"),
                "baseline_predicted_label": base_row.get("predicted_label"),
                "baseline_predicted_role": base_row.get("predicted_role"),
                "baseline_correct": base_row.get("correct"),
                "baseline_target_minus_top_wrong_margin": base_row.get("target_minus_top_wrong_margin"),
                "probe_predicted_label": probe_row.get("predicted_label"),
                "probe_predicted_role": probe_row.get("predicted_role"),
                "probe_correct": probe_row.get("correct"),
                "probe_target_minus_top_wrong_margin": probe_row.get("target_minus_top_wrong_margin"),
                "target_margin_delta": delta_margin,
                "prediction_changed": base_row.get("predicted_label") != probe_row.get("predicted_label"),
                "baseline_top_k": base_row.get("top_k"),
                "probe_top_k": probe_row.get("top_k"),
            }
        )
    write_jsonl(ROW_CARDS, joined)
    deltas = [row["target_margin_delta"] for row in joined if row.get("target_margin_delta") is not None]
    improved = [row for row in joined if row.get("target_margin_delta") is not None and row["target_margin_delta"] > 0]
    worsened = [row for row in joined if row.get("target_margin_delta") is not None and row["target_margin_delta"] < 0]
    flipped_correct = [row for row in joined if row.get("baseline_correct") is not True and row.get("probe_correct") is True]
    flipped_wrong = [row for row in joined if row.get("baseline_correct") is True and row.get("probe_correct") is not True]
    gates = {
        "all_13_rows_scored": len(joined) == 13 and all(row.get("probe_target_minus_top_wrong_margin") is not None for row in joined),
        "any_prediction_changed": any(row.get("prediction_changed") for row in joined),
        "any_correct_flip": len(flipped_correct) > 0,
        "mean_margin_improved": (mean(deltas) or 0.0) > 0.0,
        "at_least_half_rows_margin_improved": len(improved) >= 7,
    }
    if gates["any_correct_flip"]:
        decision = "stage11695_moved_web_gap_predictions"
    elif gates["mean_margin_improved"] or gates["at_least_half_rows_margin_improved"]:
        decision = "stage11695_moved_margins_without_top1_gain"
    else:
        decision = "stage11695_no_margin_or_prediction_progress"
    summary = {
        "stage": 11697,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "metrics": {
            "rows": len(joined),
            "baseline_correct": sum(1 for row in joined if row.get("baseline_correct") is True),
            "probe_correct": sum(1 for row in joined if row.get("probe_correct") is True),
            "prediction_changed_rows": sum(1 for row in joined if row.get("prediction_changed")),
            "correct_flips": len(flipped_correct),
            "wrong_flips": len(flipped_wrong),
            "margin_improved_rows": len(improved),
            "margin_worsened_rows": len(worsened),
            "mean_target_margin_delta": mean(deltas),
            "by_task": dict(Counter(str(row.get("task_type")) for row in joined).most_common()),
        },
        "gates": gates,
        "recommended_next": [
            "If margins did not move, stop adding same objective support rows; implement a verifier-transition/value-specific scorer head or listwise loss.",
            "If margins moved but top-1 did not flip, lower learning rate is not the issue; train a calibrated head against hard heldout-style analogues and track target-vs-top-wrong margin.",
            "Do not train on the 13 heldout margin rows.",
        ],
        "runtime": {
            "baseline_runtime": rel(BASELINE_RUNTIME),
            "baseline_weights_sha256": baseline_meta["bundle"].get("weights_sha256"),
            "probe_runtime": rel(PROBE_RUNTIME),
            "probe_weights_sha256": probe_meta["bundle"].get("weights_sha256"),
        },
        "source_artifacts": {"bridged_rows": rel(BRIDGED_ROWS), "gap_rows": rel(GAP_ROWS)},
        "outputs": {"summary": rel(SUMMARY), "row_cards": rel(ROW_CARDS)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "metrics": summary["metrics"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
