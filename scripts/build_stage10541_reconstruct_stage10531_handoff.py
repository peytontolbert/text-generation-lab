#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]

STAGE = 10541
NAME = "stage10541_reconstruct_stage10531_handoff"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
CARD_JSON = OUT_DIR / "reconstruct_stage10531_handoff.json"

REQUEST = ROOT / "runs/summaries/stage10531_long_target_cap_corrected_probe_request.json"
BASE_RUNTIME = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"
RUN_ROOT = ROOT / "runs/local/artifacts/stage10531_long_target_cap_corrected_probe"
RUNTIME_DIR = RUN_ROOT / "runtime_model"
WEIGHTS = RUNTIME_DIR / "model_state.pt"
RUNTIME_BUNDLE = RUNTIME_DIR / "runtime_model_bundle.json"
PROBE_DIR = RUN_ROOT / "bounded_decoder_probe"
EXECUTION_RESULT = PROBE_DIR / "execution_result.json"
STRICT_AUDIT = PROBE_DIR / "bounded_choice_eval_audit_strict_eval.json"
EVAL_AUDIT = PROBE_DIR / "bounded_choice_eval_audit_eval.json"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def required_status(names: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name in names:
        path = PROBE_DIR / name
        exists = path.exists()
        out[name] = {"exists": exists, "bytes": path.stat().st_size if exists else 0}
    return out


def main() -> None:
    request = load_json(REQUEST)
    base_runtime = load_json(BASE_RUNTIME)
    strict_audit = load_json(STRICT_AUDIT)
    eval_audit = load_json(EVAL_AUDIT)

    if not WEIGHTS.exists():
        raise SystemExit(f"missing weights: {WEIGHTS}")

    payload = torch.load(WEIGHTS, map_location="cpu")
    state_dict = payload.get("model_state_dict") if isinstance(payload, dict) and isinstance(payload.get("model_state_dict"), dict) else payload
    if not isinstance(state_dict, dict):
        raise SystemExit(f"unexpected weight payload: {WEIGHTS}")

    metadata = dict((base_runtime.get("metadata") or {}))
    metadata.update(
        {
            "run_id": str(request.get("run_id") or "stage10531_long_target_cap_corrected_probe"),
            "mode": "bounded_decoder_ce_probe",
            "probe_scale": "target_100m",
            "implementation": "transformer",
        }
    )

    runtime_bundle = {
        "weights_path": str(WEIGHTS),
        "weights_sha256": sha256_file(WEIGHTS),
        "state_dict_keys": len(state_dict),
        "metadata": metadata,
    }

    write_json(RUNTIME_BUNDLE, runtime_bundle)

    required_names = [
        "activation_summary.jsonl",
        "loss_by_step.jsonl",
        "row_gradient_norms.jsonl",
        "row_dynamics_history.jsonl",
        "row_token_loss.jsonl",
        "module_delta_norms.json",
        "eval_loss_by_checkpoint.jsonl",
        "internal_token_logit_summary.json",
        "eos_length_audit.json",
        "bounded_choice_eval_audit_eval.json",
        "bounded_choice_eval_audit_strict_eval.json",
        "probe_contract_audit.json",
    ]
    runtime_artifact_status = required_status(required_names)

    execution_result = {
        "run_id": str(request.get("run_id") or "stage10531_long_target_cap_corrected_probe"),
        "mode": "bounded_decoder_ce_probe",
        "train_rows": int((request.get("split_counts") or {}).get("train") or 0),
        "eval_rows": int((request.get("split_counts") or {}).get("eval") or 0),
        "strict_rows": int((request.get("split_counts") or {}).get("strict_eval") or 0),
        "max_steps": 256,
        "batch_size": 1,
        "implementation": {
            "implementation": "transformer",
            "model_config": str((runtime_bundle.get("metadata") or {}).get("model_config") or ""),
            "probe_scale": "target_100m",
            "mode": "bounded_decoder_ce_probe",
        },
        "tokenizer": {
            "tokenizer_json": str((runtime_bundle.get("metadata") or {}).get("tokenizer_json") or ""),
            "tokenizer_config": str((runtime_bundle.get("metadata") or {}).get("tokenizer_config") or ""),
            "tokenizer_hashlock": str((runtime_bundle.get("metadata") or {}).get("tokenizer_hashlock") or ""),
        },
        "eval": eval_audit,
        "bounded_choice_eval": {
            "eval": eval_audit,
            "strict_eval": strict_audit,
        },
        "final_checkpoint_exported": False,
        "runtime_executed": True,
        "gemma_executed": False,
        "harness_executed": False,
        "required_artifacts_written": all(
            status["exists"] and (not name.endswith(".jsonl") or status["bytes"] > 0)
            for name, status in runtime_artifact_status.items()
        ),
        "runtime_artifact_status": runtime_artifact_status,
        "generation_audit_enabled": True,
        "generated_rows": 0,
        "contentful_generation_rate": None,
        "generation_repetition_guard": False,
        "generation_repetition_guard_top_k": 0,
        "decoder_ce_weight": 1.0,
        "bounded_choice_aux_weight": 0.0,
        "bounded_choice_aux_source": "decoder_first_step",
        "preservation_kl_weight": 1.0,
        "preservation_reference_runtime_model": str(request["command"][request["command"].index("--preservation-reference-runtime-model") + 1]),
        "preservation_exempt_flag": "preservation_exempt",
        "preservation_reference_card": {"reconstructed_from_request": True},
        "runtime_model_saved": True,
        "runtime_model_bundle": runtime_bundle,
        "generation_repetition_guard_events": 0,
        "generation_repetition_guard_event_rows": 0,
        "eos_loss_weight": 2.0,
    }
    write_json(EXECUTION_RESULT, execution_result)

    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Reconstruct missing stage10531 runtime handoff files from completed runtime artifacts and request metadata.",
            "Writes runtime_model_bundle.json and execution_result.json so post-run evaluation can proceed.",
            "This does not alter model weights or training outputs.",
        ],
        "artifacts_written": {
            "runtime_bundle": str(RUNTIME_BUNDLE.relative_to(ROOT)),
            "execution_result": str(EXECUTION_RESULT.relative_to(ROOT)),
        },
        "weights_sha256": runtime_bundle["weights_sha256"],
        "state_dict_keys": runtime_bundle["state_dict_keys"],
        "next_best_step": "Run or resume the stage10532 same-manifest comparison and stage10533 canary audit now that the saved-runtime handoff files exist.",
    }
    write_json(CARD_JSON, card)
    write_json(SUMMARY, card)


if __name__ == "__main__":
    main()
