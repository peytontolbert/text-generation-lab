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
STAGE = 11548
NAME = "stage11548_web_root_heldout_stage11507_score_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_root_heldout_stage11507_score_audit.json"
ROWS_OUT = OUT / "web_root_heldout_rows.jsonl"

RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
ROW_SOURCES = {
    "llama_stack_ui": ART / "stage11361_web_llama_stack_executed_heldout_rows/web_llama_stack_executed_heldout_rows.jsonl",
    "openhands_frontend": ART / "stage11390_openhands_unit_verifier_heldout_candidate_rows/openhands_unit_verifier_heldout_candidate_rows.jsonl",
    "mcp_typescript_sdk": ART / "stage11541_mcp_typescript_sdk_web_gold_heldout_rows/mcp_typescript_sdk_web_gold_heldout_rows.jsonl",
    "sep_automation": ART / "stage11543_sep_automation_web_gold_heldout_rows/sep_automation_web_gold_heldout_rows.jsonl",
}
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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def load_runtime() -> tuple[Any, Any, dict[str, Any]]:
    bundle = read_json(RUNTIME)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(read_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME, model=model)
    model.to(DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def metric_from_card(card: dict[str, Any], rows_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    row_cards = card.get("row_cards") or []
    misses = []
    scored_rows = []
    for row in row_cards:
        original = rows_by_id.get(str(row.get("row_id"))) or {}
        out = {
            "row_id": row.get("row_id"),
            "root_id": original.get("root_id"),
            "repo_family": original.get("repo_family"),
            "task_type": original.get("task_type"),
            "language_family": original.get("language_family"),
            "target": row.get("bounded_choice_target_label"),
            "predicted": row.get("constrained_choice_top1_label"),
            "correct": row.get("constrained_choice_match"),
            "full_vocab_top1_text": row.get("full_vocab_top1_text"),
            "target_rank_full_vocab": row.get("target_rank_full_vocab"),
        }
        scored_rows.append(out)
        if row.get("constrained_choice_match") is not True:
            misses.append(out)
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


def group_metric(row_cards: list[dict[str, Any]], group: str) -> dict[str, dict[str, Any]]:
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"rows": 0, "correct": 0})
    for row in row_cards:
        key = str(row.get(group) or "unknown")
        buckets[key]["rows"] += 1
        if row.get("correct") is True:
            buckets[key]["correct"] += 1
    return {
        key: {**value, "accuracy": value["correct"] / value["rows"] if value["rows"] else 0.0}
        for key, value in sorted(buckets.items())
    }


def anti_cheat(rows: list[dict[str, Any]]) -> dict[str, Any]:
    root_ids = [str(row.get("root_id") or "") for row in rows]
    repo_families = [str(row.get("repo_family") or "") for row in rows]
    singletons = [row.get("row_id") for row in rows if len(row.get("opaque_options") or []) < 2]
    missing_shuffle = [
        row.get("row_id")
        for row in rows
        if (row.get("anti_cheat") or {}).get("deterministic_option_shuffle") is not True
    ]
    visible_gold_flags = [
        row.get("row_id")
        for row in rows
        if (row.get("anti_cheat") or {}).get("target_label_not_visible_before_options") is False
        or (row.get("anti_cheat") or {}).get("semantic_target_not_visible_before_options") is False
    ]
    return {
        "rows": len(rows),
        "unique_roots": len(set(root_ids)),
        "repo_families": sorted(set(repo_families)),
        "singletons": singletons,
        "missing_deterministic_option_shuffle": missing_shuffle,
        "visible_gold_flags": visible_gold_flags,
    }


def load_rows() -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows = []
    source_counts = {}
    seen = set()
    for source, path in ROW_SOURCES.items():
        source_rows = read_jsonl(path)
        source_counts[source] = len(source_rows)
        for row in source_rows:
            row_id = str(row.get("row_id"))
            if row_id in seen:
                raise ValueError(f"duplicate row_id: {row_id}")
            seen.add(row_id)
            out = dict(row)
            out["web_heldout_source"] = source
            out.setdefault("prompt_text", out.get("input_text") or "")
            out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or "")
            out.setdefault("expected_enabled_loss", "bounded_choice")
            out.setdefault("loss_mask", "decoder")
            standalone = dict(out.get("standalone_projection_source") or {})
            standalone.setdefault("opaque_options", out.get("opaque_options") or [])
            out["standalone_projection_source"] = standalone
            if "target" not in out or not isinstance(out.get("target"), dict):
                out["target"] = {
                    "decoder_text": out.get("decoder_text"),
                    "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text"),
                }
            rows.append(out)
    return rows, source_counts


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, source_counts = load_rows()
    rows_by_id = {str(row.get("row_id")): row for row in rows}
    write_jsonl(ROWS_OUT, rows)
    model, tokenizer, init_card = load_runtime()
    scorer_results = {}
    for scorer in SCORERS:
        card = _write_bounded_choice_eval_audit(
            OUT,
            model=model,
            rows=rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=16,
            split_name=f"web_root_heldout_{scorer}",
            bounded_choice_aux_source=scorer,
            eval_batch_size=8,
        )
        metric = metric_from_card(card, rows_by_id)
        metric["by_task_type"] = group_metric(metric["row_cards"], "task_type")
        metric["by_repo_family"] = group_metric(metric["row_cards"], "repo_family")
        scorer_results[scorer] = metric
    hundred_m = scorer_results[PRODUCT_SCORER]
    gates = {
        "all_rows_web": all(row.get("language_family") == "web_js_ts_html" for row in rows),
        "no_duplicate_rows": len({row.get("row_id") for row in rows}) == len(rows),
        "no_singletons": not anti_cheat(rows)["singletons"],
        "product_scorer_full_coverage": hundred_m.get("coverage") == 1.0,
        "root_heldout_minimum_met": anti_cheat(rows)["unique_roots"] >= 10,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": all(gates.values()),
        "decision": "web_root_heldout_stage11507_score_complete" if all(gates.values()) else "web_root_heldout_stage11507_score_has_gate_failures",
        "runtime_initialization": init_card,
        "runtime_weights_sha256": init_card.get("weights_sha256"),
        "product_scorer": PRODUCT_SCORER,
        "hundred_m": {key: value for key, value in hundred_m.items() if key != "row_cards"},
        "scorer_results": {
            scorer: {key: value for key, value in result.items() if key != "row_cards"}
            for scorer, result in scorer_results.items()
        },
        "source_counts": source_counts,
        "anti_cheat": anti_cheat(rows),
        "gates": gates,
        "claim_boundary": [
            "This is a Web/JS/TS/HTML root-heldout diagnostic, not a repo-family-heldout claim.",
            "Stage11547 already found repo-family overlap in the broader Web manifest.",
            "This is compact bounded-choice scoring, not freeform repair or executable patch synthesis.",
            "Gemma must be run on the exact ROWS_OUT manifest before any same-manifest comparison claim.",
        ],
        "source_artifacts": {"runtime_bundle": rel(RUNTIME), **{key: rel(path) for key, path in ROW_SOURCES.items()}},
        "outputs": {"summary": rel(SUMMARY), "web_root_heldout_rows": rel(ROWS_OUT), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"passed": summary["passed"], "hundred_m": summary["hundred_m"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
