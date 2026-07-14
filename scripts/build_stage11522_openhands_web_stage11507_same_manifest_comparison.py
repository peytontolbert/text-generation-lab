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
STAGE = 11522
NAME = "stage11522_openhands_web_stage11507_same_manifest_comparison"
OUT = ART / NAME
SUMMARY = OUT / "openhands_web_stage11507_same_manifest_comparison.json"

RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
WEB_ROWS = ART / "stage11390_openhands_unit_verifier_heldout_candidate_rows/openhands_unit_verifier_heldout_candidate_rows.jsonl"
GEMMA_ROWS = ART / "stage11392_openhands_web_same_manifest_gemma_comparison/openhands_web_gemma_rows.jsonl"
STAGE11520 = SUMMARIES / "stage11520_provenance_aware_smoke_admission_audit.json"
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


def metric_from_card(card: dict[str, Any]) -> dict[str, Any]:
    row_cards = card.get("row_cards") or []
    misses = []
    scored_rows = []
    for row in row_cards:
        scored_rows.append(
            {
                "row_id": row.get("row_id"),
                "task_type": row.get("task_type"),
                "language_family": row.get("language_family"),
                "target": row.get("bounded_choice_target_label"),
                "predicted": row.get("constrained_choice_top1_label"),
                "correct": row.get("constrained_choice_match"),
                "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                "target_rank_full_vocab": row.get("target_rank_full_vocab"),
            }
        )
        if row.get("constrained_choice_match") is not True:
            misses.append(scored_rows[-1])
    return {
        "rows": card.get("rows"),
        "correct": card.get("constrained_choice_correct"),
        "scored_rows": card.get("constrained_choice_rows"),
        "unscored_rows": card.get("constrained_choice_unscored_rows"),
        "coverage": card.get("constrained_choice_coverage"),
        "accuracy": card.get("constrained_choice_top1_accuracy"),
        "coverage_corrected_accuracy": card.get("constrained_choice_coverage_corrected_top1_accuracy"),
        "misses": misses,
        "row_cards": scored_rows,
    }


def score_100m(model: Any, tokenizer: Any, rows: list[dict[str, Any]], scorer: str) -> dict[str, Any]:
    card = _write_bounded_choice_eval_audit(
        OUT,
        model=model,
        rows=rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=16,
        split_name=f"openhands_web_{scorer}",
        bounded_choice_aux_source=scorer,
        eval_batch_size=8,
    )
    return metric_from_card(card)


def gemma_metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    correct = sum(1 for row in rows if row.get("gemma12b_correct") is True)
    by_task: dict[str, dict[str, int]] = {}
    misses = []
    for row in rows:
        task = str(row.get("task_type") or "unknown")
        bucket = by_task.setdefault(task, {"rows": 0, "correct": 0})
        bucket["rows"] += 1
        if row.get("gemma12b_correct") is True:
            bucket["correct"] += 1
        else:
            misses.append(
                {
                    "row_id": row.get("row_id"),
                    "task_type": task,
                    "target": row.get("target_text"),
                    "predicted": row.get("gemma12b_predicted_label"),
                    "raw_output": row.get("gemma12b_raw_output"),
                }
            )
    for bucket in by_task.values():
        bucket["accuracy"] = bucket["correct"] / bucket["rows"] if bucket["rows"] else 0.0
    return {
        "rows": len(rows),
        "correct": correct,
        "accuracy": correct / len(rows) if rows else 0.0,
        "misses": misses,
        "by_task_type": by_task,
    }


def by_task_from_100m(row_cards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_task: dict[str, dict[str, int]] = {}
    for row in row_cards:
        task = str(row.get("task_type") or "unknown")
        bucket = by_task.setdefault(task, {"rows": 0, "correct": 0})
        bucket["rows"] += 1
        if row.get("correct") is True:
            bucket["correct"] += 1
    return {
        task: {**bucket, "accuracy": bucket["correct"] / bucket["rows"] if bucket["rows"] else 0.0}
        for task, bucket in sorted(by_task.items())
    }


def validate_same_manifest(web_rows: list[dict[str, Any]], gemma_rows: list[dict[str, Any]]) -> dict[str, Any]:
    web_ids = [str(row.get("row_id")) for row in web_rows]
    gemma_ids = [str(row.get("row_id")) for row in gemma_rows]
    return {
        "web_rows": len(web_ids),
        "gemma_rows": len(gemma_ids),
        "same_row_ids_in_order": web_ids == gemma_ids,
        "missing_from_gemma": sorted(set(web_ids) - set(gemma_ids)),
        "extra_in_gemma": sorted(set(gemma_ids) - set(web_ids)),
    }


def anti_cheat_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = [
        "deterministic_option_shuffle",
        "executed_verifier_output_attached",
        "gold_value_not_used_as_label",
        "not_from_sourcebot_or_mcp_family",
        "not_train_support",
        "source_and_verifier_snippets_visible",
        "target_label_not_visible_before_options",
    ]
    counts = {key: 0 for key in keys}
    for row in rows:
        anti = row.get("anti_cheat") or {}
        for key in keys:
            if anti.get(key) is True:
                counts[key] += 1
    return {"rows": len(rows), "true_counts": counts, "all_true": all(value == len(rows) for value in counts.values())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    web_rows = load_jsonl(WEB_ROWS)
    gemma_rows = load_jsonl(GEMMA_ROWS)
    same_manifest = validate_same_manifest(web_rows, gemma_rows)
    model, tokenizer, init_card = load_runtime()
    scorer_results = {scorer: score_100m(model, tokenizer, web_rows, scorer) for scorer in SCORERS}
    hundred_m = scorer_results[PRODUCT_SCORER]
    gemma = gemma_metric(gemma_rows)
    for result in scorer_results.values():
        result["by_task_type"] = by_task_from_100m(result.get("row_cards") or [])
    gates = {
        "same_manifest_rows": same_manifest["same_row_ids_in_order"],
        "hundred_m_full_coverage": hundred_m.get("coverage") == 1.0,
        "hundred_m_beats_gemma": (hundred_m.get("correct") or 0) > gemma["correct"],
        "all_rows_web_language_family": all(row.get("language_family") == "web_js_ts_html" for row in web_rows),
        "anti_cheat_all_expected_flags_true": anti_cheat_summary(web_rows)["all_true"],
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": all(gates.values()),
        "decision": "web_source_heldout_standalone_smoke_win" if all(gates.values()) else "web_source_heldout_standalone_smoke_incomplete_or_failed",
        "runtime_initialization": init_card,
        "runtime_weights_sha256": init_card.get("weights_sha256"),
        "product_scorer": PRODUCT_SCORER,
        "scorer_results": {
            scorer: {key: value for key, value in result.items() if key != "row_cards"}
            for scorer, result in scorer_results.items()
        },
        "eval_device": str(DEVICE),
        "same_manifest": same_manifest,
        "hundred_m": {
            key: value
            for key, value in hundred_m.items()
            if key != "row_cards"
        },
        "gemma12b_existing_artifact": gemma,
        "comparison": {
            "hundred_m_correct": hundred_m.get("correct"),
            "hundred_m_rows": hundred_m.get("rows"),
            "hundred_m_accuracy": hundred_m.get("accuracy"),
            "gemma12b_correct": gemma["correct"],
            "gemma12b_rows": gemma["rows"],
            "gemma12b_accuracy": gemma["accuracy"],
            "delta_accuracy": (hundred_m.get("accuracy") or 0.0) - gemma["accuracy"],
        },
        "gates": gates,
        "anti_cheat": anti_cheat_summary(web_rows),
        "stage11520_context": load_json_opt(STAGE11520).get("decision"),
        "claim_boundary": [
            "This is a Web/JS/TS/HTML-only OpenHands executed-heldout candidate standalone smoke comparison.",
            "Gemma outputs are reused from Stage11392; this script does not start Ollama.",
            "This does not establish the multilingual source-heldout smoke gate, because Python, C/C++, and Rust rows remain unavailable or blocked, and OpenHands is one Web repo family.",
            "This is compact bounded-choice maintainer scoring, not broad freeform repair or executable patch synthesis.",
        ],
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME),
            "web_rows": rel(WEB_ROWS),
            "gemma_rows": rel(GEMMA_ROWS),
            "stage11520": rel(STAGE11520),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "bounded_choice_eval_audit_dir": rel(OUT),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": summary["decision"],
                "passed": summary["passed"],
                "comparison": summary["comparison"],
                "gates": gates,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
