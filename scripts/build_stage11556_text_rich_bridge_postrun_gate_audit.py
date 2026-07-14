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
STAGE = 11556
NAME = "stage11556_text_rich_bridge_postrun_gate_audit"
OUT = ART / NAME
SUMMARY = OUT / "text_rich_bridge_postrun_gate_audit.json"

RUNTIME = ART / "stage11555_text_rich_web_evidence_judgment_bridge_probe/runtime_model/runtime_model_bundle.json"
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
    "repo_metadata_or_runtime_setup": "DISTRACTOR_BACKGROUND_CONTEXT",
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


def role_key(value: str) -> str:
    raw = str(value).strip()
    if "|" in raw:
        raw = raw.split("|", 1)[0].strip()
    return raw


def all_supported_text_rich_reroute(row: dict[str, Any]) -> tuple[dict[str, Any], bool, str]:
    out = normalize_row(row)
    if str(out.get("task_type") or "") != "evidence_citation":
        return out, False, "not_evidence_citation"
    options = list(((out.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    if len(options) < 2:
        return out, False, "too_few_options"
    if not all(str(option.get("text") or "").strip() for option in options):
        return out, False, "not_text_rich"
    mapped = []
    for option in options:
        key = role_key(str(option.get("value") or ""))
        judgment = ROLE_TO_JUDGMENT.get(key)
        if judgment is None:
            return out, False, "unsupported_option_value"
        item = dict(option)
        item["value"] = judgment
        mapped.append(item)
    source = dict(out.get("standalone_projection_source") or {})
    source["opaque_options"] = mapped
    source["stage11554_reroute_gate"] = "all_supported_text_rich_evidence_roles"
    out["standalone_projection_source"] = source
    out["opaque_options"] = mapped
    out["task_type"] = "evidence_candidate_judgment"
    text = str(out.get("input_text") or out.get("prompt_text") or "")
    if "Perspective: evidence_citation" in text:
        text = text.replace("Perspective: evidence_citation", "Perspective: evidence_candidate_judgment")
    out["input_text"] = text
    out["prompt_text"] = text
    return out, True, "rerouted"


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
        gated = []
        reasons: dict[str, int] = {}
        rerouted_count = 0
        for row in original:
            mapped, did, reason = all_supported_text_rich_reroute(row)
            reasons[reason] = reasons.get(reason, 0) + 1
            rerouted_count += int(did)
            gated.append(mapped)
        rowsets[name] = {"original": original, "gated": gated, "rerouted_rows": rerouted_count, "route_reasons": reasons}

    model, tokenizer, init_card = load_runtime()
    results = {"runtime_initialization": init_card, "rowsets": {}}
    for rowset_name, payload in rowsets.items():
        base_card = _write_bounded_choice_eval_audit(
            OUT,
            model=model,
            rows=payload["original"],
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=16,
            split_name=f"{rowset_name}_base",
            bounded_choice_aux_source=PRODUCT_SCORER,
            eval_batch_size=8,
        )
        gated_card = _write_bounded_choice_eval_audit(
            OUT,
            model=model,
            rows=payload["gated"],
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=16,
            split_name=f"{rowset_name}_gated",
            bounded_choice_aux_source=PRODUCT_SCORER,
            eval_batch_size=8,
        )
        base = metric(base_card)
        gated = metric(gated_card)
        results["rowsets"][rowset_name] = {
            "rerouted_rows": payload["rerouted_rows"],
            "route_reasons": payload["route_reasons"],
            "base": base,
            "gated": gated,
            "delta_correct": (gated.get("correct") or 0) - (base.get("correct") or 0),
        }

    rowsets_out = results["rowsets"]
    gates = {
        "web_heldout_improves": rowsets_out["web_heldout"]["delta_correct"] > 0,
        "filtered_strict_not_regressed": rowsets_out["filtered_strict"]["gated"]["correct"] == rowsets_out["filtered_strict"]["base"]["correct"],
        "old_canary_strict_not_regressed": rowsets_out["old_canary_strict"]["gated"]["correct"] == rowsets_out["old_canary_strict"]["base"]["correct"],
        "residual_not_regressed": rowsets_out["residual_bank"]["gated"]["correct"] >= rowsets_out["residual_bank"]["base"]["correct"],
        "full_coverage_preserved": all(item["gated"]["coverage"] == 1.0 for item in rowsets_out.values()),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "text_rich_bridge_postrun_gate_promising" if all(gates.values()) else "text_rich_bridge_postrun_gate_not_promotable",
        "product_scorer": PRODUCT_SCORER,
        "results": results,
        "gates": gates,
        "claim_boundary": [
            "Inference-side routing audit only; product scorer contract is unchanged.",
            "Gate requires evidence_citation rows with non-empty option text and every option value mapped to a supported evidence judgment bucket.",
            "A positive result supports adding this gate to a product scorer policy and rerunning full Gemma comparison.",
        ],
        "source_artifacts": {"runtime": rel(RUNTIME), **{f"rowset_{key}": rel(path) for key, path in ROWSETS.items()}},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "gates": gates, "rowsets": rowsets_out}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
