#!/usr/bin/env python3
"""Roll up Stage11981 and Stage11986 transition support rows with floor accounting."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11987
NAME = "stage11987_transition_support_rollup_v2"
OUT = ART / NAME
SUMMARY = OUT / "transition_support_rollup_v2.json"
ROWS = OUT / "transition_support_rows_v2.jsonl"
SOURCE_A = ART / "stage11981_multilingual_transition_support_rollup/multilingual_transition_support_rows.jsonl"
SOURCE_B = ART / "stage11986_transition_root_250_second_batch_admission_audit/transition_root_250_second_batch_admitted_rows.jsonl"
LANG_FLOORS = {"python": 50, "rust": 50, "c_cpp": 50, "web_js_ts_html": 50}
STATUS_FLOORS = {
    "FAIL_TO_PASS": 50,
    "PASS_TO_PASS": 100,
    "PASS_CURRENT_BUILD": 40,
    "PASS_CURRENT_BUILD_AND_RUN": 40,
    "INSUFFICIENT_EVIDENCE": 40,
    "NOT_EXERCISED": 40,
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def normalize(row: dict[str, Any], source: str) -> dict[str, Any]:
    out = dict(row)
    out["row_id"] = f"{row.get('row_id')}::stage11987_{source}"
    out["split"] = "train"
    out["split_role"] = "stage11987_transition_support_v2_train_support_only"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["source_heldout_admissible"] = False
    out["stage11987_source"] = source
    source_obj = dict(out.get("standalone_projection_source") or {})
    source_obj.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = source_obj
    if not isinstance(out.get("target"), dict):
        label = out.get("bounded_choice_target_label") or out.get("target_text") or out.get("decoder_text")
        out["bounded_choice_target_label"] = label
        out["target_text"] = label
        out["decoder_text"] = label
        out["target"] = {"bounded_choice_target_label": label, "decoder_text": label, "semantic_value": out.get("observed_verifier_transition") or label}
    out.setdefault("loss_mask", {"bounded_choice_aux": True, "decoder_ce": True, "structured_aux": True, "transition_projection": True})
    return out


def remaining(floors: dict[str, int], counts: Counter[str]) -> dict[str, int]:
    return {key: max(0, floor - int(counts.get(key, 0))) for key, floor in floors.items()}


def main() -> None:
    a = [normalize(row, "stage11981") for row in read_jsonl(SOURCE_A)]
    b = [normalize(row, "stage11986") for row in read_jsonl(SOURCE_B)]
    rows = a + b
    write_jsonl(ROWS, rows)
    lang_counts = Counter(str(r.get("language_family") or "unknown") for r in rows)
    status_counts = Counter(str(r.get("observed_verifier_transition") or "unknown") for r in rows)
    repo_counts = Counter(str(r.get("repo_family") or r.get("repo_id") or "unknown") for r in rows)
    source_counts = Counter(str(r.get("stage11987_source")) for r in rows)
    unique_roots = {str(r.get("root_lineage_key") or r.get("root_id") or r.get("source_root_id") or r.get("row_id")) for r in rows}
    train_ready = (
        len(rows) >= 80
        and len(unique_roots) >= 40
        and all(lang_counts.get(lang, 0) >= 20 for lang in ["python", "rust", "c_cpp", "web_js_ts_html"])
        and status_counts.get("PASS_TO_PASS", 0) >= 20
        and status_counts.get("PASS_CURRENT_BUILD", 0) >= 20
    )
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "transition_support_v2_ready_for_diagnostic_only" if rows else "transition_support_v2_empty",
        "claim_boundary": "Combined support remains train-support/diagnostic only; it is still far below Transition-Root-250 floors and not source-heldout.",
        "source_artifacts": {"stage11981": rel(SOURCE_A), "stage11986": rel(SOURCE_B)},
        "summary": {
            "rows": len(rows),
            "unique_roots": len(unique_roots),
            "language_counts": dict(lang_counts),
            "status_counts": dict(status_counts),
            "repo_family_counts": dict(repo_counts),
            "source_counts": dict(source_counts),
            "remaining_to_floor": {"language_remaining": remaining(LANG_FLOORS, lang_counts), "status_remaining": remaining(STATUS_FLOORS, status_counts)},
            "train_package_ready": train_ready,
        },
        "do_not_train_as_frontier_reasons": [
            "root count is below Transition-Root-250 minimum",
            "web admitted rows are still absent",
            "FAIL_TO_PASS rows are controlled fixtures rather than broad source-heldout roots",
            "PASS_CURRENT_BUILD_AND_RUN, INSUFFICIENT_EVIDENCE, and NOT_EXERCISED floors remain unfilled",
        ],
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS)},
        "next_stage_recommendation": {
            "stage": "stage11988_web_and_status_gap_materialization_plan",
            "action": "Target web rows and missing verifier statuses with real executable roots; do not run another model probe from this thin package unless explicitly diagnostic.",
        },
    }
    write_json(SUMMARY, artifact)
    print(json.dumps({"decision": artifact["decision"], "summary": artifact["summary"], "next": artifact["next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
