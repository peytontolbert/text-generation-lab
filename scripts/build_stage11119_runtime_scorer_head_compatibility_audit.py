#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq

ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11119
NAME = "stage11119_runtime_scorer_head_compatibility_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "runtime_scorer_head_compatibility_audit.json"

PAIRWISE_BUNDLE = ARTIFACTS / "stage11089_pairwise_semantic_evidence_probe/runtime_model/runtime_model_bundle.json"
BASE_BUNDLE = ARTIFACTS / "stage11116_trainable_evidence_support_probe/runtime_model/runtime_model_bundle.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def bundle_state_dict(bundle_path: Path) -> tuple[dict[str, Any], dict[str, torch.Tensor]]:
    bundle = load_json(bundle_path)
    weights_path = Path(str(bundle.get("weights_path") or ""))
    if not weights_path.is_absolute():
        weights_path = bundle_path.parent / weights_path
    payload = torch.load(weights_path, map_location="cpu")
    state_dict = payload.get("model_state_dict") if isinstance(payload, dict) and isinstance(payload.get("model_state_dict"), dict) else payload
    if not isinstance(state_dict, dict):
        raise ValueError(f"runtime model payload does not contain a state dict: {weights_path}")
    return bundle, state_dict


def model_from_bundle_metadata(bundle: dict[str, Any]) -> AgentKernelLiteTransformerSeq2Seq:
    metadata = dict(bundle.get("metadata") or {})
    config_path = Path(str(metadata.get("model_config") or ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"))
    return AgentKernelLiteTransformerSeq2Seq(AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(config_path)))


def attach_optional_heads(model: nn.Module, state_dict: dict[str, torch.Tensor]) -> list[str]:
    attached: list[str] = []
    config = getattr(model, "config", None)
    hidden_dim = int(getattr(config, "d_model", 0) or 0)
    if "bounded_choice_probe_head.weight" in state_dict and not hasattr(model, "bounded_choice_probe_head"):
        weight = state_dict["bounded_choice_probe_head.weight"]
        model.bounded_choice_probe_head = nn.Linear(hidden_dim or int(weight.shape[1]), int(weight.shape[0]), bias=False)
        attached.append("bounded_choice_probe_head")
    if "bounded_choice_role_head.weight" in state_dict and not hasattr(model, "bounded_choice_role_head"):
        weight = state_dict["bounded_choice_role_head.weight"]
        model.bounded_choice_role_head = nn.Linear(hidden_dim or int(weight.shape[1]), int(weight.shape[0]), bias=True)
        attached.append("bounded_choice_role_head")
    if "bounded_choice_pair_head.0.weight" in state_dict and not hasattr(model, "bounded_choice_pair_head"):
        first = state_dict["bounded_choice_pair_head.0.weight"]
        last = state_dict.get("bounded_choice_pair_head.2.weight")
        model.bounded_choice_pair_head = nn.Sequential(
            nn.Linear(int(first.shape[1]), int(first.shape[0]), bias=True),
            nn.SiLU(),
            nn.Linear(int(first.shape[0]), int(last.shape[0]) if last is not None else 1, bias=True),
        )
        attached.append("bounded_choice_pair_head")
    return attached


def audit_bundle(bundle_path: Path) -> dict[str, Any]:
    if not bundle_path.exists():
        return {"bundle": rel(bundle_path), "exists": False}
    bundle, state_dict = bundle_state_dict(bundle_path)
    scorer_keys = sorted(key for key in state_dict if key.startswith("bounded_choice_"))
    base_model = model_from_bundle_metadata(bundle)
    strict_error = None
    try:
        base_model.load_state_dict(state_dict, strict=True)
    except Exception as exc:  # noqa: BLE001 - audit captures exact compatibility failure.
        strict_error = str(exc).splitlines()[:8]
    repaired_model = model_from_bundle_metadata(bundle)
    attached = attach_optional_heads(repaired_model, state_dict)
    repaired_error = None
    try:
        repaired_model.load_state_dict(state_dict, strict=True)
    except Exception as exc:  # noqa: BLE001
        repaired_error = str(exc).splitlines()[:8]
    return {
        "bundle": rel(bundle_path),
        "exists": True,
        "metadata_aux_source": (bundle.get("metadata") or {}).get("bounded_choice_aux_source"),
        "scorer_state_keys": scorer_keys,
        "base_strict_load_passed": strict_error is None,
        "base_strict_error": strict_error,
        "attached_heads": attached,
        "repaired_strict_load_passed": repaired_error is None,
        "repaired_strict_error": repaired_error,
    }


def main() -> None:
    audits = [audit_bundle(BASE_BUNDLE), audit_bundle(PAIRWISE_BUNDLE)]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": all(item.get("repaired_strict_load_passed", True) for item in audits),
        "claim_scope": [
            "Prove whether saved dynamic bounded-choice scorer heads can be made strictly reloadable by attaching modules from state_dict key shapes before load.",
        ],
        "audits": audits,
        "decision": "patch_training_loop_loader_to_attach_saved_bounded_choice_heads_before_strict_load",
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
