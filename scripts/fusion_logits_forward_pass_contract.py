from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


AUTHORITY_CLOSED = {
    "model_execution": False,
    "training": False,
    "runtime": False,
    "source_body_emission": False,
    "decoder_ce": False,
    "denoise_ce": False,
    "scoring_authorized": False,
}

SAFE_ROUTES = {
    "ABSTAIN_UNSAFE",
    "RETRIEVE_MORE",
    "REPAIR_STRUCTURED",
    "STRUCTURED_ONLY",
    "ALLOW_BOUNDED_DECODER_SHADOW",
}


def _float(row: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def _bool(row: Mapping[str, Any], key: str) -> bool:
    return bool(row.get(key))


def normalize_signal_packet(row: Mapping[str, Any]) -> dict[str, Any]:
    structured = row.get("structured_heads") if isinstance(row.get("structured_heads"), dict) else {}
    retrieval = row.get("retrieval") if isinstance(row.get("retrieval"), dict) else {}
    verifier = row.get("verifier") if isinstance(row.get("verifier"), dict) else {}
    decoder = row.get("decoder") if isinstance(row.get("decoder"), dict) else {}
    uncertainty = row.get("uncertainty") if isinstance(row.get("uncertainty"), dict) else {}
    authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
    return {
        "row_id": str(row.get("row_id") or row.get("id") or ""),
        "structured_confidence": _float(structured, "confidence", _float(row, "structured_confidence", 0.0)),
        "structured_margin": _float(structured, "margin", _float(row, "structured_margin", 0.0)),
        "retrieval_confidence": _float(retrieval, "confidence", _float(row, "retrieval_confidence", 0.0)),
        "retrieval_coverage": _float(retrieval, "coverage", _float(row, "retrieval_coverage", 0.0)),
        "verifier_pass": _bool(verifier, "pass") or _bool(row, "verifier_pass"),
        "verifier_confidence": _float(verifier, "confidence", _float(row, "verifier_confidence", 0.0)),
        "verifier_failure": str(verifier.get("failure") or row.get("verifier_failure") or ""),
        "decoder_confidence": _float(decoder, "confidence", _float(row, "decoder_confidence", 0.0)),
        "decoder_budget_ok": _bool(decoder, "budget_ok") or _bool(row, "decoder_budget_ok"),
        "decoder_schema_ok": _bool(decoder, "schema_ok") or _bool(row, "decoder_schema_ok"),
        "ood_score": _float(uncertainty, "ood_score", _float(row, "ood_score", 0.0)),
        "entropy": _float(uncertainty, "entropy", _float(row, "entropy", 0.0)),
        "high_confidence_wrong": _bool(uncertainty, "high_confidence_wrong") or _bool(row, "high_confidence_wrong"),
        "internal_leak": _bool(row, "internal_leak"),
        "authority_true": any(value is True for value in authority.values()) or _bool(row, "authority_true"),
    }


def fusion_decision(row: Mapping[str, Any]) -> dict[str, Any]:
    s = normalize_signal_packet(row)
    reasons: list[str] = []

    if s["authority_true"]:
        reasons.append("authority_true")
    if s["internal_leak"]:
        reasons.append("internal_leak")
    if s["high_confidence_wrong"]:
        reasons.append("high_confidence_wrong")
    if s["ood_score"] >= 0.75:
        reasons.append("ood_score_high")
    if s["retrieval_coverage"] < 0.45:
        reasons.append("retrieval_coverage_low")
    if s["retrieval_confidence"] < 0.35:
        reasons.append("retrieval_confidence_low")
    if s["verifier_failure"]:
        reasons.append(f"verifier_failure:{s['verifier_failure']}")
    if s["structured_confidence"] < 0.45:
        reasons.append("structured_confidence_low")
    if not s["decoder_budget_ok"]:
        reasons.append("decoder_budget_not_ok")
    if not s["decoder_schema_ok"]:
        reasons.append("decoder_schema_not_ok")

    fused_confidence = (
        0.30 * s["structured_confidence"]
        + 0.25 * s["retrieval_confidence"]
        + 0.20 * s["retrieval_coverage"]
        + 0.15 * s["verifier_confidence"]
        + 0.10 * s["decoder_confidence"]
        - 0.25 * s["ood_score"]
    )
    fused_confidence = max(0.0, min(1.0, fused_confidence))

    if s["authority_true"] or s["internal_leak"]:
        route = "ABSTAIN_UNSAFE"
    elif s["high_confidence_wrong"] or s["ood_score"] >= 0.75:
        route = "REPAIR_STRUCTURED"
    elif s["retrieval_coverage"] < 0.45 or s["retrieval_confidence"] < 0.35:
        route = "RETRIEVE_MORE"
    elif s["verifier_failure"]:
        route = "REPAIR_STRUCTURED"
    elif (
        fused_confidence >= 0.70
        and s["structured_confidence"] >= 0.70
        and s["retrieval_coverage"] >= 0.70
        and s["verifier_pass"]
        and s["decoder_budget_ok"]
        and s["decoder_schema_ok"]
        and s["ood_score"] < 0.35
    ):
        route = "ALLOW_BOUNDED_DECODER_SHADOW"
    else:
        route = "STRUCTURED_ONLY"

    decoder_shadow_allowed = route == "ALLOW_BOUNDED_DECODER_SHADOW"
    return {
        "row_id": s["row_id"],
        "route": route,
        "safe_route": route in SAFE_ROUTES,
        "fused_confidence": round(fused_confidence, 6),
        "decoder_shadow_allowed": decoder_shadow_allowed,
        "decoder_ce_authorized": False,
        "model_execution_authorized": False,
        "signals": s,
        "reasons": sorted(set(reasons)),
        "authority": AUTHORITY_CLOSED,
    }


def fusion_card(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    decisions = [fusion_decision(row) for row in rows]
    route_counts: dict[str, int] = {}
    for decision in decisions:
        route_counts[decision["route"]] = route_counts.get(decision["route"], 0) + 1
    unsafe = [d for d in decisions if not d["safe_route"] or d["decoder_ce_authorized"] or d["model_execution_authorized"]]
    return {
        "rows": len(decisions),
        "route_counts": dict(sorted(route_counts.items())),
        "unsafe_decisions": len(unsafe),
        "decoder_shadow_rows": sum(1 for d in decisions if d["decoder_shadow_allowed"]),
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
    parser = argparse.ArgumentParser(description="No-execution fusion contract for structured heads, retrieval, verifier, uncertainty, and decoder readiness.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = read_jsonl(args.input) if args.input else [
        {"row_id": "ok", "structured_confidence": .9, "retrieval_confidence": .9, "retrieval_coverage": .9, "verifier_pass": True, "verifier_confidence": .8, "decoder_confidence": .8, "decoder_budget_ok": True, "decoder_schema_ok": True},
        {"row_id": "missing", "structured_confidence": .8, "retrieval_confidence": .2, "retrieval_coverage": .2},
    ]
    card = fusion_card(rows)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
