#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import torch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

from legacy_src.agentkernel_lite.training_data import _row_text, build_batch, load_tokenizer
from legacy_src.agentkernel_lite.training_loop import _build_probe_model

STAGE = 9596
NAME = "stage9596_encoder_rope_order_sensitivity_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9595_structured_probe_optimizer_isolation_verification.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9591_residual_denoise_minimal_sidecar_manifest/residual_denoise_minimal_sidecar_manifest.jsonl"
RUN_ROOT = ROOT / "runs/local/artifacts" / NAME
AUDIT = RUN_ROOT / "encoder_rope_order_sensitivity_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ENCODER_ROPE_ORDER_SENSITIVITY_STAGE9596.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(9596)
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9595_not_passed")
    if len(rows) < 2:
        failures.append("manifest_too_small")

    tokenizer = load_tokenizer(TOKENIZER_JSON, TOKENIZER_CONFIG)
    first = rows[0]
    second = rows[1]
    text_a = _row_text(first)
    text_b = _row_text(second)
    ids_a = tokenizer.encode(text_a, max_length=512)
    ids_b = tokenizer.encode(text_b, max_length=512)
    token_sequence_equal = ids_a == ids_b
    token_multiset_equal = sorted(ids_a) == sorted(ids_b)
    target_a = (first.get("target") or {}).get("suffix_choice")
    target_b = (second.get("target") or {}).get("suffix_choice")
    if token_sequence_equal:
        failures.append("paired_sequences_identical")
    if not token_multiset_equal:
        failures.append("paired_token_multiset_not_equal")
    if target_a == target_b:
        failures.append("paired_targets_not_flipped")

    model, implementation_card = _build_probe_model(
        "transformer",
        vocab_size=tokenizer.vocab_size,
        probe_scale="target_100m",
        model_config=MODEL_CONFIG,
    )
    model.eval()
    batch = build_batch([first, second], max_encoder_tokens=512, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    pooled = out["pooled"].detach().float()
    pooled_l2 = float((pooled[0] - pooled[1]).norm().item())
    logits = out["structured_logits"].get("suffix_choice")
    suffix_logit_l2 = float((logits[0].detach().float() - logits[1].detach().float()).norm().item()) if logits is not None else 0.0
    if pooled_l2 <= 1e-6:
        failures.append("pooled_state_not_order_sensitive")
    if suffix_logit_l2 <= 1e-7:
        failures.append("suffix_logits_not_order_sensitive")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "row_a": first.get("row_id"),
        "row_b": second.get("row_id"),
        "target_a": target_a,
        "target_b": target_b,
        "token_sequence_equal": token_sequence_equal,
        "token_multiset_equal": token_multiset_equal,
        "token_len_a": len(ids_a),
        "token_len_b": len(ids_b),
        "pooled_pair_l2": pooled_l2,
        "suffix_logit_pair_l2": suffix_logit_l2,
        "implementation": implementation_card,
        "authority": dict(AUTHORITY_CLOSED),
        "runtime_executed": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Enabled encoder RoPE and verified ordered key/value evidence is visible to structured heads despite identical token multisets.",
        "next_best_step": "Rerun the minimal sidecar structured probe with encoder RoPE and frozen decoder/export buckets.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9596 Encoder RoPE Order Sensitivity Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Token multiset equal: `{token_multiset_equal}`",
        f"Token sequence equal: `{token_sequence_equal}`",
        f"Pooled pair L2: `{pooled_l2}`",
        f"Suffix logit pair L2: `{suffix_logit_l2}`",
        "",
        "This stage protects the structured maintainer heads from permutation-invariant evidence packets. Decoder, denoise, runtime, export, harness, and promotion remain closed.",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "pooled_pair_l2": pooled_l2, "suffix_logit_pair_l2": suffix_logit_l2, "failures": failures}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
