from __future__ import annotations

import argparse
import json
import re
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

INTERNAL_TOKEN_RE = re.compile(r"<(?:MT|COPY|SEM|CTRL|PLAN|MNSB|PYPLAN)[^>]*>|POLICY_|CONTROL_|INTERNAL_|decoder_control")
REPEAT_RE = re.compile(r"\b(\w{3,})\b(?:\s+\1\b){3,}", re.I)

REPAIR_ACTIONS = {
    "REPAIR_INTERNAL_LEAK": "mask_internal_control_tokens",
    "REPAIR_SHORT_OUTPUT": "expand_missing_semantic_spans",
    "REPAIR_REPETITION": "mask_repeated_spans",
    "REPAIR_WRONG_SURFACE": "remask_surface_and_style",
    "ABSTAIN_UNRECOVERABLE": "abstain_without_denoise",
}


def detect_bad_output_features(text: str) -> dict[str, bool]:
    stripped = text.strip()
    return {
        "internal_leak": bool(INTERNAL_TOKEN_RE.search(text)),
        "short_output": bool(stripped and len(stripped.split()) <= 3),
        "repetition": bool(REPEAT_RE.search(text)),
        "empty_output": not stripped,
        "looks_like_wrong_surface": stripped.startswith("{") or stripped.startswith("<") or "Traceback (" in text,
    }


def choose_repair_route(features: Mapping[str, bool], verifier_failure: str = "") -> str:
    if features.get("internal_leak"):
        return "REPAIR_INTERNAL_LEAK"
    if features.get("repetition"):
        return "REPAIR_REPETITION"
    if features.get("short_output") or features.get("empty_output"):
        return "REPAIR_SHORT_OUTPUT"
    if features.get("looks_like_wrong_surface") or verifier_failure in {"wrong_surface", "schema_failure"}:
        return "REPAIR_WRONG_SURFACE"
    if verifier_failure in {"unsafe", "unrecoverable", "locked_eval", "authority_open"}:
        return "ABSTAIN_UNRECOVERABLE"
    return "REPAIR_WRONG_SURFACE"


def mask_spans(text: str, route: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    if route == "REPAIR_INTERNAL_LEAK":
        for match in INTERNAL_TOKEN_RE.finditer(text):
            spans.append({"start": match.start(), "end": match.end(), "reason": "internal_control_token"})
    elif route == "REPAIR_REPETITION":
        for match in REPEAT_RE.finditer(text):
            spans.append({"start": match.start(), "end": match.end(), "reason": "degenerate_repetition"})
    elif route == "REPAIR_SHORT_OUTPUT":
        spans.append({"start": len(text), "end": len(text), "reason": "missing_semantic_content"})
    elif route == "REPAIR_WRONG_SURFACE":
        spans.append({"start": 0, "end": len(text), "reason": "wrong_surface_full_remask"})
    return spans


def build_repair_plan(row: Mapping[str, Any]) -> dict[str, Any]:
    row_id = str(row.get("row_id") or row.get("id") or "")
    bad_output = str(row.get("bad_output") or row.get("candidate_output") or row.get("output") or "")
    verifier_failure = str(row.get("verifier_failure") or "")
    authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
    authority_true = any(value is True for value in authority.values()) or bool(row.get("authority_true"))
    features = detect_bad_output_features(bad_output)
    route = "ABSTAIN_UNRECOVERABLE" if authority_true else choose_repair_route(features, verifier_failure)
    spans = [] if route == "ABSTAIN_UNRECOVERABLE" else mask_spans(bad_output, route)
    max_steps = int(row.get("max_repair_steps", 3) or 3)
    max_steps = max(1, min(max_steps, 8))
    repair_steps = []
    for step in range(max_steps):
        repair_steps.append({
            "step": step,
            "operation": REPAIR_ACTIONS[route],
            "uses_verifier_feedback": True,
            "remask_policy": "remask_failed_spans_only" if step else "initial_mask",
        })
        if route == "ABSTAIN_UNRECOVERABLE":
            break
    denoise_candidate_eligible = bool(spans and route != "ABSTAIN_UNRECOVERABLE" and not authority_true)
    return {
        "row_id": row_id,
        "route": route,
        "bad_output_features": features,
        "mask_spans": spans,
        "repair_steps": repair_steps,
        "denoise_candidate_eligible": denoise_candidate_eligible,
        "denoise_ce_authorized": False,
        "decoder_ce_authorized": False,
        "model_execution_authorized": False,
        "authority": AUTHORITY_CLOSED,
    }


def repair_contract_card(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    plans = [build_repair_plan(row) for row in rows]
    route_counts: dict[str, int] = {}
    for plan in plans:
        route_counts[plan["route"]] = route_counts.get(plan["route"], 0) + 1
    unsafe = [p for p in plans if p["denoise_ce_authorized"] or p["decoder_ce_authorized"] or p["model_execution_authorized"]]
    return {
        "rows": len(plans),
        "route_counts": dict(sorted(route_counts.items())),
        "denoise_candidate_rows": sum(1 for p in plans if p["denoise_candidate_eligible"]),
        "denoise_ce_rows": sum(1 for p in plans if p["denoise_ce_authorized"]),
        "decoder_ce_rows": sum(1 for p in plans if p["decoder_ce_authorized"]),
        "unsafe_authority_rows": len(unsafe),
        "plans": plans,
        "authority": AUTHORITY_CLOSED,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="No-execution denoise/diffusion repair contract for bad-output repair planning.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = read_jsonl(args.input) if args.input else [
        {"row_id": "leak", "bad_output": "<SEM_SLOT_X> POLICY_CONTINUE"},
        {"row_id": "short", "bad_output": "def f("},
    ]
    card = repair_contract_card(rows)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
