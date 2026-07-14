#!/usr/bin/env python3
from __future__ import annotations

import json
import os
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
STAGE = 11329
NAME = "stage11329_alias_free_evidence_scale_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "alias_free_evidence_scale_postrun_audit.json"
RUNTIME = ART / "stage11328_alias_free_evidence_scale_probe/runtime_model/runtime_model_bundle.json"
REQUEST = ART / "stage11327_alias_free_evidence_scale_probe_request/alias_free_evidence_scale_probe_request.json"
PKG = ART / "stage11326_alias_free_evidence_item_selection_scale_package/alias_free_evidence_item_selection_scale_package.json"

SPLITS = {
    "alias_scale_validation": ART
    / "stage11326_alias_free_evidence_item_selection_scale_package"
    / "alias_free_evidence_item_selection_scale_validation_rows.jsonl",
    "alias_scale_strict": ART
    / "stage11326_alias_free_evidence_item_selection_scale_package"
    / "alias_free_evidence_item_selection_scale_strict_rows.jsonl",
    "alias_scale_diagnostic": ART
    / "stage11326_alias_free_evidence_item_selection_scale_package"
    / "alias_free_evidence_item_selection_scale_diagnostic_rows.jsonl",
    "canary_validation": ART
    / "stage11312_deleaked_fail_to_pass_transition_package"
    / "deleaked_fail_to_pass_validation_rows.jsonl",
    "canary_strict": ART
    / "stage11312_deleaked_fail_to_pass_transition_package"
    / "deleaked_fail_to_pass_strict_rows.jsonl",
    "canary_residual": ART
    / "stage11312_deleaked_fail_to_pass_transition_package"
    / "deleaked_fail_to_pass_residual_rows.jsonl",
}

SCORERS = [
    "encoder_option_retrieval_evidence_judgment_head",
    "encoder_option_retrieval_verifier_conditioned",
    "encoder_option_retrieval",
    "decoder_first_step",
]

torch.set_num_threads(max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8"))))
torch.set_num_interop_threads(2)
DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def load_runtime():
    bundle = read_json(RUNTIME)
    metadata = bundle["metadata"]
    cfg = AgentKernelLiteTransformerConfig.from_recovered_target_json(read_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(cfg)
    init = _load_runtime_model_bundle(RUNTIME, model=model)
    model.to(DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    return model, tokenizer, init


def metric(card: dict[str, Any]) -> dict[str, Any]:
    rows = card.get("row_cards") or []
    scored = [row for row in rows if isinstance(row.get("constrained_choice_match"), bool)]
    correct = sum(1 for row in scored if row.get("constrained_choice_match"))
    by_language: dict[str, dict[str, int]] = {}
    by_gold: dict[str, dict[str, int]] = {}
    for row in scored:
        lang = str(row.get("language_family") or "unknown")
        gold = str(row.get("semantic_target_value") or "unknown")
        by_language.setdefault(lang, {"rows": 0, "correct": 0})
        by_gold.setdefault(gold, {"rows": 0, "correct": 0})
        by_language[lang]["rows"] += 1
        by_gold[gold]["rows"] += 1
        if row.get("constrained_choice_match"):
            by_language[lang]["correct"] += 1
            by_gold[gold]["correct"] += 1
    for group in [by_language, by_gold]:
        for value in group.values():
            value["accuracy"] = value["correct"] / value["rows"] if value["rows"] else 0
    return {
        "rows": len(rows),
        "scored_rows": len(scored),
        "correct": correct,
        "exact_accuracy": correct / len(scored) if scored else None,
        "by_language": by_language,
        "by_gold": by_gold,
    }


def misses(card: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for row in card.get("row_cards") or []:
        if row.get("constrained_choice_match") is False:
            out.append(
                {
                    "row_id": row.get("row_id"),
                    "language_family": row.get("language_family"),
                    "semantic_target_value": row.get("semantic_target_value"),
                    "target_text": row.get("target_text"),
                    "predicted": row.get("constrained_choice_top1_label"),
                    "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                    "target_rank_full_vocab": row.get("target_rank_full_vocab"),
                }
            )
    return out[:80]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    model, tokenizer, init = load_runtime()
    scored: dict[str, Any] = {}
    for scorer in SCORERS:
        scored[scorer] = {}
        for split_name, path in SPLITS.items():
            rows = read_jsonl(path)
            card = _write_bounded_choice_eval_audit(
                OUT,
                model=model,
                rows=rows,
                tokenizer=tokenizer,
                max_encoder_tokens=768,
                max_decoder_tokens=8,
                split_name=f"{split_name}_{scorer}",
                bounded_choice_aux_source=scorer,
                eval_batch_size=8,
            )
            scored[scorer][split_name] = {"metric": metric(card), "misses": misses(card)}
    product = scored["encoder_option_retrieval_evidence_judgment_head"]
    gates = {
        "alias_scale_diagnostic_above_5_of_7": product["alias_scale_diagnostic"]["metric"]["correct"] > 5,
        "alias_scale_validation_at_least_70pct": (product["alias_scale_validation"]["metric"]["exact_accuracy"] or 0) >= 0.70,
        "alias_scale_strict_at_least_70pct": (product["alias_scale_strict"]["metric"]["exact_accuracy"] or 0) >= 0.70,
        "canary_strict_22_of_22": product["canary_strict"]["metric"]["correct"] == 22,
        "canary_validation_at_least_20_of_23": product["canary_validation"]["metric"]["correct"] >= 20,
        "canary_residual_above_5_of_10": product["canary_residual"]["metric"]["correct"] > 5,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "decision": "alias_free_evidence_scale_postrun_audit_complete",
        "runtime_initialization": init,
        "gates": gates,
        "product_metrics": {name: value["metric"] for name, value in product.items()},
        "scored": scored,
        "source_artifacts": {
            "runtime": rel(RUNTIME),
            "request": rel(REQUEST),
            "package": rel(PKG),
            **{name: rel(path) for name, path in SPLITS.items()},
        },
        "outputs": {"summary_json": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    print(json.dumps({"gates": gates, "product_metrics": summary["product_metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
