#!/usr/bin/env python3
"""Score current runtimes on Stage11897 transition projection rows."""

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
STAGE = 11913
NAME = "stage11913_transition_projection_semantic_head_only_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "transition_projection_semantic_head_only_postrun_audit.json"

ROWS = ART / "stage11897_transition_record_projection_rows/transition_projection_rows.jsonl"
RUNTIMES = {
    "stage11507_selected_frontier": ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json",
    "stage11912_transition_projection_semantic_head_only": ART / "stage11912_transition_projection_semantic_head_only_probe/runtime_model/runtime_model_bundle.json",
}
PROTECTED_ROWSETS = {
    "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "old_canary_strict": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "filtered_validation": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl",
    "old_canary_validation": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl",
    "verifier_grounded_source_heldout_smoke": ART / "stage11740_verifier_grounded_source_heldout_successor_score/verifier_grounded_successor_rows.jsonl",
}
SCORER = "encoder_option_retrieval_semantic_candidate_head"

torch.set_num_threads(max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8"))))
try:
    torch.set_num_interop_threads(max(1, min(4, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))))
except RuntimeError:
    pass
DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    source = dict(out.get("standalone_projection_source") or {})
    source.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = source
    if not isinstance(out.get("target"), dict):
        label = out.get("bounded_choice_target_label") or out.get("target_label") or out.get("target_text")
        out["target"] = {
            "decoder_text": out.get("decoder_text") or label,
            "bounded_choice_target_label": label,
            "semantic_value": out.get("semantic_target_value") or out.get("target_value"),
        }
    out.setdefault("loss_mask", {"decoder_ce": True, "bounded_choice_aux": True})
    return out


def load_runtime(path: Path) -> tuple[Any, Any, dict[str, Any]]:
    bundle = read_json(path)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(read_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(path, model=model)
    model.to(DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def metric(card: dict[str, Any]) -> dict[str, Any]:
    misses = []
    for row in card.get("row_cards") or []:
        if row.get("constrained_choice_match") is not True:
            misses.append(
                {
                    "row_id": row.get("row_id"),
                    "target": row.get("bounded_choice_target_label"),
                    "predicted": row.get("constrained_choice_top1_label"),
                    "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                    "target_rank_full_vocab": row.get("target_rank_full_vocab"),
                }
            )
    return {
        "rows": card.get("rows"),
        "correct": card.get("constrained_choice_correct"),
        "accuracy": card.get("constrained_choice_top1_accuracy"),
        "coverage": card.get("constrained_choice_coverage"),
        "misses": misses[:30],
        "miss_count": len(misses),
    }


def row_groups(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = {"all_transition_projection_rows": rows}
    for row in rows:
        groups.setdefault(str(row.get("task_type")), []).append(row)
        groups.setdefault(f"language::{row.get('language_family')}", []).append(row)
    for name, path in PROTECTED_ROWSETS.items():
        groups[f"protected::{name}"] = [normalize_row(row) for row in read_jsonl(path)]
    return groups


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [normalize_row(row) for row in read_jsonl(ROWS)]
    groups = row_groups(rows)
    results: dict[str, Any] = {}
    init_cards: dict[str, Any] = {}
    for runtime_name, runtime_path in RUNTIMES.items():
        model, tokenizer, init_card = load_runtime(runtime_path)
        init_cards[runtime_name] = init_card
        runtime_results: dict[str, Any] = {}
        for group_name, group_rows in groups.items():
            card = _write_bounded_choice_eval_audit(
                OUT / runtime_name,
                model=model,
                rows=group_rows,
                tokenizer=tokenizer,
                max_encoder_tokens=768,
                max_decoder_tokens=16,
                split_name=group_name.replace(":", "_"),
                bounded_choice_aux_source=SCORER,
                eval_batch_size=8,
            )
            runtime_results[group_name] = metric(card)
        results[runtime_name] = runtime_results
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    selected_all = results["stage11507_selected_frontier"]["all_transition_projection_rows"]
    postrun_all = results["stage11912_transition_projection_semantic_head_only"]["all_transition_projection_rows"]
    protected = results["stage11912_transition_projection_semantic_head_only"]
    gates = {
        "projection_fit_improved": (postrun_all.get("correct") or 0) > (selected_all.get("correct") or 0),
        "projection_fit_at_least_320_of_640": (postrun_all.get("correct") or 0) >= 320,
        "filtered_strict_preserved": protected["protected::filtered_strict"].get("correct") == 22,
        "old_canary_strict_preserved": protected["protected::old_canary_strict"].get("correct") == 23,
        "residual_preserved": (protected["protected::residual_bank"].get("correct") or 0) >= 7,
    }
    if gates["projection_fit_improved"] and gates["projection_fit_at_least_320_of_640"]:
        decision = "transition_projection_semantic_head_only_learned_interface"
    elif gates["projection_fit_improved"]:
        decision = "transition_projection_semantic_head_only_partial_fit"
    else:
        decision = "transition_projection_semantic_head_only_no_fit_gain"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "device": str(DEVICE),
        "gates": gates,
        "scorer": SCORER,
        "row_counts": {
            "total_rows": len(rows),
            "by_task": dict(Counter(str(row.get("task_type")) for row in rows)),
            "by_language": dict(Counter(str(row.get("language_family")) for row in rows)),
        },
        "results": results,
        "runtime_initialization": init_cards,
        "source_artifacts": {
            "projection_rows": rel(ROWS),
            **{name: rel(path) for name, path in RUNTIMES.items()},
        },
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
        "claim_boundary": [
            "This is a projection-row baseline audit, not a training run.",
            "Stage11912 trains only the semantic candidate bounded-choice head on root-disjoint transition projection and compact analogue rows.",
            "Protected gates are audited only to measure interference, not to support promotion.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": decision,
                "selected_all": {"correct": selected_all.get("correct"), "rows": selected_all.get("rows")},
                "postrun_all": {"correct": postrun_all.get("correct"), "rows": postrun_all.get("rows")},
                "gates": gates,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
