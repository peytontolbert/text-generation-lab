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

from legacy_src.agentkernel_lite.modeling_transformer import (  # noqa: E402
    AgentKernelLiteTransformerConfig,
    AgentKernelLiteTransformerSeq2Seq,
)
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer  # noqa: E402
from legacy_src.agentkernel_lite.training_loop import (  # noqa: E402
    _load_runtime_model_bundle,
    _write_bounded_choice_eval_audit,
)

ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11397
NAME = "stage11397_openhands_support_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "openhands_support_postrun_audit.json"

SEALED_OPENHANDS = ART / "stage11390_openhands_unit_verifier_heldout_candidate_rows/openhands_unit_verifier_heldout_candidate_rows.jsonl"
SUPPORT_ROWS = ART / "stage11394_openhands_support_unit_verifier_train_rows/openhands_support_unit_verifier_train_rows.jsonl"
CANARY_STRICT = ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_strict_rows.jsonl"
CANARY_VALIDATION = ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_validation_rows.jsonl"

RUNTIMES = {
    "stage11200_frontier": ART / "stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json",
    "stage11396_openhands_support_diagnostic": ART
    / "stage11396_openhands_support_diagnostic_probe/runtime_model/runtime_model_bundle.json",
}

PRODUCT_SCORER = "encoder_option_retrieval_evidence_judgment_head"

torch.set_num_threads(max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8"))))
torch.set_num_interop_threads(2)
DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def load_runtime(runtime: Path):
    bundle = read_json(runtime)
    metadata = bundle["metadata"]
    cfg = AgentKernelLiteTransformerConfig.from_recovered_target_json(read_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(cfg)
    init = _load_runtime_model_bundle(runtime, model=model)
    model.to(DEVICE)
    model.eval()
    tok = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tok, init, bundle


def metric(card: dict[str, Any]) -> dict[str, Any]:
    row_cards = card.get("row_cards") or []
    scored = [row for row in row_cards if isinstance(row.get("constrained_choice_match"), bool)]
    correct = sum(1 for row in scored if row.get("constrained_choice_match"))
    return {
        "rows": len(row_cards),
        "scored_rows": len(scored),
        "correct": correct,
        "exact_accuracy": correct / len(scored) if scored else None,
        "full_vocab_top1_accuracy": card.get("full_vocab_top1_accuracy"),
        "rows_with_target_rank_1": card.get("rows_with_target_rank_1"),
    }


def misses(card: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in card.get("row_cards") or []:
        if row.get("constrained_choice_match") is False:
            out.append(
                {
                    "row_id": row.get("row_id"),
                    "task_type": row.get("task_type"),
                    "target_text": row.get("target_text"),
                    "predicted": row.get("constrained_choice_top1_label"),
                    "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                    "target_rank_full_vocab": row.get("target_rank_full_vocab"),
                }
            )
    return out


def score_runtime(runtime_name: str, runtime_path: Path, splits: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    if not runtime_path.exists():
        return {"missing_runtime": rel(runtime_path)}
    model, tok, init, bundle = load_runtime(runtime_path)
    scores: dict[str, Any] = {}
    for split_name, rows in splits.items():
        card = _write_bounded_choice_eval_audit(
            OUT,
            model=model,
            rows=rows,
            tokenizer=tok,
            max_encoder_tokens=768,
            max_decoder_tokens=8,
            split_name=f"{runtime_name}_{split_name}_{PRODUCT_SCORER}",
            bounded_choice_aux_source=PRODUCT_SCORER,
            eval_batch_size=8,
        )
        scores[split_name] = {"metric": metric(card), "misses": misses(card)}
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return {
        "runtime_initialization": init,
        "runtime_bundle": {
            "path": rel(runtime_path),
            "weights_sha256": bundle.get("weights_sha256") or (bundle.get("runtime_model_bundle") or {}).get("weights_sha256"),
        },
        "scores": scores,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    splits = {
        "sealed_openhands_heldout": read_jsonl(SEALED_OPENHANDS),
        "openhands_support_train": read_jsonl(SUPPORT_ROWS),
        "canary_strict": read_jsonl(CANARY_STRICT),
        "canary_validation": read_jsonl(CANARY_VALIDATION),
    }
    scored = {name: score_runtime(name, path, splits) for name, path in RUNTIMES.items()}

    base = scored.get("stage11200_frontier", {}).get("scores", {})
    candidate = scored.get("stage11396_openhands_support_diagnostic", {}).get("scores", {})
    base_heldout = (base.get("sealed_openhands_heldout") or {}).get("metric", {})
    candidate_heldout = (candidate.get("sealed_openhands_heldout") or {}).get("metric", {})
    base_strict = (base.get("canary_strict") or {}).get("metric", {})
    candidate_strict = (candidate.get("canary_strict") or {}).get("metric", {})
    base_validation = (base.get("canary_validation") or {}).get("metric", {})
    candidate_validation = (candidate.get("canary_validation") or {}).get("metric", {})

    heldout_delta = None
    if base_heldout.get("exact_accuracy") is not None and candidate_heldout.get("exact_accuracy") is not None:
        heldout_delta = candidate_heldout["exact_accuracy"] - base_heldout["exact_accuracy"]
    strict_regressed = (
        candidate_strict.get("exact_accuracy") is not None
        and base_strict.get("exact_accuracy") is not None
        and candidate_strict["exact_accuracy"] < base_strict["exact_accuracy"]
    )
    validation_regressed = (
        candidate_validation.get("exact_accuracy") is not None
        and base_validation.get("exact_accuracy") is not None
        and candidate_validation["exact_accuracy"] < base_validation["exact_accuracy"]
    )
    heldout_improved = heldout_delta is not None and heldout_delta > 0
    accept_runtime = bool(heldout_improved and not strict_regressed and not validation_regressed)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "decision": "accept_stage11396_diagnostic_runtime" if accept_runtime else "reject_stage11396_keep_stage11200_frontier",
        "claim_scope": "diagnostic OpenHands Web support postrun; Stage11390 remains a sealed smoke slice, not broad Web proof",
        "product_scorer": PRODUCT_SCORER,
        "base_runtime": "stage11200_frontier",
        "candidate_runtime": "stage11396_openhands_support_diagnostic",
        "base_heldout": base_heldout,
        "candidate_heldout": candidate_heldout,
        "heldout_delta": heldout_delta,
        "base_canary_strict": base_strict,
        "candidate_canary_strict": candidate_strict,
        "base_canary_validation": base_validation,
        "candidate_canary_validation": candidate_validation,
        "strict_regressed": strict_regressed,
        "validation_regressed": validation_regressed,
        "accept_runtime": accept_runtime,
        "scored": scored,
        "source_artifacts": {
            "sealed_openhands_heldout": rel(SEALED_OPENHANDS),
            "openhands_support_train": rel(SUPPORT_ROWS),
            "canary_strict": rel(CANARY_STRICT),
            "canary_validation": rel(CANARY_VALIDATION),
            **{f"runtime_{key}": rel(path) for key, path in RUNTIMES.items()},
        },
        "outputs": {"summary": rel(SUMMARY)},
        "recommended_next_action": (
            "Reject Stage11396 if sealed OpenHands does not improve over 4/18; build broader disjoint Web verifier support instead."
        ),
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": summary["decision"],
                "base_heldout": base_heldout,
                "candidate_heldout": candidate_heldout,
                "heldout_delta": heldout_delta,
                "base_canary_strict": base_strict,
                "candidate_canary_strict": candidate_strict,
                "base_canary_validation": base_validation,
                "candidate_canary_validation": candidate_validation,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
