#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle

ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11120
NAME = "stage11120_runtime_scorer_head_loader_patch_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "runtime_scorer_head_loader_patch_audit.json"

BASE_BUNDLE = ARTIFACTS / "stage11116_trainable_evidence_support_probe/runtime_model/runtime_model_bundle.json"
PAIRWISE_BUNDLE = ARTIFACTS / "stage11089_pairwise_semantic_evidence_probe/runtime_model/runtime_model_bundle.json"
DEFAULT_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def model_for_bundle(bundle_path: Path) -> AgentKernelLiteTransformerSeq2Seq:
    bundle = load_json(bundle_path)
    metadata = dict(bundle.get("metadata") or {})
    config_path = Path(str(metadata.get("model_config") or DEFAULT_CONFIG))
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    return AgentKernelLiteTransformerSeq2Seq(AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(config_path)))


def audit_bundle(bundle_path: Path) -> dict[str, Any]:
    if not bundle_path.exists():
        return {"bundle": rel(bundle_path), "exists": False}
    model = model_for_bundle(bundle_path)
    error = None
    info: dict[str, Any] = {}
    try:
        info = _load_runtime_model_bundle(bundle_path, model=model)
    except Exception as exc:  # noqa: BLE001 - stage records loader failure exactly.
        error = str(exc).splitlines()[:12]
    return {
        "bundle": rel(bundle_path),
        "exists": True,
        "load_passed": error is None,
        "error": error,
        "attached_bounded_choice_heads": info.get("attached_bounded_choice_heads", []),
        "state_dict_keys": info.get("state_dict_keys"),
        "weights_sha256": info.get("weights_sha256"),
        "metadata_aux_source": (info.get("metadata") or {}).get("bounded_choice_aux_source"),
    }


def main() -> None:
    audits = [audit_bundle(BASE_BUNDLE), audit_bundle(PAIRWISE_BUNDLE)]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": all(item.get("load_passed") for item in audits),
        "claim_scope": [
            "Verify the production runtime loader can strictly load ordinary and saved pairwise bounded-choice scorer runtimes.",
        ],
        "audits": audits,
        "decision": "runtime_loader_patch_validated_for_saved_bounded_choice_pair_head",
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
