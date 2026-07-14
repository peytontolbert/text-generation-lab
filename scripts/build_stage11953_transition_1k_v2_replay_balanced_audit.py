#!/usr/bin/env python3
"""Audit Stage11952 replay-balanced Transition-1K-v2 runtime.

This audit intentionally compares three runtimes:
  - Stage11924: selected transition baseline.
  - Stage11947: v2-only runtime that improved v2 but regressed old-640.
  - Stage11952: replay-balanced runtime under review.
"""

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
STAGE = 11953
NAME = "stage11953_transition_1k_v2_replay_balanced_audit"
OUT = ART / NAME
SUMMARY = OUT / "transition_1k_v2_replay_balanced_audit.json"

OLD_TRANSITION_ROWS = ART / "stage11897_transition_record_projection_rows/transition_projection_rows.jsonl"
V2_ROWS = ART / "stage11945_transition_1k_v2_multisource_package/transition_projection_rows_v2.jsonl"

RUNTIMES = {
    "stage11924_selected_transition": ART / "stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json",
    "stage11947_v2_only": ART / "stage11947_transition_1k_v2_listwise_probe/runtime_model/runtime_model_bundle.json",
    "stage11952_v2_replay_balanced": ART / "stage11952_transition_1k_v2_replay_balanced_probe/runtime_model/runtime_model_bundle.json",
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
        out["target"] = {
            "decoder_text": out.get("decoder_text") or label,
            "bounded_choice_target_label": label,
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
    rows = card.get("rows") or 0
    correct = card.get("constrained_choice_correct") or 0
    return {
        "rows": rows,
        "correct": correct,
        "accuracy": correct / rows if rows else None,
        "coverage": card.get("constrained_choice_coverage"),
        "miss_count": sum(1 for row in card.get("row_cards") or [] if row.get("constrained_choice_match") is not True),
    }


def grouped(card: dict[str, Any], key: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in card.get("row_cards") or []:
        buckets.setdefault(str(row.get(key)), []).append(row)
    out: dict[str, Any] = {}
    for name, rows in sorted(buckets.items()):
        correct = sum(1 for row in rows if row.get("constrained_choice_match") is True)
        out[name] = {"rows": len(rows), "correct": correct, "accuracy": correct / len(rows) if rows else None}
    return out


def audit_rows(
    *,
    out_dir: Path,
    model: Any,
    tokenizer: Any,
    rows: list[dict[str, Any]],
    split_name: str,
    scorer: str,
) -> dict[str, Any]:
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
    return {
        "metric": metric(card),
        "by_language_family": grouped(card, "language_family"),
        "by_task_type": grouped(card, "task_type"),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    old_rows = [normalize_row(row) for row in read_jsonl(OLD_TRANSITION_ROWS)]
    v2_all = [normalize_row(row) for row in read_jsonl(V2_ROWS)]
    v2_by_split = {
        split: [row for row in v2_all if row.get("split") == split]
        for split in ("train", "validation", "strict_eval")
    }
    protected = {name: [normalize_row(row) for row in read_jsonl(path)] for name, path in PROTECTED_ROWSETS.items()}

    results: dict[str, Any] = {}
    init_cards: dict[str, Any] = {}
    for runtime_name, runtime_path in RUNTIMES.items():
        model, tokenizer, init_card = load_runtime(runtime_path)
        init_cards[runtime_name] = init_card
        runtime_out = OUT / runtime_name
        runtime_results: dict[str, Any] = {}
        runtime_results["old_transition_640"] = audit_rows(
            out_dir=runtime_out / "old_transition_640",
            model=model,
            tokenizer=tokenizer,
            rows=old_rows,
            split_name="old_transition_640",
            scorer=TRANSITION_SCORER,
        )
        for split, rows in v2_by_split.items():
            runtime_results[f"v2_{split}"] = audit_rows(
                out_dir=runtime_out / f"v2_{split}",
                model=model,
                tokenizer=tokenizer,
                rows=rows,
                split_name=f"v2_{split}",
                scorer=TRANSITION_SCORER,
            )
        for name, rows in protected.items():
            runtime_results[f"protected_{name}"] = audit_rows(
                out_dir=runtime_out / f"protected_{name}",
                model=model,
                tokenizer=tokenizer,
                rows=rows,
                split_name=f"protected_{name}",
                scorer=COMPACT_SCORER,
            )
        results[runtime_name] = runtime_results
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    baseline = results["stage11924_selected_transition"]
    v2_only = results["stage11947_v2_only"]
    replay = results["stage11952_v2_replay_balanced"]
    gates = {
        "old_transition_at_least_stage11924_364": replay["old_transition_640"]["metric"]["correct"] >= baseline["old_transition_640"]["metric"]["correct"],
        "v2_validation_at_least_stage11947_66": replay["v2_validation"]["metric"]["correct"] >= v2_only["v2_validation"]["metric"]["correct"],
        "v2_strict_at_least_stage11947_123": replay["v2_strict_eval"]["metric"]["correct"] >= v2_only["v2_strict_eval"]["metric"]["correct"],
        "filtered_strict_22": replay["protected_filtered_strict"]["metric"]["correct"] == 22,
        "old_canary_strict_23": replay["protected_old_canary_strict"]["metric"]["correct"] == 23,
        "filtered_validation_at_least_20": replay["protected_filtered_validation"]["metric"]["correct"] >= 20,
        "old_canary_validation_at_least_21": replay["protected_old_canary_validation"]["metric"]["correct"] >= 21,
        "residual_at_least_7": replay["protected_residual_bank"]["metric"]["correct"] >= 7,
        "source_heldout_smoke_at_least_6": replay["protected_verifier_grounded_source_heldout_smoke"]["metric"]["correct"] >= 6,
    }
    if all(gates.values()):
        decision = "promote_transition_replay_balanced_candidate"
    elif gates["old_transition_at_least_stage11924_364"] and gates["filtered_strict_22"] and gates["old_canary_strict_23"]:
        decision = "partial_transition_candidate_needs_v2_or_residual_repair"
    else:
        decision = "reject_transition_replay_balanced_candidate"

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "device": str(DEVICE),
        "route_policy": {
            "transition_rows": TRANSITION_SCORER,
            "protected_compact_rows": COMPACT_SCORER,
        },
        "gates": gates,
        "scoreboard": {
            name: {
                "old_transition_640": data["old_transition_640"]["metric"],
                "v2_train": data["v2_train"]["metric"],
                "v2_validation": data["v2_validation"]["metric"],
                "v2_strict_eval": data["v2_strict_eval"]["metric"],
                "filtered_strict": data["protected_filtered_strict"]["metric"],
                "filtered_validation": data["protected_filtered_validation"]["metric"],
                "old_canary_strict": data["protected_old_canary_strict"]["metric"],
                "old_canary_validation": data["protected_old_canary_validation"]["metric"],
                "residual_bank": data["protected_residual_bank"]["metric"],
                "source_heldout_smoke": data["protected_verifier_grounded_source_heldout_smoke"]["metric"],
            }
            for name, data in results.items()
        },
        "results": results,
        "runtime_initialization": init_cards,
        "source_artifacts": {
            "old_transition_rows": rel(OLD_TRANSITION_ROWS),
            "v2_rows": rel(V2_ROWS),
            "runtimes": {name: rel(path) for name, path in RUNTIMES.items()},
            "protected_rowsets": {name: rel(path) for name, path in PROTECTED_ROWSETS.items()},
        },
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "gates": gates, "scoreboard": summary["scoreboard"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
