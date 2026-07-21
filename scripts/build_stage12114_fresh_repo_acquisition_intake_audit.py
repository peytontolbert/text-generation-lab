#!/usr/bin/env python3
"""Audit fresh repo acquisition scout outputs before checkout/probing."""
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
STAGE = 12114
NAME = "stage12114_fresh_repo_acquisition_intake_audit"
OUT = ART / NAME
SUMMARY = OUT / "fresh_repo_acquisition_intake_audit.json"
MIRROR = SUM / f"{NAME}.json"
DEFAULT_INTAKE = ART / "stage12113_fresh_repo_acquisition_plan/fresh_repo_acquisition_scout_candidates.jsonl"
ADMITTED_LOCAL = OUT / "admitted_local_candidates.jsonl"
ADMITTED_ACQUIRE = OUT / "admitted_acquisition_targets.jsonl"
REJECTED = OUT / "rejected_acquisition_candidates.jsonl"

VALID_LANGS = {"rust", "c_cpp", "web_js_ts_html", "mixed_build_config_dependency"}
VALID_VERIFIER_TYPES = {
    "selected_test_anchor",
    "build_config_anchor",
    "static_compile_anchor",
    "dependency_resolution_anchor",
}


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
        "stage12111_subagent_scout_intake_audit/**/*.jsonl",
    ]
    for pattern in patterns:
        for path in ART.glob(pattern):
            for row in read_jsonl(path):
                if task_type(row).startswith("transition_") or "transition" in str(row.get("row_id") or "") or row.get("stage12107_work_item") or row.get("stage12109_build_verifier_gap_fill") or row.get("stage12111_admitted"):
                    for key in ("repo_family", "repo_id", "root_id", "root_lineage_key", "source_root_id", "source_bundle_id", "source_path", "source_path_or_acquisition_target"):
                        if row.get(key):
                            excluded.add(canonical(row.get(key)))
    return excluded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intake", default=str(DEFAULT_INTAKE))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    intake_path = Path(args.intake)
    rows = read_jsonl(intake_path)
    excluded = gather_excluded_families()

    local = []
    acquire = []
    rejected = []
    counts = Counter()
    seen = set()

    for row in rows:
        reasons = []
        target = row.get("source_path_or_acquisition_target") or row.get("source_path")
        repo = canonical(row.get("repo_family") or target)
        language = str(row.get("language") or "")
        verifier_type = str(row.get("verifier_type") or "")
        split_status = str(row.get("split_status") or "")
        key = f"{repo}::{target}"

        if row.get("_parse_error"):
            reasons.append("json_parse_error")
        if key in seen:
            reasons.append("duplicate_candidate")
        if language not in VALID_LANGS:
            reasons.append("invalid_language")
        if verifier_type not in VALID_VERIFIER_TYPES:
            reasons.append("invalid_verifier_type")
        if split_status not in {"sealed_candidate", "needs_acquisition", "dev_only"}:
            reasons.append("invalid_split_status")
        if split_status == "dev_only":
            reasons.append("dev_only_not_sealed")
        if row.get("reserved_family_conflict") is True:
            reasons.append("reserved_family_conflict_true")
        if repo in excluded:
            reasons.append("repo_family_overlaps_prior_transition_or_selected_work")
        if not row.get("available_evidence"):
            reasons.append("missing_available_evidence")
        if not row.get("suggested_commands"):
            reasons.append("missing_suggested_commands")
        if verifier_type != "selected_test_anchor":
            notes = row.get("risk_notes") or row.get("anti_cheat_notes") or []
            note_text = json.dumps(notes).lower()
            if "selected" not in note_text and "build" not in note_text:
                reasons.append("build_only_scope_not_explicit")
        exists = bool(row.get("exists_locally"))
        if exists:
            path = Path(str(target))
            if not path.exists():
                reasons.append("local_path_missing")
        elif split_status == "sealed_candidate":
            reasons.append("sealed_candidate_not_local")

        audit = {
            **row,
            "stage12114_repo_family_normalized": repo,
            "stage12114_reasons": reasons,
        }
        if reasons:
            rejected.append(audit)
            for reason in reasons:
                counts[reason] += 1
            continue
        seen.add(key)
        audit["stage12114_admitted"] = True
        audit["root_lineage_key"] = "stage12114::" + re.sub(r"[^a-zA-Z0-9]+", "_", key)[-96:]
        if exists:
            local.append(audit)
        else:
            acquire.append(audit)

    admitted_counts = Counter()
    for row in local + acquire:
        admitted_counts[row.get("language")] += 1
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "fresh_repo_acquisition_intake_audited",
        "intake_path": str(intake_path),
        "input_candidates": len(rows),
        "admitted_local_candidates": len(local),
        "admitted_acquisition_targets": len(acquire),
        "rejected_candidates": len(rejected),
        "admitted_by_language": dict(sorted(admitted_counts.items())),
        "rejection_counts": dict(counts.most_common()),
        "excluded_family_count": len(excluded),
        "next_stage_recommendation": {
            "stage": "stage12115_checkout_or_probe_admitted_acquisition_targets",
            "action": "Only admitted local/acquisition candidates may proceed to checkout/probe; rows are still not train/eval examples until verifier logs are captured.",
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "summary_mirror": rel(MIRROR),
            "admitted_local": rel(ADMITTED_LOCAL),
            "admitted_acquisition": rel(ADMITTED_ACQUIRE),
            "rejected": rel(REJECTED),
        },
    }
    write_jsonl(ADMITTED_LOCAL, local)
    write_jsonl(ADMITTED_ACQUIRE, acquire)
    write_jsonl(REJECTED, rejected)
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        "decision": summary["decision"],
        "input_candidates": len(rows),
        "admitted_local_candidates": len(local),
        "admitted_acquisition_targets": len(acquire),
        "admitted_by_language": summary["admitted_by_language"],
        "top_rejections": dict(counts.most_common(8)),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
