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
STAGE = 11552
NAME = "stage11552_evidence_judgment_reroute_audit"
OUT = ART / NAME
SUMMARY = OUT / "evidence_judgment_reroute_audit.json"

RUNTIMES = {
    "stage11507_selected": ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json",
    "stage11550_web_support_diagnostic": ART / "stage11550_web_root_support_from_stage11507_probe/runtime_model/runtime_model_bundle.json",
}
ROWSETS = {
    "web_heldout": ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl",
    "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "old_canary_strict": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
}
PRODUCT_SCORER = "encoder_option_retrieval_evidence_judgment_head"
ROLE_TO_JUDGMENT = {
    "candidate_change_surface": "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
    "verifier_and_test_constraint": "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "symptom_or_call_path_analogue": "SUPPORTING_SYMPTOM_OR_CALL_PATH",
    "nearby_definition_or_usage_context": "DISTRACTOR_BACKGROUND_CONTEXT",
    "external_analogue_reference": "DISTRACTOR_BACKGROUND_CONTEXT",
    "algorithmic_background_reference": "DISTRACTOR_BACKGROUND_CONTEXT",
    "dependency_or_test_environment_surface": "DISTRACTOR_BACKGROUND_CONTEXT",
    "supporting_secondary_surface": "DISTRACTOR_BACKGROUND_CONTEXT",
    "abstain_insufficient_evidence": "DISTRACTOR_BACKGROUND_CONTEXT",
}

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


def judgment_value(value: str) -> str | None:
    raw = str(value).strip()
    if "|" in raw:
        raw = raw.split("|", 1)[0].strip()
    if raw in ROLE_TO_JUDGMENT:
        return ROLE_TO_JUDGMENT[raw]
    if raw in set(ROLE_TO_JUDGMENT.values()):
        return raw
    return None


def reroute_row(row: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    out = normalize_row(row)
    task = str(out.get("task_type") or "")
    if task != "evidence_citation":
        return out, False
    options = list(((out.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    mapped = []
    supported = False
    for option in options:
        value = judgment_value(str(option.get("value") or ""))
        item = dict(option)
        if value is not None:
            item["value"] = value
            supported = True
        mapped.append(item)
    if not supported:
        return out, False
    source = dict(out.get("standalone_projection_source") or {})
    source["opaque_options"] = mapped
    source["stage11552_rerouted_from_task_type"] = task
    out["standalone_projection_source"] = source
    out["opaque_options"] = mapped
    out["task_type"] = "evidence_candidate_judgment"
    text = str(out.get("input_text") or out.get("prompt_text") or "")
    if "Perspective: evidence_citation" in text:
        text = text.replace("Perspective: evidence_citation", "Perspective: evidence_candidate_judgment")
    out["input_text"] = text
    out["prompt_text"] = text
    return out, True


def load_runtime(runtime: Path) -> tuple[Any, Any, dict[str, Any]]:
    bundle = load_json(runtime)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(runtime, model=model)
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
                    "target_rank_full_vocab": row.get("target_rank_full_vocab"),
                    "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                }
            )
    return {
        "rows": card.get("rows"),
        "correct": card.get("constrained_choice_correct"),
        "scored_rows": card.get("constrained_choice_rows"),
        "coverage": card.get("constrained_choice_coverage"),
        "accuracy": card.get("constrained_choice_top1_accuracy"),
        "misses": misses,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rowsets: dict[str, dict[str, Any]] = {}
    for name, path in ROWSETS.items():
        original = [normalize_row(row) for row in load_jsonl(path)]
        rerouted = []
        count = 0
        for row in original:
            mapped, did = reroute_row(row)
            count += int(did)
            rerouted.append(mapped)
        rowsets[name] = {"original": original, "rerouted": rerouted, "rerouted_rows": count}

    results: dict[str, Any] = {}
    for runtime_name, runtime_path in RUNTIMES.items():
        model, tokenizer, init_card = load_runtime(runtime_path)
        runtime_results = {"runtime_initialization": init_card, "rowsets": {}}
        for rowset_name, payload in rowsets.items():
            base_card = _write_bounded_choice_eval_audit(
                OUT,
                model=model,
                rows=payload["original"],
                tokenizer=tokenizer,
                max_encoder_tokens=768,
                max_decoder_tokens=16,
                split_name=f"{runtime_name}_{rowset_name}_base",
                bounded_choice_aux_source=PRODUCT_SCORER,
                eval_batch_size=8,
            )
            reroute_card = _write_bounded_choice_eval_audit(
                OUT,
                model=model,
                rows=payload["rerouted"],
                tokenizer=tokenizer,
                max_encoder_tokens=768,
                max_decoder_tokens=16,
                split_name=f"{runtime_name}_{rowset_name}_rerouted",
                bounded_choice_aux_source=PRODUCT_SCORER,
                eval_batch_size=8,
            )
            base = metric(base_card)
            rerouted = metric(reroute_card)
            runtime_results["rowsets"][rowset_name] = {
                "rerouted_rows": payload["rerouted_rows"],
                "base": base,
                "rerouted": rerouted,
                "delta_correct": (rerouted.get("correct") or 0) - (base.get("correct") or 0),
            }
        results[runtime_name] = runtime_results
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    selected = results["stage11507_selected"]["rowsets"]
    gates = {
        "web_heldout_reroute_improves": selected["web_heldout"]["delta_correct"] > 0,
        "filtered_strict_not_regressed": selected["filtered_strict"]["rerouted"]["correct"] == selected["filtered_strict"]["base"]["correct"],
        "old_canary_strict_not_regressed": selected["old_canary_strict"]["rerouted"]["correct"] == selected["old_canary_strict"]["base"]["correct"],
        "residual_not_regressed": selected["residual_bank"]["rerouted"]["correct"] >= selected["residual_bank"]["base"]["correct"],
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "evidence_judgment_reroute_promising" if all(gates.values()) else "evidence_judgment_reroute_not_promotable",
        "product_scorer": PRODUCT_SCORER,
        "results": results,
        "gates": gates,
        "claim_boundary": [
            "Inference-side routing audit only; no product scorer contract changed here.",
            "Rows are only rerouted when evidence_citation options map to evidence judgment buckets.",
            "A positive result would justify implementing a gated scorer route and rerunning full promotion gates.",
        ],
        "source_artifacts": {f"runtime_{key}": rel(path) for key, path in RUNTIMES.items()} | {f"rowset_{key}": rel(path) for key, path in ROWSETS.items()},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "gates": gates, "selected": selected}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
