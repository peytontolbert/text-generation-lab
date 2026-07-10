#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10114
NAME = "stage10114_real_session_successor_review_priority_atlas"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ATLAS = OUT_DIR / "real_session_successor_review_priority_atlas.json"
QUEUE = OUT_DIR / "real_session_successor_review_priority_queue.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_SESSION_SUCCESSOR_REVIEW_PRIORITY_ATLAS_STAGE10114.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

PACKET = ROOT / "runs/local/artifacts/stage10110_real_session_shortcut_safe_successor_packet/real_session_shortcut_safe_successor_packet.jsonl"
PACKET_AUDIT = ROOT / "runs/local/artifacts/stage10110_real_session_shortcut_safe_successor_packet/real_session_shortcut_safe_successor_audit.json"
REVIEW_MANIFEST = ROOT / "runs/local/artifacts/stage10111_real_session_successor_review_packets/real_session_successor_review_manifest.json"
BLOCKED = ROOT / "runs/local/artifacts/stage10113_real_session_successor_adjudicated_manifest_compiler/real_session_successor_adjudication_blocked_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sorted_surface_pair(row: dict[str, Any]) -> str:
    redacted = ((row.get("hidden_metadata") or {}).get("redacted_candidates")) or []
    families = sorted(str(candidate.get("candidate_surface_family") or "") for candidate in redacted)
    return "__vs__".join(families)


def _priority_row(
    row: dict[str, Any],
    blocked: dict[str, Any],
    *,
    language_counts: dict[str, int],
    template_counts: dict[str, int],
    repo_counts: dict[str, int],
    underfilled_languages: set[str],
) -> dict[str, Any]:
    language = str(row.get("language_family") or "")
    template = str(row.get("successor_template") or "")
    repo_id = str(row.get("repo_id") or "")
    hidden = row.get("hidden_metadata") if isinstance(row.get("hidden_metadata"), dict) else {}
    tags = {str(tag) for tag in (hidden.get("candidate_geometry_tags") or [])}
    surface_pair = _sorted_surface_pair(row)
    pair_tokens = [token for token in surface_pair.split("__vs__") if token]

    claim_reasons: list[str] = []
    shortcut_reasons: list[str] = []
    claim_score = 0
    shortcut_score = 0

    lang_count = int(language_counts.get(language, 0))
    template_count = int(template_counts.get(template, 0))
    repo_count = int(repo_counts.get(repo_id, 0))

    if language in underfilled_languages:
        claim_score += 5
        claim_reasons.append("underfilled_language_slice")
    if lang_count <= 2:
        claim_score += 4
        claim_reasons.append("language_slice_count_le_2")
    elif lang_count <= 9:
        claim_score += 3
        claim_reasons.append("language_slice_count_le_9")
    elif lang_count <= 12:
        claim_score += 2
        claim_reasons.append("language_slice_count_le_12")

    if template_count <= 2:
        claim_score += 3
        claim_reasons.append("template_slice_count_le_2")
    elif template_count >= 18:
        claim_score += 2
        claim_reasons.append("template_dominates_packet")

    if repo_count == 1:
        claim_score += 2
        claim_reasons.append("singleton_repo_slice")
    elif repo_count >= 20:
        claim_score += 1
        claim_reasons.append("dominant_repo_cluster")

    if "CONFIG" in pair_tokens:
        shortcut_score += 3
        shortcut_reasons.append("config_surface_shortcut_risk")
    if "ENTRYPOINT" in pair_tokens:
        shortcut_score += 2
        shortcut_reasons.append("entrypoint_surface_shortcut_risk")
    if len(set(pair_tokens)) > 1:
        shortcut_score += 2
        shortcut_reasons.append("mixed_surface_family_pair")
    if "changed_test_file_present" in tags:
        shortcut_score += 2
        shortcut_reasons.append("changed_test_file_present")
    if "has_selected_tests" in tags:
        shortcut_score += 1
        shortcut_reasons.append("selected_tests_visible_context")
    if template == "python_implementation_vs_config":
        shortcut_score += 2
        shortcut_reasons.append("python_config_template_cluster")
    if template == "web_entrypoint_vs_implementation":
        shortcut_score += 1
        shortcut_reasons.append("single_web_entrypoint_row")
    if repo_id == "agentkernel" and template.startswith("python_"):
        shortcut_score += 1
        shortcut_reasons.append("agentkernel_python_cluster")

    total = claim_score + shortcut_score
    tier = "high" if total >= 9 else "medium" if total >= 5 else "low"

    return {
        "row_id": row.get("row_id"),
        "language_family": language,
        "repo_id": repo_id,
        "successor_template": template,
        "review_packet_dir": blocked.get("review_packet_dir"),
        "expert_maintainer_rubric_review": blocked.get("expert_maintainer_rubric_review"),
        "anti_cheat_review_card": blocked.get("anti_cheat_review_card"),
        "claim_status": blocked.get("claim_status"),
        "block_reasons": blocked.get("block_reasons") or [],
        "language_slice_count": lang_count,
        "template_slice_count": template_count,
        "repo_slice_count": repo_count,
        "candidate_surface_pair": surface_pair,
        "candidate_geometry_tags": sorted(tags),
        "selected_tests_count": len(hidden.get("selected_tests") or []),
        "claim_criticality_score": claim_score,
        "shortcut_risk_score": shortcut_score,
        "priority_score": total,
        "priority_tier": tier,
        "claim_criticality_reasons": claim_reasons,
        "shortcut_risk_reasons": shortcut_reasons,
    }


def build() -> dict[str, Any]:
    packet_rows = load_jsonl(PACKET)
    blocked_rows = load_jsonl(BLOCKED)
    review_manifest = load_json(REVIEW_MANIFEST)
    packet_audit = load_json(PACKET_AUDIT)
    failures: list[str] = []

    if packet_audit.get("passed") is not True:
        failures.append("stage10110_audit_not_passed")
    if len(packet_rows) != 41:
        failures.append("stage10110_packet_rows_not_41")
    if len(blocked_rows) != 41:
        failures.append("stage10113_blocked_rows_not_41")
    if int(review_manifest.get("rows", 0) or 0) != 41:
        failures.append("stage10111_manifest_rows_not_41")

    language_counts = Counter(str(row.get("language_family") or "") for row in packet_rows)
    template_counts = Counter(str(row.get("successor_template") or "") for row in packet_rows)
    repo_counts = Counter(str(row.get("repo_id") or "") for row in packet_rows)
    manifest_language_counts = {
        str(key): int(value)
        for key, value in ((review_manifest.get("language_counts") or {}).items())
    }
    manifest_template_counts = {
        str(key): int(value)
        for key, value in ((review_manifest.get("template_counts") or {}).items())
    }
    if manifest_language_counts and manifest_language_counts != dict(language_counts):
        failures.append("stage10111_language_counts_mismatch")
    if manifest_template_counts and manifest_template_counts != dict(template_counts):
        failures.append("stage10111_template_counts_mismatch")

    blocked_by_row = {str(row.get("row_id") or ""): row for row in blocked_rows}
    underfilled_languages = {
        str(language)
        for language, deficit in ((packet_audit.get("metrics") or {}).get("unmet_quotas") or {}).items()
        if int(deficit or 0) > 0
    }

    queue_rows: list[dict[str, Any]] = []
    tier_counts = Counter()
    claim_reason_counts = Counter()
    shortcut_reason_counts = Counter()
    pair_counts = Counter()
    repo_queue_counts = Counter()

    for row in packet_rows:
        row_id = str(row.get("row_id") or "")
        blocked = blocked_by_row.get(row_id)
        if blocked is None:
            failures.append(f"missing_blocked_row::{row_id}")
            continue
        queued = _priority_row(
            row,
            blocked,
            language_counts=dict(language_counts),
            template_counts=dict(template_counts),
            repo_counts=dict(repo_counts),
            underfilled_languages=underfilled_languages,
        )
        queue_rows.append(queued)
        tier_counts[queued["priority_tier"]] += 1
        pair_counts[queued["candidate_surface_pair"]] += 1
        repo_queue_counts[queued["repo_id"]] += 1
        for reason in queued["claim_criticality_reasons"]:
            claim_reason_counts[reason] += 1
        for reason in queued["shortcut_risk_reasons"]:
            shortcut_reason_counts[reason] += 1

    queue_rows.sort(
        key=lambda row: (
            {"high": 0, "medium": 1, "low": 2}[str(row["priority_tier"])],
            -int(row["priority_score"]),
            -int(row["claim_criticality_score"]),
            -int(row["shortcut_risk_score"]),
            str(row["language_family"]),
            str(row["row_id"]),
        )
    )
    for index, row in enumerate(queue_rows, start=1):
        row["review_priority_rank"] = index

    wave1_rows: list[dict[str, Any]] = []
    for language in ("web_js_ts_html", "c_cpp"):
        wave1_rows.extend(row for row in queue_rows if row["language_family"] == language)
    remaining_slots = max(0, min(15, len(queue_rows)) - len(wave1_rows))
    if remaining_slots:
        for row in queue_rows:
            if row["language_family"] != "python":
                continue
            wave1_rows.append(row)
            if len(wave1_rows) >= min(15, len(queue_rows)):
                break
    recommended_wave = {
        "wave1_review_rows": len(wave1_rows),
        "wave1_languages": dict(sorted(Counter(row["language_family"] for row in wave1_rows).items())),
        "wave1_templates": dict(sorted(Counter(row["successor_template"] for row in wave1_rows).items())),
        "wave1_row_ids": [row["row_id"] for row in wave1_rows],
    }

    metrics = {
        "packet_rows": len(packet_rows),
        "blocked_rows": len(blocked_rows),
        "high_priority_rows": sum(1 for row in queue_rows if row["priority_tier"] == "high"),
        "medium_priority_rows": sum(1 for row in queue_rows if row["priority_tier"] == "medium"),
        "low_priority_rows": sum(1 for row in queue_rows if row["priority_tier"] == "low"),
        "language_counts": dict(sorted(language_counts.items())),
        "template_counts": dict(sorted(template_counts.items())),
        "candidate_surface_pair_counts": dict(sorted(pair_counts.items())),
        "claim_reason_counts": dict(sorted(claim_reason_counts.items())),
        "shortcut_reason_counts": dict(sorted(shortcut_reason_counts.items())),
        "repo_counts": dict(sorted(repo_queue_counts.items())),
        "underfilled_languages": sorted(underfilled_languages),
    }
    atlas = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "metrics": metrics,
        "failures": failures,
        "top_priority_rows": queue_rows[:10],
        "recommended_first_wave": recommended_wave,
        "decision": (
            "Prioritized the 41-row shortcut-safe successor packet for human adjudication by combining claim criticality "
            "(underfilled or scarce language slices, singleton repo coverage, dominant template influence) with shortcut risk "
            "(config or entrypoint competition, test-anchored geometry, and concentrated Python clusters)."
        ),
        "claim_boundary": {
            "supports_training_or_scoring_now": False,
            "all_rows_still_blocked_pending_human_review": True,
            "web_rows_should_be_reviewed_first": metrics["language_counts"].get("web_js_ts_html", 0) == 2
            and "web_js_ts_html" in underfilled_languages,
            "python_config_rows_are_main_shortcut_audit_slice": metrics["template_counts"].get("python_implementation_vs_config", 0) == 18,
        },
    }
    write_json(ATLAS, atlas)
    write_jsonl(QUEUE, queue_rows)
    return atlas


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    built = build()
    next_step = (
        "Start maintainer and anti-cheat review with the ranked web rows and the highest-priority Python config rows, "
        "then move into the scarce C/C++ slice before treating any successor row as admissible for training, scoring, or a multilingual claim."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "atlas": display(ATLAS),
            "queue": display(QUEUE),
            "doc": display(DOC),
        },
        "decision": built["decision"],
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10114 Real Session Successor Review Priority Atlas",
                "",
                f"Passed: `{summary['passed']}`",
                f"Packet rows: `{built['metrics']['packet_rows']}`",
                f"High-priority rows: `{built['metrics']['high_priority_rows']}`",
                f"Medium-priority rows: `{built['metrics']['medium_priority_rows']}`",
                "",
                built["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "metrics": built["metrics"],
                "failures": built["failures"],
                "next_best_step": next_step,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
