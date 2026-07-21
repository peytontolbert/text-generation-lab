#!/usr/bin/env python3
"""Deterministically audit subagent-scouted sealed root candidates."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
STAGE = 12111
NAME = "stage12111_subagent_scout_intake_audit"
OUT = ART / NAME
SUMMARY = OUT / "subagent_scout_intake_audit.json"
MIRROR = SUM / f"{NAME}.json"
DEFAULT_INTAKE = OUT / "subagent_scout_candidates.jsonl"
ADMITTED = OUT / "subagent_scout_admitted_candidates.jsonl"
REJECTED = OUT / "subagent_scout_rejected_candidates.jsonl"

STAGE12110 = SUM / "stage12110_subagent_scout_intake_contract.json"

VALID_LANGS = {"rust", "c_cpp", "web_js_ts_html", "mixed_build_config_dependency"}
VALID_VERIFIER_TYPES = {
    "selected_test_anchor",
    "build_config_anchor",
    "static_compile_anchor",
    "dependency_resolution_anchor",
}
VALID_TASKS = {
    "transition_next_action",
    "transition_candidate_selection",
    "transition_verifier_transition",
    "transition_continue_or_stop",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"_parse_error": line[:500]})
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def canonical(value: Any) -> str:
    text = str(value or "").lower().replace("\\", "/").strip("/")
    for prefix in (
        "/data/repositories/",
        "/data/parametergolf/helpful_repos/",
        "/data/agentkernel_other_repos/",
        "/data/agentkernel-seq2seq-text-lab/",
    ):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    if "::" in text:
        text = text.split("::", 1)[0]
    parts = [part for part in text.split("/") if part]
    return re.sub(r"[^a-z0-9]+", "", parts[0] if parts else text)


def task_type(row: dict[str, Any]) -> str:
    value = row.get("task_type")
    if value:
        return str(value)
    rid = str(row.get("row_id") or "")
    for suffix in ("next_action", "candidate_selection", "verifier_transition", "continue_or_stop"):
        if rid.endswith("::" + suffix) or ("::" + suffix + "::") in rid:
            return "transition_" + suffix
    return "unknown"


def gather_excluded_families() -> set[str]:
    excluded: set[str] = set()
    patterns = [
        "stage11897_transition_record_projection_rows/**/*.jsonl",
        "stage11943*/**/*.jsonl",
        "stage120*/**/*.jsonl",
        "stage12105_sealed_transition_candidate_atlas/**/*.jsonl",
        "stage12107_fresh_sealed_transition_root_materializer/**/*.jsonl",
        "stage12109_build_verifier_gap_fill_queue/**/*.jsonl",
    ]
    for pattern in patterns:
        for path in ART.glob(pattern):
            for row in read_jsonl(path):
                if task_type(row).startswith("transition_") or "transition" in str(row.get("row_id") or "") or row.get("stage12107_work_item") or row.get("stage12109_build_verifier_gap_fill"):
                    for key in ("repo_family", "repo_id", "root_id", "root_lineage_key", "source_root_id", "source_bundle_id", "source_path"):
                        if row.get(key):
                            excluded.add(canonical(row.get(key)))
    return excluded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intake", default=str(DEFAULT_INTAKE))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    contract = read_json(STAGE12110)
    intake_path = Path(args.intake)
    rows = read_jsonl(intake_path)
    excluded = gather_excluded_families()

    admitted = []
    rejected = []
    rejection_counts: Counter[str] = Counter()
    admitted_counts: Counter[str] = Counter()
    seen = set()

    for row in rows:
        reasons = []
        if row.get("_parse_error"):
            reasons.append("json_parse_error")
        source_path = Path(str(row.get("source_path") or ""))
        repo_family = canonical(row.get("repo_family") or source_path)
        language = str(row.get("language") or "")
        verifier_type = str(row.get("verifier_type") or "")
        task = str(row.get("candidate_task_family") or "")
        key = f"{repo_family}::{source_path}"
        if key in seen:
            reasons.append("duplicate_candidate")
        if not source_path.exists():
            reasons.append("source_path_missing")
        if language not in VALID_LANGS:
            reasons.append("invalid_language")
        if verifier_type not in VALID_VERIFIER_TYPES:
            reasons.append("invalid_verifier_type")
        if task not in VALID_TASKS:
            reasons.append("invalid_candidate_task_family")
        if repo_family in excluded:
            reasons.append("repo_family_overlaps_prior_transition_or_selected_work")
        if row.get("reserved_family_conflict") is True:
            reasons.append("reserved_family_conflict_true")
        if not row.get("available_evidence"):
            reasons.append("missing_available_evidence")
        if not row.get("suggested_commands"):
            reasons.append("missing_suggested_commands")
        anti = row.get("anti_cheat_notes") or {}
        if anti.get("no_singleton_options") is not True:
            reasons.append("anti_cheat_no_singleton_missing")
        if anti.get("must_use_opaque_shuffled_options") is not True:
            reasons.append("anti_cheat_opaque_shuffle_missing")
        if anti.get("target_not_visible_before_options") is not True:
            reasons.append("anti_cheat_target_hidden_missing")
        if verifier_type != "selected_test_anchor" and anti.get("build_only_not_selected_test") is not True:
            reasons.append("build_only_scope_not_declared")
        if row.get("split_status") not in {"sealed_candidate", "dev_only"}:
            reasons.append("invalid_split_status")
        if row.get("split_status") == "dev_only":
            reasons.append("dev_only_not_sealed")

        audit = {**row, "stage12111_reasons": reasons, "stage12111_repo_family_normalized": repo_family}
        if reasons:
            rejected.append(audit)
            for reason in reasons:
                rejection_counts[reason] += 1
        else:
            audit["stage12111_admitted"] = True
            audit["root_lineage_key"] = "stage12111::" + re.sub(r"[^a-zA-Z0-9]+", "_", key)[-96:]
            admitted.append(audit)
            admitted_counts[language] += 1
            seen.add(key)

    remaining_gap = dict(contract["current_remaining_gap"])
    for lang, count in admitted_counts.items():
        if lang in remaining_gap:
            remaining_gap[lang] = max(0, int(remaining_gap[lang]) - count)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "subagent_scout_intake_audited",
        "intake_path": str(intake_path),
        "input_candidates": len(rows),
        "admitted_candidates": len(admitted),
        "rejected_candidates": len(rejected),
        "admitted_by_language": dict(sorted(admitted_counts.items())),
        "remaining_gap_after_admission": remaining_gap,
        "rejection_counts": dict(rejection_counts.most_common()),
        "excluded_family_count": len(excluded),
        "next_stage_recommendation": {
            "stage": "stage12112_subagent_candidate_row_builder",
            "action": "Only if admitted_candidates > 0, build typed transition rows from admitted candidates, then run anti-cheat row audit before scoring.",
        },
        "source_artifacts": {
            "stage12110_contract": rel(STAGE12110),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "summary_mirror": rel(MIRROR),
            "admitted": rel(ADMITTED),
            "rejected": rel(REJECTED),
        },
    }
    write_jsonl(ADMITTED, admitted)
    write_jsonl(REJECTED, rejected)
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        "decision": summary["decision"],
        "input_candidates": len(rows),
        "admitted_candidates": len(admitted),
        "remaining_gap_after_admission": remaining_gap,
        "top_rejections": dict(rejection_counts.most_common(8)),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
