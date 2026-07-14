#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer, build_batch
from legacy_src.agentkernel_lite.training_loop import _bounded_choice_option_logits, _load_runtime_model_bundle

STAGE = 10431
NAME = "stage10431_reviewed_v27_saved_runtime_margin_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "reviewed_v27_saved_runtime_margin_audit.json"
ROW_JSONL = OUT_DIR / "reviewed_v27_saved_runtime_margin_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

STRICT_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_strict_eval.jsonl"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"
STRICT_AUDIT_JSON = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
EVAL_HACK_JSON = ROOT / "runs/local/artifacts/stage10429_reviewed_v27_eval_hacking_audit/reviewed_v27_eval_hacking_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_rows() -> list[dict[str, Any]]:
    rows = load_jsonl(STRICT_ROWS_JSONL)
    rows.sort(key=lambda row: str(row["row_id"]))
    return rows


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    model_config = load_json(Path(str(metadata["model_config"])))
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(model_config)
    model = AgentKernelLiteTransformerSeq2Seq(config)
    _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    model.eval()
    return model, tokenizer


def semantic_value_for_label(row: dict[str, Any], label: str) -> str | None:
    options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    for option in options:
        if str(option.get("label")) == label:
            return str(option.get("value"))
    return None


def prompt_target_leak(row: dict[str, Any]) -> bool:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    target_value = str((row.get("standalone_projection_source") or {}).get("gold_value") or "")
    body = prompt.split("\nOptions:\n", 1)[0]
    return bool(target_value and target_value in body)


def residual_family(row: dict[str, Any], predicted_semantic: str | None) -> str:
    task_type = str(row.get("task_type") or "")
    if predicted_semantic == "candidate_change_surface":
        if task_type == "evidence_citation":
            return "candidate_change_surface_attractor"
        return "candidate_change_surface_collapse"
    if task_type == "verifier_outcome":
        return "verifier_target_disambiguation"
    if task_type == "evidence_citation":
        return "evidence_support_disambiguation"
    return "other_semantic_miss"


def margin_band(value: float) -> str:
    if value < 0.02:
        return "very_low"
    if value < 0.05:
        return "low"
    if value < 0.15:
        return "medium"
    return "high"


def summary_for(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"rows": 0}
    margins = [float(row["margin_top1_minus_top2"]) for row in rows]
    return {
        "rows": len(rows),
        "correct_rows": sum(1 for row in rows if row["constrained_choice_match"]),
        "incorrect_rows": sum(1 for row in rows if not row["constrained_choice_match"]),
        "mean_margin": mean(margins),
        "min_margin": min(margins),
        "max_margin": max(margins),
        "rows_margin_lt_0_05": sum(1 for row in rows if row["margin_top1_minus_top2"] < 0.05),
        "rows_margin_lt_0_15": sum(1 for row in rows if row["margin_top1_minus_top2"] < 0.15),
    }


def score_row(model: AgentKernelLiteTransformerSeq2Seq, tokenizer: AgentKernelBPETokenizer, row: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    option_logits, option_pairs, skip_reason = _bounded_choice_option_logits(
        row=row,
        tokenizer=tokenizer,
        source="encoder_option_retrieval",
        first_step_logits_row=out["decoder_logits"][0, 0],
        pooled_row=out.get("pooled")[0] if isinstance(out.get("pooled"), torch.Tensor) else None,
        model=model,
        untied_head=getattr(model, "bounded_choice_probe_head", None),
    )
    if option_logits is None:
        raise RuntimeError(f"missing bounded choice logits for {row['row_id']}: {skip_reason}")
    probs = torch.softmax(option_logits.float(), dim=0)
    scored = []
    for idx, (label, _token_id) in enumerate(option_pairs):
        scored.append(
            {
                "label": label,
                "semantic_value": semantic_value_for_label(row, label),
                "logit": float(option_logits[idx].item()),
                "probability": float(probs[idx].item()),
            }
        )
    scored.sort(key=lambda item: item["logit"], reverse=True)
    top1 = scored[0]
    top2 = scored[1] if len(scored) > 1 else {"label": "", "semantic_value": None, "logit": 0.0, "probability": 0.0}
    predicted_semantic = top1["semantic_value"]
    result = {
        "row_id": str(row["row_id"]),
        "language_family": str(row.get("language_family") or ""),
        "task_type": str(row.get("task_type") or ""),
        "repo_family": str(row.get("repo_family") or ""),
        "selected_test_anchor": bool(row.get("selected_test_anchor")),
        "verifier_anchor": bool(row.get("verifier_anchor")),
        "abstention_heavy": bool(row.get("abstention_heavy")),
        "constrained_choice_match": bool(card.get("constrained_choice_match")),
        "predicted_label": str(top1["label"]),
        "predicted_semantic_value": predicted_semantic,
        "target_label": str(card.get("target_text") or row.get("decoder_text") or ""),
        "target_semantic_value": str((row.get("standalone_projection_source") or {}).get("gold_value") or ""),
        "top1_probability": float(top1["probability"]),
        "top2_probability": float(top2["probability"]),
        "margin_top1_minus_top2": float(top1["probability"] - top2["probability"]),
        "margin_band": margin_band(float(top1["probability"] - top2["probability"])),
        "top2_label": str(top2["label"]),
        "top2_semantic_value": top2["semantic_value"],
        "target_rank_full_vocab": card.get("target_rank_full_vocab"),
        "full_vocab_top1_text": card.get("full_vocab_top1_text"),
        "prompt_target_leak": prompt_target_leak(row),
        "scored_options": scored,
    }
    if not result["constrained_choice_match"]:
        result["residual_family"] = residual_family(row, predicted_semantic)
    return result


def main() -> None:
    rows = load_rows()
    strict_audit = load_json(STRICT_AUDIT_JSON)
    eval_hack = load_json(EVAL_HACK_JSON)
    card_by_row = {card["row_id"]: card for card in strict_audit["row_cards"]}
    model, tokenizer = load_runtime()

    row_cards = [score_row(model, tokenizer, row, card_by_row[str(row["row_id"])]) for row in rows]
    row_cards.sort(key=lambda row: (row["margin_top1_minus_top2"], row["row_id"]))
    residuals = [row for row in row_cards if not row["constrained_choice_match"]]

    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in row_cards:
        by_task[row["task_type"]].append(row)
        by_language[row["language_family"]].append(row)

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Saved-runtime margin and residual audit for the stage10422 reviewed-v2.7 strict_eval surface.",
            "Margins are computed with the same encoder_option_retrieval bounded-choice scorer used by the standalone probe.",
            "This is a diagnostic artifact for prioritizing fresh disjoint support and anti-cheat cleanup, not a new benchmark claim.",
        ],
        "source_artifacts": {
            "strict_rows": display(STRICT_ROWS_JSONL),
            "runtime_bundle": display(RUNTIME_BUNDLE),
            "strict_eval_audit": display(STRICT_AUDIT_JSON),
            "eval_hacking_audit": display(EVAL_HACK_JSON),
        },
        "summary": {
            "strict_rows": len(row_cards),
            "strict_accuracy": strict_audit["constrained_choice_top1_accuracy"],
            "strict_correct": sum(1 for row in row_cards if row["constrained_choice_match"]),
            "mean_margin": mean(row["margin_top1_minus_top2"] for row in row_cards),
            "rows_margin_lt_0_05": sum(1 for row in row_cards if row["margin_top1_minus_top2"] < 0.05),
            "rows_margin_lt_0_15": sum(1 for row in row_cards if row["margin_top1_minus_top2"] < 0.15),
            "residual_rows": len(residuals),
            "rows_with_prompt_target_leak": sum(1 for row in row_cards if row["prompt_target_leak"]),
            "eval_hack_prompt_target_leak_rate_all_rows": (eval_hack.get("prompt_leakage") or {}).get("prompt_contains_target_value_before_options_rate"),
        },
        "per_task": {task: summary_for(items) for task, items in sorted(by_task.items())},
        "per_language": {lang: summary_for(items) for lang, items in sorted(by_language.items())},
        "lowest_margin_rows": row_cards[:8],
        "residual_rows": residuals,
        "recommended_disjoint_support_targets": [
            {
                "row_id": row["row_id"],
                "language_family": row["language_family"],
                "task_type": row["task_type"],
                "residual_family": row["residual_family"],
                "prompt_target_leak": row["prompt_target_leak"],
                "recommended_support_direction": (
                    "fresh verifier target disambiguation roots with similar selected-test competition"
                    if row["residual_family"] == "verifier_target_disambiguation"
                    else "fresh evidence-citation contrast roots separating candidate surface from stronger visible support"
                ),
            }
            for row in residuals
        ],
        "notes": [
            "Current strict misses should be treated as semantic residuals, not formatting failures.",
            "Rows with prompt target leakage need anti-cheat cleanup even when the model is correct.",
            "Fresh heldout roots are a better next lever than same-surface replay for the remaining residuals.",
        ],
        "outputs": {
            "audit_json": display(AUDIT_JSON),
            "row_cards": display(ROW_JSONL),
        },
    }

    write_json(AUDIT_JSON, audit)
    write_jsonl(ROW_JSONL, row_cards)
    write_json(SUMMARY, audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
