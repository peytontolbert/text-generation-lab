from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


AUTHORITY_CLOSED = {
    "model_execution": False,
    "training": False,
    "adapter_training": False,
    "runtime": False,
    "decoder_ce": False,
    "denoise_ce": False,
    "checkpoint_export": False,
    "promotion_ready": False,
}

SAFE_ROUTES = {
    "USE_BASE_SHARED",
    "ROUTE_LANGUAGE_ADAPTER_SHADOW",
    "ROUTE_TASK_ADAPTER_SHADOW",
    "ROUTE_REPO_ADAPTER_SHADOW",
    "ROUTE_COMPOSED_ADAPTER_SHADOW",
    "REQUEST_SLICE_EVIDENCE",
    "ABSTAIN_ADAPTER_ROUTE",
}

DEFAULT_INVENTORY = {
    "language": {
        "python": "adapter_language_python",
        "rust": "adapter_language_rust",
        "c_family": "adapter_language_c_family",
        "web_js_ts_html": "adapter_language_web",
    },
    "task": {
        "repo_repair": "adapter_task_repo_repair",
        "repo_qa_or_maintainer": "adapter_task_repo_qa",
        "code_generation": "adapter_task_code_generation",
        "verifier_repair": "adapter_task_verifier_repair",
    },
    "repo": {
        "test_heavy": "adapter_repo_test_heavy",
        "dependency_heavy": "adapter_repo_dependency_heavy",
        "frontend": "adapter_repo_frontend",
    },
}


def _float(row: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def _bool(row: Mapping[str, Any], key: str) -> bool:
    return bool(row.get(key))


def _mapping(row: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = row.get(key)
    return value if isinstance(value, Mapping) else {}


def normalize_router_packet(row: Mapping[str, Any]) -> dict[str, Any]:
    slice_quality = _mapping(row, "slice_quality")
    confidence = _mapping(row, "confidence")
    authority = _mapping(row, "authority")
    return {
        "row_id": str(row.get("row_id") or row.get("id") or ""),
        "language_family": str(row.get("language_family") or "unknown"),
        "task_family": str(row.get("task_family") or row.get("surface") or "unknown"),
        "repo_family": str(row.get("repo_family") or "unknown"),
        "surface_role": str(row.get("surface_role") or "unknown"),
        "language_slice_ready": _bool(slice_quality, "language_ready") or _bool(row, "language_slice_ready"),
        "task_slice_ready": _bool(slice_quality, "task_ready") or _bool(row, "task_slice_ready"),
        "repo_slice_ready": _bool(slice_quality, "repo_ready") or _bool(row, "repo_slice_ready"),
        "language_confidence": _float(confidence, "language", _float(row, "language_confidence", 0.0)),
        "task_confidence": _float(confidence, "task", _float(row, "task_confidence", 0.0)),
        "repo_confidence": _float(confidence, "repo", _float(row, "repo_confidence", 0.0)),
        "ood_score": _float(row, "ood_score", 0.0),
        "high_confidence_wrong": _bool(row, "high_confidence_wrong"),
        "leak_or_locked": _bool(row, "leak_or_locked") or _bool(row, "internal_leak") or _bool(row, "locked_eval"),
        "authority_true": any(value is True for value in authority.values()) or _bool(row, "authority_true"),
    }


def _adapter_id(kind: str, key: str, inventory: Mapping[str, Mapping[str, str]]) -> str | None:
    values = inventory.get(kind, {})
    return values.get(key) if isinstance(values, Mapping) else None


def router_decision(row: Mapping[str, Any], inventory: Mapping[str, Mapping[str, str]] | None = None) -> dict[str, Any]:
    inv = inventory or DEFAULT_INVENTORY
    s = normalize_router_packet(row)
    reasons: list[str] = []
    selected: list[dict[str, str]] = []

    if s["authority_true"]:
        reasons.append("authority_true")
    if s["leak_or_locked"]:
        reasons.append("leak_or_locked")
    if s["high_confidence_wrong"]:
        reasons.append("high_confidence_wrong")
    if s["ood_score"] >= 0.70:
        reasons.append("ood_score_high")

    language_adapter = _adapter_id("language", s["language_family"], inv)
    task_adapter = _adapter_id("task", s["task_family"], inv)
    repo_adapter = _adapter_id("repo", s["repo_family"], inv)

    if not language_adapter:
        reasons.append("language_adapter_missing")
    if not task_adapter:
        reasons.append("task_adapter_missing")
    if s["repo_family"] != "unknown" and not repo_adapter:
        reasons.append("repo_adapter_missing")

    if not s["language_slice_ready"]:
        reasons.append("language_slice_not_ready")
    if not s["task_slice_ready"]:
        reasons.append("task_slice_not_ready")
    if s["repo_family"] != "unknown" and not s["repo_slice_ready"]:
        reasons.append("repo_slice_not_ready")

    if s["language_confidence"] < 0.55:
        reasons.append("language_confidence_low")
    if s["task_confidence"] < 0.55:
        reasons.append("task_confidence_low")
    if s["repo_family"] != "unknown" and s["repo_confidence"] < 0.55:
        reasons.append("repo_confidence_low")

    if s["authority_true"] or s["leak_or_locked"] or s["high_confidence_wrong"] or s["ood_score"] >= 0.70:
        route = "ABSTAIN_ADAPTER_ROUTE"
    elif not s["language_slice_ready"] or not s["task_slice_ready"]:
        route = "REQUEST_SLICE_EVIDENCE"
    elif not language_adapter or not task_adapter:
        route = "USE_BASE_SHARED"
    else:
        if language_adapter and s["language_confidence"] >= 0.55:
            selected.append({"kind": "language", "adapter_id": language_adapter})
        if task_adapter and s["task_confidence"] >= 0.55:
            selected.append({"kind": "task", "adapter_id": task_adapter})
        if repo_adapter and s["repo_slice_ready"] and s["repo_confidence"] >= 0.65:
            selected.append({"kind": "repo", "adapter_id": repo_adapter})

        if len(selected) >= 2:
            route = "ROUTE_COMPOSED_ADAPTER_SHADOW"
        elif selected and selected[0]["kind"] == "language":
            route = "ROUTE_LANGUAGE_ADAPTER_SHADOW"
        elif selected and selected[0]["kind"] == "task":
            route = "ROUTE_TASK_ADAPTER_SHADOW"
        elif selected and selected[0]["kind"] == "repo":
            route = "ROUTE_REPO_ADAPTER_SHADOW"
        else:
            route = "USE_BASE_SHARED"

    adapter_shadow_allowed = route.startswith("ROUTE_") and route.endswith("_SHADOW")
    return {
        "row_id": s["row_id"],
        "route": route,
        "safe_route": route in SAFE_ROUTES,
        "selected_adapters": selected if adapter_shadow_allowed else [],
        "adapter_shadow_allowed": adapter_shadow_allowed,
        "adapter_training_authorized": False,
        "model_execution_authorized": False,
        "decoder_ce_authorized": False,
        "reasons": sorted(set(reasons)),
        "signals": s,
        "authority": AUTHORITY_CLOSED,
    }


def router_card(rows: list[Mapping[str, Any]], inventory: Mapping[str, Mapping[str, str]] | None = None) -> dict[str, Any]:
    decisions = [router_decision(row, inventory=inventory) for row in rows]
    route_counts: dict[str, int] = {}
    adapter_counts: dict[str, int] = {}
    for decision in decisions:
        route_counts[decision["route"]] = route_counts.get(decision["route"], 0) + 1
        for adapter in decision["selected_adapters"]:
            adapter_id = adapter["adapter_id"]
            adapter_counts[adapter_id] = adapter_counts.get(adapter_id, 0) + 1
    unsafe = [
        d for d in decisions
        if not d["safe_route"] or d["adapter_training_authorized"] or d["model_execution_authorized"] or d["decoder_ce_authorized"]
    ]
    return {
        "rows": len(decisions),
        "route_counts": dict(sorted(route_counts.items())),
        "adapter_counts": dict(sorted(adapter_counts.items())),
        "unsafe_decisions": len(unsafe),
        "adapter_shadow_rows": sum(1 for d in decisions if d["adapter_shadow_allowed"]),
        "decisions": decisions,
        "authority": AUTHORITY_CLOSED,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="No-execution MoE/LoRA adapter router contract with conservative slice gates.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = read_jsonl(args.input) if args.input else [
        {"row_id": "ok", "language_family": "python", "task_family": "repo_repair", "repo_family": "test_heavy", "language_slice_ready": True, "task_slice_ready": True, "repo_slice_ready": True, "language_confidence": .9, "task_confidence": .85, "repo_confidence": .8},
        {"row_id": "needs_slice", "language_family": "rust", "task_family": "repo_repair", "language_slice_ready": False, "task_slice_ready": True, "language_confidence": .8, "task_confidence": .8},
    ]
    card = router_card(rows)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
