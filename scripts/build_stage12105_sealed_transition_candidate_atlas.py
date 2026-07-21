#!/usr/bin/env python3
"""Atlas candidate rows for the Stage12104 sealed transition confirmation slice."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
STAGE = 12105
NAME = "stage12105_sealed_transition_candidate_atlas"
OUT = ART / NAME
SUMMARY = OUT / "sealed_transition_candidate_atlas.json"
MIRROR = SUM / f"{NAME}.json"
CANDIDATE_ROWS = OUT / "sealed_transition_candidate_rows.jsonl"
REJECTED_ROWS = OUT / "sealed_transition_rejected_rows.jsonl"

STAGE12104 = SUM / "stage12104_sealed_transition_slice_request.json"

TASKS = {
    "transition_next_action",
    "transition_candidate_selection",
    "transition_verifier_transition",
    "transition_continue_or_stop",
}

PREFERRED_SOURCES = [
    ART / "stage11945_transition_1k_v2_multisource_package/transition_projection_rows_v2.jsonl",
    ART / "stage11951_transition_1k_v2_replay_balanced_probe_request/transition_1k_v2_replay_balanced_manifest.jsonl",
    ART / "stage11955_transition_5k_v1_multisource_package/transition_projection_rows_5k_v1.jsonl",
    ART / "stage11958_transition_5k_v1_augmented_package/transition_projection_rows_5k_v1_augmented.jsonl",
    ART / "stage11982_transition_support_replay_probe_request/transition_support_replay_manifest.jsonl",
]


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
            continue
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


def task_type(row: dict[str, Any]) -> str:
    value = row.get("task_type")
    if value:
        return str(value)
    rid = str(row.get("row_id") or "")
    for suffix in ("next_action", "candidate_selection", "verifier_transition", "continue_or_stop"):
        if rid.endswith("::" + suffix) or ("::" + suffix + "::") in rid:
            return "transition_" + suffix
    return "unknown"


def root_key(row: dict[str, Any]) -> str:
    for key in ("root_lineage_key", "root_id", "source_root_id", "source_bundle_id"):
        value = row.get(key)
        if value:
            return str(value)
    rid = str(row.get("row_id") or "")
    if "::" in rid:
        return "::".join(rid.split("::")[:4])
    return rid


def repo_family(row: dict[str, Any]) -> str:
    return str(row.get("repo_family") or row.get("repo_id") or "unknown")


def option_count(row: dict[str, Any]) -> int:
    return len(row.get("opaque_options") or (row.get("standalone_projection_source") or {}).get("opaque_options") or [])


def has_visible_candidate_contract(row: dict[str, Any]) -> bool:
    opts = row.get("opaque_options") or (row.get("standalone_projection_source") or {}).get("opaque_options") or []
    if len(opts) < 2:
        return False
    for opt in opts:
        if not isinstance(opt, dict):
            return False
        if not opt.get("label"):
            return False
        if not (opt.get("role") or opt.get("value") or opt.get("artifact_type")):
            return False
    return True


def has_evidence_markers(row: dict[str, Any]) -> bool:
    text = "\n".join(str(row.get(k) or "") for k in ("input_text", "prompt_text"))
    markers = [
        "SOURCE_EVIDENCE",
        "VERIFIER_EVIDENCE",
        "CANDIDATES",
        "Observed verifier",
        "Visible source evidence",
        "Visible verifier",
        "verifier",
    ]
    return "CANDIDATES" in text and any(marker in text for marker in markers)


def target_leak_risk(row: dict[str, Any]) -> bool:
    anti = row.get("anti_cheat") or {}
    if anti.get("target_value_not_visible_before_options") is False:
        return True
    if anti.get("target_label_not_visible_before_options") is False:
        return True
    return False


def gather_exclusion_roots() -> tuple[set[str], Counter[str]]:
    roots: set[str] = set()
    counts: Counter[str] = Counter()
    for path in ART.glob("stage*/**/*.jsonl"):
        text_path = str(path)
        stage_name = path.parts[path.parts.index("artifacts") + 1] if "artifacts" in path.parts else ""
        if not (
            stage_name.startswith("stage11897")
            or stage_name.startswith("stage11943")
            or stage_name.startswith("stage120")
        ):
            continue
        if "transition" not in text_path and "candidate_selection" not in text_path and "next_action" not in text_path:
            continue
        for row in read_jsonl(path):
            if task_type(row) in TASKS or "transition" in str(row.get("row_id") or ""):
                key = root_key(row)
                if key:
                    roots.add(key)
                    counts[stage_name] += 1
    return roots, counts


def candidate_sources() -> list[Path]:
    seen = set()
    out = []
    for path in PREFERRED_SOURCES:
        if path.exists():
            out.append(path)
            seen.add(path)
    for path in ART.glob("stage119*/**/*.jsonl"):
        if path in seen:
            continue
        if "transition" in str(path) and ("manifest" in path.name or "rows" in path.name):
            out.append(path)
            seen.add(path)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    request = read_json(STAGE12104)
    exclusion_roots, exclusion_counts = gather_exclusion_roots()

    dedup: dict[str, dict[str, Any]] = {}
    source_counts: Counter[str] = Counter()
    raw_rows = 0
    for path in candidate_sources():
        source_name = path.parts[path.parts.index("artifacts") + 1]
        for row in read_jsonl(path):
            if task_type(row) not in TASKS:
                continue
            raw_rows += 1
            source_counts[source_name] += 1
            rid = str(row.get("row_id") or "")
            if rid not in dedup:
                item = dict(row)
                item["stage12105_source_path"] = rel(path)
                item["stage12105_source_stage"] = source_name
                dedup[rid] = item

    admitted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    rejection_counts: Counter[str] = Counter()

    for row in dedup.values():
        reasons = []
        key = root_key(row)
        anti = row.get("anti_cheat") or {}
        if key in exclusion_roots:
            reasons.append("root_lineage_overlaps_discovery_or_stage120")
        if row.get("train_support_only") is True or row.get("split") == "train":
            reasons.append("train_support_or_train_split")
        if row.get("source_heldout_admissible") is not True and row.get("strict_eval_eligible") is not True:
            reasons.append("not_source_heldout_or_strict_eligible")
        if option_count(row) < 2 or anti.get("singleton_options") is True:
            reasons.append("singleton_or_missing_options")
        if anti.get("deterministic_option_shuffle") is not True:
            reasons.append("option_shuffle_not_declared")
        if target_leak_risk(row):
            reasons.append("target_leak_risk")
        if not has_visible_candidate_contract(row):
            reasons.append("candidate_contract_incomplete")
        if not has_evidence_markers(row):
            reasons.append("missing_visible_evidence_markers")
        if not (row.get("language_family") or row.get("language")):
            reasons.append("missing_language_family")
        if not repo_family(row):
            reasons.append("missing_repo_family")

        audit = {
            "row_id": row.get("row_id"),
            "root_key": key,
            "repo_family": repo_family(row),
            "language_family": row.get("language_family") or row.get("language") or "unknown",
            "task_type": task_type(row),
            "source_stage": row.get("stage12105_source_stage"),
            "source_path": row.get("stage12105_source_path"),
            "reasons": reasons,
        }
        if reasons:
            rejected.append(audit)
            for reason in reasons:
                rejection_counts[reason] += 1
        else:
            clean = dict(row)
            clean["stage12105_sealed_candidate"] = True
            clean["stage12105_root_key"] = key
            admitted.append(clean)

    by_task = Counter(task_type(row) for row in admitted)
    by_language = Counter((row.get("language_family") or row.get("language") or "unknown") for row in admitted)
    by_repo = Counter(repo_family(row) for row in admitted)
    unique_roots = {root_key(row) for row in admitted}

    min_task = request["sealed_slice_contract"]["task_balance"]
    min_needed = {task: spec["minimum_rows_at_100"] for task, spec in min_task.items()}
    task_remaining = {task: max(0, min_needed[task] - by_task.get(task, 0)) for task in min_needed}

    language_floor = request["sealed_slice_contract"]["language_floor_at_100_rows"]
    language_remaining = {lang: max(0, floor - by_language.get(lang, 0)) for lang, floor in language_floor.items()}

    can_materialize_minimum = (
        len(admitted) >= request["sealed_slice_contract"]["minimum_rows"]
        and len(unique_roots) >= request["sealed_slice_contract"]["minimum_rows"]
        and all(v == 0 for v in task_remaining.values())
        and all(v == 0 for v in language_remaining.values())
    )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "sealed_slice_can_be_materialized_from_existing_rows" if can_materialize_minimum else "fresh_sealed_roots_required",
        "raw_candidate_rows_scanned": raw_rows,
        "deduped_candidate_rows": len(dedup),
        "admitted_rows": len(admitted),
        "rejected_rows": len(rejected),
        "unique_admitted_roots": len(unique_roots),
        "can_materialize_minimum_100": can_materialize_minimum,
        "admitted_counts": {
            "by_task": dict(sorted(by_task.items())),
            "by_language": dict(sorted(by_language.items())),
            "top_repo_family": dict(by_repo.most_common(20)),
        },
        "remaining_to_minimum": {
            "by_task": task_remaining,
            "by_language": language_remaining,
            "rows": max(0, request["sealed_slice_contract"]["minimum_rows"] - len(admitted)),
            "unique_roots": max(0, request["sealed_slice_contract"]["minimum_rows"] - len(unique_roots)),
        },
        "rejection_counts": dict(rejection_counts.most_common()),
        "exclusion_root_count": len(exclusion_roots),
        "exclusion_source_counts": dict(exclusion_counts.most_common(30)),
        "source_counts": dict(source_counts.most_common(30)),
        "request_contract": {
            "minimum_rows": request["sealed_slice_contract"]["minimum_rows"],
            "preferred_rows": request["sealed_slice_contract"]["preferred_rows"],
            "task_balance": request["sealed_slice_contract"]["task_balance"],
            "language_floor_at_100_rows": request["sealed_slice_contract"]["language_floor_at_100_rows"],
        },
        "next_recommendation": (
            "Build Stage12106 sealed-slice materializer from admitted rows, then run frozen route and Gemma on it."
            if can_materialize_minimum
            else "Build fresh root-disjoint sealed transition rows; existing rows do not satisfy the Stage12104 sealed contract."
        ),
        "outputs": {
            "summary": rel(SUMMARY),
            "summary_mirror": rel(MIRROR),
            "candidate_rows": rel(CANDIDATE_ROWS),
            "rejected_rows": rel(REJECTED_ROWS),
        },
        "source_artifacts": {
            "sealed_slice_request": rel(STAGE12104),
        },
    }

    write_jsonl(CANDIDATE_ROWS, admitted)
    write_jsonl(REJECTED_ROWS, rejected)
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        "decision": summary["decision"],
        "admitted_rows": len(admitted),
        "unique_admitted_roots": len(unique_roots),
        "remaining_to_minimum": summary["remaining_to_minimum"],
        "top_rejections": dict(rejection_counts.most_common(8)),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
