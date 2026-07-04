from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
IMPLEMENTATION_PATHS = {
    "scaffold": ROOT / "legacy_src/agentkernel_lite/modeling.py",
    "transformer": ROOT / "legacy_src/agentkernel_lite/modeling_transformer.py",
}
REQUIRED_FEATURES = ["has_rotary", "has_agent_policy_heads", "has_retrieval_heads", "has_scalar_invariant"]


def implementation_features(path: Path) -> dict[str, bool]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    low = text.lower()
    return {
        "has_rotary": "rotary" in low or "rope" in low or "apply_rotary" in text,
        "has_agent_policy_heads": "agent_policy" in text or "policy_head" in text or "agent_policy_heads" in text,
        "has_retrieval_heads": "retrieval_query_head" in text and "retrieval_doc_head" in text,
        "has_scalar_invariant": "scalar_invariant" in text,
    }


def target_requires_recovered_transformer(config_path: Path = DEFAULT_TARGET_CONFIG) -> bool:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    cfg = data.get("model_config") or {}
    roles = set(data.get("roles") or [])
    return bool(
        data.get("model_family") == "agentkernel_lite_encdec_v1"
        and cfg.get("positional") == "apply_rotary"
        and cfg.get("agent_policy_heads") is True
        and int(cfg.get("retrieval_head_dim") or 0) > 0
        and int(cfg.get("scalar_invariant_rank") or 0) > 0
        and "retrieval_embedding_heads" in roles
    )


def evaluate_implementation_selection(
    selected: str,
    *,
    config_path: Path = DEFAULT_TARGET_CONFIG,
    implementation_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    implementation_paths = implementation_paths or IMPLEMENTATION_PATHS
    target_requires = target_requires_recovered_transformer(config_path)
    path = implementation_paths.get(selected)
    features = implementation_features(path) if path is not None else {key: False for key in REQUIRED_FEATURES}
    missing = [key for key in REQUIRED_FEATURES if not features.get(key)]
    errors: list[str] = []
    if selected not in implementation_paths:
        errors.append(f"unknown implementation: {selected}")
    if target_requires and selected != "transformer":
        errors.append("recovered 100M target requires implementation=transformer")
    if target_requires and missing:
        errors.append("selected implementation missing recovered features: " + ",".join(missing))
    return {
        "selected": selected,
        "implementation_path": str(path) if path else None,
        "target_requires_recovered_transformer": target_requires,
        "features": features,
        "missing_features": missing,
        "allowed_for_recovered_100m_target": not errors,
        "errors": errors,
    }


def assert_implementation_allowed(selected: str, *, config_path: Path = DEFAULT_TARGET_CONFIG) -> None:
    result = evaluate_implementation_selection(selected, config_path=config_path)
    if not result["allowed_for_recovered_100m_target"]:
        raise ValueError(f"implementation selection blocked: {result}")
