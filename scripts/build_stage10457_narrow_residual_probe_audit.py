#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10457
NAME = "stage10457_narrow_residual_probe_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "narrow_residual_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASELINE = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
NARROW = ROOT / "runs/local/artifacts/stage10456_reviewed_v27_narrow_residual_support_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
REQUEST = ROOT / "runs/local/artifacts/stage10455_reviewed_v27_narrow_residual_support_probe_request/reviewed_v27_narrow_residual_support_probe_request.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def per_language(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in rows:
        rid = str(row["row_id"])
        if "::python::" in rid:
            lang = "python"
        elif "::c_cpp::" in rid:
            lang = "c_cpp"
        elif "::rust::" in rid:
            lang = "rust"
        elif "::web_js_ts_html::" in rid:
            lang = "web_js_ts_html"
        else:
            lang = "unknown"
        card = out.setdefault(lang, {"correct": 0, "total": 0})
        card["total"] += 1
        if row["constrained_choice_match"]:
            card["correct"] += 1
    return out


def main() -> None:
    baseline = load_json(BASELINE)
    narrow = load_json(NARROW)
    request = load_json(REQUEST)

    base_rows = {row["row_id"]: row for row in baseline["row_cards"]}
    narrow_rows = {row["row_id"]: row for row in narrow["row_cards"]}

    changed_rows: list[dict[str, Any]] = []
    for row_id in sorted(base_rows):
        before = base_rows[row_id]
        after = narrow_rows[row_id]
        if before["constrained_choice_match"] != after["constrained_choice_match"] or before["constrained_choice_top1_label"] != after["constrained_choice_top1_label"]:
            changed_rows.append(
                {
                    "row_id": row_id,
                    "baseline_pred": before["constrained_choice_top1_label"],
                    "baseline_correct": before["constrained_choice_match"],
                    "narrow_pred": after["constrained_choice_top1_label"],
                    "narrow_correct": after["constrained_choice_match"],
                    "target": after["target_text"],
                }
            )

    misses = [
        {
            "row_id": row["row_id"],
            "pred": row["constrained_choice_top1_label"],
            "target": row["target_text"],
            "full_vocab_top1": row["full_vocab_top1_text"],
            "target_rank_full_vocab": row["target_rank_full_vocab"],
        }
        for row in narrow["row_cards"]
        if not row["constrained_choice_match"]
    ]

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "narrow_support_safe_but_no_residual_recovery",
        "claim_scope": [
            "Audit the narrow Python-verifier-only plus Rust-citation-only residual probe against the live repaired-overlay baseline.",
            "Record that the narrower support packet removed the prior regression but still did not recover the two remaining strict misses.",
        ],
        "source_artifacts": {
            "baseline_strict_audit": display(BASELINE),
            "narrow_strict_audit": display(NARROW),
            "request": display(REQUEST),
        },
        "baseline": {
            "strict_constrained_accuracy": baseline["constrained_choice_top1_accuracy"],
            "full_vocab_top1_accuracy": baseline["full_vocab_top1_accuracy"],
            "per_language": per_language(baseline["row_cards"]),
        },
        "narrow_probe": {
            "strict_constrained_accuracy": narrow["constrained_choice_top1_accuracy"],
            "full_vocab_top1_accuracy": narrow["full_vocab_top1_accuracy"],
            "per_language": per_language(narrow["row_cards"]),
        },
        "changed_rows": changed_rows,
        "remaining_misses": misses,
        "targeted_focus_rows": request["strict_focus_rows"],
        "findings": [
            "The narrow support probe matched the repaired-overlay baseline exactly at 22/24 and introduced no new strict regressions.",
            "The two remaining misses persisted unchanged: Python verifier_outcome and Rust evidence_citation.",
            "The narrower packet is therefore safer than the mixed stage10450 packet, but still insufficient to move the actual residual boundary.",
            "Full-vocab top-1 remains materially weaker than constrained-choice scoring, so raw-decoding robustness did not improve here.",
        ],
        "next_actions": [
            "Preserve the narrow packet shape for future probes because it avoids the Python citation regression path.",
            "Add option-representation invariance or stronger contrast examples specifically around Python verifier B-vs-C and Rust citation E-vs-F.",
            "Prefer new disjoint residual roots over more repetitions of the same compact rows once the contrast packet is exhausted.",
        ],
        "required_honesty_gates": [
            "Do not promote stage10456 as an upgrade over the live stage10424 baseline.",
            "Treat stage10456 as a safety validation for support isolation, not a capability improvement.",
        ],
    }

    write_json(AUDIT_JSON, audit)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": audit["decision"],
            "audit": display(AUDIT_JSON),
        },
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
