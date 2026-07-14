#!/usr/bin/env python3
"""Routed audit for Stage11960 augmented Transition-5K diagnostic runtime."""

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
STAGE = 11961
NAME = "stage11961_transition_5k_augmented_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "transition_5k_augmented_postrun_audit.json"

OLD_ROWS = ART / "stage11897_transition_record_projection_rows/transition_projection_rows.jsonl"
AUG_ROWS = ART / "stage11958_transition_5k_v1_augmented_package/transition_projection_rows_5k_v1_augmented.jsonl"

RUNTIMES = {
    "stage11924_selected_transition": ART / "stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json",
    "stage11947_v2_only": ART / "stage11947_transition_1k_v2_listwise_probe/runtime_model/runtime_model_bundle.json",
    "stage11952_v2_replay_balanced": ART / "stage11952_transition_1k_v2_replay_balanced_probe/runtime_model/runtime_model_bundle.json",
    "stage11960_augmented_5k": ART / "stage11960_transition_5k_augmented_probe/runtime_model/runtime_model_bundle.json",
}

PROTECTED_ROWSETS = {
    "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "filtered_validation": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl",
    "old_canary_strict": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "old_canary_validation": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl",
    "verifier_grounded_source_heldout_smoke": ART / "stage11740_verifier_grounded_source_heldout_successor_score/verifier_grounded_successor_rows.jsonl",
}

TRANSITION_SCORER = "encoder_option_retrieval_semantic_candidate_head"
COMPACT_SCORER = "encoder_option_retrieval_evidence_judgment_head"

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
        out["target"] = {"decoder_text": out.get("decoder_text") or label, "bounded_choice_target_label": label}
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
    rows = card.get("rows") or 0
    correct = card.get("constrained_choice_correct") or 0
    return {
        "rows": rows,
        "correct": correct,
        "accuracy": correct / rows if rows else None,
        "coverage": card.get("constrained_choice_coverage"),
        "miss_count": sum(1 for row in card.get("row_cards") or [] if row.get("constrained_choice_match") is not True),
    }


def audit_rows(out_dir: Path, model: Any, tokenizer: Any, rows: list[dict[str, Any]], split_name: str, scorer: str) -> tuple[dict[str, Any], dict[str, Any]]:
    card = _write_bounded_choice_eval_audit(
        out_dir,
        model=model,
        rows=rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=16,
        split_name=split_name,
        bounded_choice_aux_source=scorer,
        eval_batch_size=8,
    )
    return metric(card), card


def group_from_card(card: dict[str, Any], rows_by_id: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in card.get("row_cards") or []:
        meta = rows_by_id.get(str(item.get("row_id")), {})
        buckets.setdefault(str(meta.get(key) or "unknown"), []).append(item)
    out: dict[str, Any] = {}
    for name, items in sorted(buckets.items()):
        correct = sum(1 for item in items if item.get("constrained_choice_match") is True)
        out[name] = {"rows": len(items), "correct": correct, "accuracy": correct / len(items) if items else None}
    return out


def by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("row_id")): row for row in rows}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    old_rows = [normalize_row(row) for row in read_jsonl(OLD_ROWS)]
    aug_all = [normalize_row(row) for row in read_jsonl(AUG_ROWS)]
    aug_splits = {
        "train": [row for row in aug_all if str(row.get("split")) == "train"],
        "validation": [row for row in aug_all if str(row.get("split")) == "validation"],
        "strict_eval": [row for row in aug_all if str(row.get("split")) == "strict_eval"],
    }
    protected = {name: [normalize_row(row) for row in read_jsonl(path)] for name, path in PROTECTED_ROWSETS.items()}
    row_meta = {"old_transition_640": by_id(old_rows), **{f"aug_{k}": by_id(v) for k, v in aug_splits.items()}}

    results: dict[str, Any] = {}
    init_cards: dict[str, Any] = {}
    for runtime_name, runtime_path in RUNTIMES.items():
        model, tokenizer, init_card = load_runtime(runtime_path)
        init_cards[runtime_name] = init_card
        runtime_out = OUT / runtime_name
        runtime_result: dict[str, Any] = {}
        metric_old, card_old = audit_rows(runtime_out / "old_transition_640", model, tokenizer, old_rows, "old_transition_640", TRANSITION_SCORER)
        runtime_result["old_transition_640"] = {
            "metric": metric_old,
            "by_task_type": group_from_card(card_old, row_meta["old_transition_640"], "task_type"),
            "by_language_family": group_from_card(card_old, row_meta["old_transition_640"], "language_family"),
        }
        for split, rows in aug_splits.items():
            m, c = audit_rows(runtime_out / f"aug_{split}", model, tokenizer, rows, f"aug_{split}", TRANSITION_SCORER)
            runtime_result[f"aug_{split}"] = {
                "metric": m,
                "by_task_type": group_from_card(c, row_meta[f"aug_{split}"], "task_type"),
                "by_language_family": group_from_card(c, row_meta[f"aug_{split}"], "language_family"),
            }
        for name, rows in protected.items():
            m, _ = audit_rows(runtime_out / f"protected_{name}", model, tokenizer, rows, f"protected_{name}", COMPACT_SCORER)
            runtime_result[f"protected_{name}"] = {"metric": m}
        results[runtime_name] = runtime_result
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    baseline = results["stage11924_selected_transition"]
    postrun = results["stage11960_augmented_5k"]
    gates = {
        "old_transition_at_least_stage11924_364": postrun["old_transition_640"]["metric"]["correct"] >= baseline["old_transition_640"]["metric"]["correct"],
        "aug_validation_improves_stage11924": postrun["aug_validation"]["metric"]["correct"] > baseline["aug_validation"]["metric"]["correct"],
        "aug_strict_improves_stage11924": postrun["aug_strict_eval"]["metric"]["correct"] > baseline["aug_strict_eval"]["metric"]["correct"],
        "filtered_strict_22": postrun["protected_filtered_strict"]["metric"]["correct"] == 22,
        "filtered_validation_at_least_20": postrun["protected_filtered_validation"]["metric"]["correct"] >= 20,
        "old_canary_strict_23": postrun["protected_old_canary_strict"]["metric"]["correct"] == 23,
        "old_canary_validation_at_least_21": postrun["protected_old_canary_validation"]["metric"]["correct"] >= 21,
        "residual_at_least_7": postrun["protected_residual_bank"]["metric"]["correct"] >= 7,
        "source_heldout_smoke_at_least_6": postrun["protected_verifier_grounded_source_heldout_smoke"]["metric"]["correct"] >= 6,
    }
    decision = "promote_transition_5k_augmented_candidate" if all(gates.values()) else "reject_transition_5k_augmented_candidate"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "device": str(DEVICE),
        "route_policy": {"transition_rows": TRANSITION_SCORER, "protected_compact_rows": COMPACT_SCORER},
        "gates": gates,
        "scoreboard": {
            runtime: {
                "old_transition_640": data["old_transition_640"]["metric"],
                "aug_train": data["aug_train"]["metric"],
                "aug_validation": data["aug_validation"]["metric"],
                "aug_strict_eval": data["aug_strict_eval"]["metric"],
                "filtered_strict": data["protected_filtered_strict"]["metric"],
                "filtered_validation": data["protected_filtered_validation"]["metric"],
                "old_canary_strict": data["protected_old_canary_strict"]["metric"],
                "old_canary_validation": data["protected_old_canary_validation"]["metric"],
                "residual_bank": data["protected_residual_bank"]["metric"],
                "source_heldout_smoke": data["protected_verifier_grounded_source_heldout_smoke"]["metric"],
            }
            for runtime, data in results.items()
        },
        "results": results,
        "runtime_initialization": init_cards,
        "source_artifacts": {
            "old_rows": rel(OLD_ROWS),
            "augmented_rows": rel(AUG_ROWS),
            "runtimes": {name: rel(path) for name, path in RUNTIMES.items()},
            "protected_rowsets": {name: rel(path) for name, path in PROTECTED_ROWSETS.items()},
        },
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
        "claim_boundary": [
            "Stage11960 is diagnostic because Stage11958 includes counterfactual rows that do not add independent roots.",
            "No broad Gemma claim is valid unless old transition 640 beats Gemma 386/640 and source-heldout smoke improves.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "gates": gates, "scoreboard": summary["scoreboard"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
