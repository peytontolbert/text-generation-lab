#!/usr/bin/env python3
"""Write decision and delta analysis for Stage11952 replay-balanced probe."""

from __future__ import annotations

import json
import shutil
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11954
NAME = "stage11954_transition_1k_v2_replay_decision"
OUT = ART / NAME
SUMMARY = OUT / "transition_1k_v2_replay_decision.json"

AUDIT = ART / "stage11953_transition_1k_v2_replay_balanced_audit/transition_1k_v2_replay_balanced_audit.json"
OLD_ROWS = ART / "stage11897_transition_record_projection_rows/transition_projection_rows.jsonl"
V2_ROWS = ART / "stage11945_transition_1k_v2_multisource_package/transition_projection_rows_v2.jsonl"
AUDIT_DIR = ART / "stage11953_transition_1k_v2_replay_balanced_audit"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("row_id") or row.get("id"))


def metadata_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row_id(row): row for row in rows}


def audit_rows(runtime: str, split: str) -> list[dict[str, Any]]:
    path = AUDIT_DIR / runtime / split / f"bounded_choice_eval_audit_{split}.json"
    return list(read_json(path).get("row_cards") or [])


def bucket_deltas(
    *,
    baseline_runtime: str,
    candidate_runtime: str,
    split: str,
    meta: dict[str, dict[str, Any]],
    keys: tuple[str, ...],
) -> dict[str, Any]:
    base = {row_id(row): row for row in audit_rows(baseline_runtime, split)}
    cand = {row_id(row): row for row in audit_rows(candidate_runtime, split)}
    out: dict[str, Any] = {}
    for key in keys:
        buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"rows": 0, "baseline_correct": 0, "candidate_correct": 0, "delta": 0})
        for rid, c_row in cand.items():
            m = meta.get(rid, {})
            name = str(m.get(key) or "unknown")
            b_ok = base.get(rid, {}).get("constrained_choice_match") is True
            c_ok = c_row.get("constrained_choice_match") is True
            buckets[name]["rows"] += 1
            buckets[name]["baseline_correct"] += int(b_ok)
            buckets[name]["candidate_correct"] += int(c_ok)
            buckets[name]["delta"] += int(c_ok) - int(b_ok)
        out[key] = dict(sorted(buckets.items()))
    return out


def flip_summary(*, baseline_runtime: str, candidate_runtime: str, split: str, meta: dict[str, dict[str, Any]]) -> dict[str, Any]:
    base = {row_id(row): row for row in audit_rows(baseline_runtime, split)}
    cand = {row_id(row): row for row in audit_rows(candidate_runtime, split)}
    gained: list[dict[str, Any]] = []
    lost: list[dict[str, Any]] = []
    for rid, c_row in cand.items():
        b_ok = base.get(rid, {}).get("constrained_choice_match") is True
        c_ok = c_row.get("constrained_choice_match") is True
        if b_ok == c_ok:
            continue
        m = meta.get(rid, {})
        item = {
            "row_id": rid,
            "task_type": m.get("task_type"),
            "language_family": m.get("language_family"),
            "repo_id": m.get("repo_id"),
            "target": c_row.get("bounded_choice_target_label"),
            "candidate_prediction": c_row.get("constrained_choice_top1_label"),
            "baseline_prediction": base.get(rid, {}).get("constrained_choice_top1_label"),
        }
        if c_ok:
            gained.append(item)
        else:
            lost.append(item)
    return {
        "gained_count": len(gained),
        "lost_count": len(lost),
        "net": len(gained) - len(lost),
        "gained_sample": gained[:20],
        "lost_sample": lost[:20],
    }


def main() -> None:
    audit = read_json(AUDIT)
    old_meta = metadata_index(read_jsonl(OLD_ROWS))
    v2_meta = metadata_index(read_jsonl(V2_ROWS))
    scoreboard = audit["scoreboard"]
    stage11924 = scoreboard["stage11924_selected_transition"]
    stage11947 = scoreboard["stage11947_v2_only"]
    stage11952 = scoreboard["stage11952_v2_replay_balanced"]

    deltas = {
        "old_640_stage11924_to_stage11952": {
            "overall_delta": stage11952["old_transition_640"]["correct"] - stage11924["old_transition_640"]["correct"],
            "by_bucket": bucket_deltas(
                baseline_runtime="stage11924_selected_transition",
                candidate_runtime="stage11952_v2_replay_balanced",
                split="old_transition_640",
                meta=old_meta,
                keys=("task_type", "language_family", "repo_id"),
            ),
            "flips": flip_summary(
                baseline_runtime="stage11924_selected_transition",
                candidate_runtime="stage11952_v2_replay_balanced",
                split="old_transition_640",
                meta=old_meta,
            ),
        },
        "v2_validation_stage11947_to_stage11952": {
            "overall_delta": stage11952["v2_validation"]["correct"] - stage11947["v2_validation"]["correct"],
            "by_bucket": bucket_deltas(
                baseline_runtime="stage11947_v2_only",
                candidate_runtime="stage11952_v2_replay_balanced",
                split="v2_validation",
                meta=v2_meta,
                keys=("task_type", "language_family", "repo_id"),
            ),
            "flips": flip_summary(
                baseline_runtime="stage11947_v2_only",
                candidate_runtime="stage11952_v2_replay_balanced",
                split="v2_validation",
                meta=v2_meta,
            ),
        },
        "v2_strict_stage11947_to_stage11952": {
            "overall_delta": stage11952["v2_strict_eval"]["correct"] - stage11947["v2_strict_eval"]["correct"],
            "by_bucket": bucket_deltas(
                baseline_runtime="stage11947_v2_only",
                candidate_runtime="stage11952_v2_replay_balanced",
                split="v2_strict_eval",
                meta=v2_meta,
                keys=("task_type", "language_family", "repo_id"),
            ),
            "flips": flip_summary(
                baseline_runtime="stage11947_v2_only",
                candidate_runtime="stage11952_v2_replay_balanced",
                split="v2_strict_eval",
                meta=v2_meta,
            ),
        },
    }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "reject_stage11952_keep_stage11924_selected_transition_frontier",
        "reason": [
            "Stage11952 preserved compact gates and residual but failed transition promotion gates.",
            "Old 640 transition score is 357/640, below Stage11924 364/640.",
            "V2 validation is 64/128, below Stage11947 66/128.",
            "V2 strict is 98/220, below Stage11947 123/220.",
        ],
        "selected_transition_frontier": {
            "runtime": "runs/local/artifacts/stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json",
            "scorer": "encoder_option_retrieval_semantic_candidate_head",
            "old_transition_640": stage11924["old_transition_640"],
        },
        "stage11952_scoreboard": stage11952,
        "promotion_gates": audit["gates"],
        "delta_analysis": deltas,
        "next_recommendation": {
            "do_not_promote": True,
            "do_not_run_same_replay_recipe": True,
            "next_experiment": "transition_next_action_and_verifier_status_repair",
            "rationale": "Replay protected compact behavior but diluted the v2-only transition gains; next work should target next_action/verifier-transition geometry with split-aware heldout, not more broad replay.",
        },
        "source_artifacts": {
            "audit": rel(AUDIT),
            "old_rows": rel(OLD_ROWS),
            "v2_rows": rel(V2_ROWS),
        },
    }
    write_json(SUMMARY, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": payload["decision"], "reason": payload["reason"], "next": payload["next_recommendation"]}, indent=2))


if __name__ == "__main__":
    main()
