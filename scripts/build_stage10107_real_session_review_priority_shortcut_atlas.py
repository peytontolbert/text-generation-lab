#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10107
NAME = "stage10107_real_session_review_priority_shortcut_atlas"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ATLAS = OUT_DIR / "real_session_review_priority_shortcut_atlas.json"
QUEUE = OUT_DIR / "real_session_review_priority_queue.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_SESSION_REVIEW_PRIORITY_SHORTCUT_ATLAS_STAGE10107.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

PACKET = ROOT / "runs/local/artifacts/stage10103_real_session_candidate_competition_bootstrap_packet/real_session_candidate_competition_bootstrap_packet.jsonl"
BLOCKED = ROOT / "runs/local/artifacts/stage10106_real_session_adjudicated_manifest_compiler/real_session_bootstrap_adjudication_blocked_rows.jsonl"


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
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
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


def _length_ratio(lengths: list[int]) -> float:
    if not lengths:
        return 1.0
    low = min(lengths)
    high = max(lengths)
    if low <= 0:
        return float(high)
    return round(high / low, 4)


def _surface_pair(candidates: list[dict[str, Any]]) -> str:
    labels = sorted(str(candidate.get("surface_family") or "") for candidate in candidates)
    return "__vs__".join(labels)


def _row_risk(row: dict[str, Any], blocked_by_row: dict[str, dict[str, Any]]) -> dict[str, Any]:
    prompt = row.get("prompt_surface") if isinstance(row.get("prompt_surface"), dict) else {}
    candidates = prompt.get("candidate_choices") if isinstance(prompt.get("candidate_choices"), list) else []
    snippets = [str(candidate.get("snippet_preview") or "") for candidate in candidates]
    families = [str(candidate.get("surface_family") or "") for candidate in candidates]
    blocked = blocked_by_row.get(str(row.get("row_id") or ""), {})

    has_verification_target_phrase = any("Verification target:" in snippet for snippet in snippets)
    exposes_test_surface_family = "TEST" in families
    exposes_entrypoint_surface_family = "ENTRYPOINT" in families
    candidate_count = len(candidates)
    snippet_lengths = [len(snippet) for snippet in snippets]
    snippet_ratio = _length_ratio(snippet_lengths)
    terse_candidate_present = any(length <= 48 for length in snippet_lengths if length > 0)
    long_candidate_present = any(length >= 160 for length in snippet_lengths)
    mixed_terse_vs_long = terse_candidate_present and long_candidate_present
    surface_pair = _surface_pair(candidates)

    risk_score = 0
    reasons: list[str] = []
    if has_verification_target_phrase:
        risk_score += 4
        reasons.append("verification_target_phrase_visible")
    if exposes_test_surface_family:
        risk_score += 3
        reasons.append("test_surface_family_visible")
    if exposes_entrypoint_surface_family:
        risk_score += 2
        reasons.append("entrypoint_surface_family_visible")
    if snippet_ratio >= 3.0:
        risk_score += 2
        reasons.append("snippet_length_asymmetry_ge_3x")
    if mixed_terse_vs_long:
        risk_score += 1
        reasons.append("short_vs_long_candidate_asymmetry")
    if candidate_count == 2:
        risk_score += 1
        reasons.append("binary_choice_surface")
    if blocked.get("language_family") == "c_cpp":
        risk_score += 1
        reasons.append("scarce_language_slice")

    severity = "high" if risk_score >= 7 else "medium" if risk_score >= 4 else "low"
    return {
        "row_id": row.get("row_id"),
        "repo_id": row.get("repo_id"),
        "language_family": row.get("language_family"),
        "competition_template": row.get("competition_template"),
        "surface_pair": surface_pair,
        "candidate_count": candidate_count,
        "snippet_length_ratio": snippet_ratio,
        "risk_score": risk_score,
        "risk_severity": severity,
        "risk_reasons": reasons,
        "blocked_reasons": blocked.get("block_reasons") or [],
    }


def build() -> dict[str, Any]:
    packet_rows = load_jsonl(PACKET)
    blocked_rows = load_jsonl(BLOCKED)
    failures: list[str] = []
    if len(packet_rows) != 33:
        failures.append("stage10103_packet_rows_not_33")
    if len(blocked_rows) != 33:
        failures.append("stage10106_blocked_rows_not_33")

    blocked_by_row = {str(row.get("row_id") or ""): row for row in blocked_rows}
    queue_rows: list[dict[str, Any]] = []
    severity_counts = Counter()
    reason_counts = Counter()
    language_counts = Counter()
    pair_counts = Counter()
    repo_counts = Counter()

    for row in packet_rows:
        risk = _row_risk(row, blocked_by_row)
        queue_rows.append(risk)
        severity_counts[risk["risk_severity"]] += 1
        language_counts[str(risk["language_family"] or "")] += 1
        pair_counts[str(risk["surface_pair"] or "")] += 1
        repo_counts[str(risk["repo_id"] or "")] += 1
        for reason in risk["risk_reasons"]:
            reason_counts[reason] += 1

    queue_rows.sort(
        key=lambda row: (
            {"high": 0, "medium": 1, "low": 2}[row["risk_severity"]],
            -int(row["risk_score"]),
            str(row["language_family"]),
            str(row["row_id"]),
        )
    )
    for index, row in enumerate(queue_rows, start=1):
        row["review_priority_rank"] = index

    top_rows = queue_rows[:10]
    metrics = {
        "packet_rows": len(packet_rows),
        "blocked_rows": len(blocked_rows),
        "high_risk_rows": sum(1 for row in queue_rows if row["risk_severity"] == "high"),
        "medium_risk_rows": sum(1 for row in queue_rows if row["risk_severity"] == "medium"),
        "low_risk_rows": sum(1 for row in queue_rows if row["risk_severity"] == "low"),
        "language_counts": dict(sorted(language_counts.items())),
        "surface_pair_counts": dict(sorted(pair_counts.items())),
        "risk_reason_counts": dict(sorted(reason_counts.items())),
        "repo_counts": dict(sorted(repo_counts.items())),
    }
    atlas = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "metrics": metrics,
        "failures": failures,
        "top_priority_rows": top_rows,
        "decision": (
            "Prioritized real-session review toward rows whose visible prompt shape is most likely to support shortcut behavior, "
            "so expert maintainer and anti-cheat review starts with the highest-risk packet slices instead of treating all 33 blocked rows as equally trustworthy."
        ),
        "claim_boundary": {
            "supports_training_or_scoring_now": False,
            "review_packet_still_requires_human_completion": True,
            "python_file_vs_test_rows_dominate_shortcut_risk": metrics["surface_pair_counts"].get("IMPLEMENTATION__vs__TEST", 0) > 0,
        },
    }
    write_json(ATLAS, atlas)
    write_jsonl(QUEUE, queue_rows)
    return atlas


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    built = build()
    next_step = "Use the priority queue to review the highest-risk rows first, beginning with the implementation-vs-test slices whose visible prompt shape may proxy the answer before maintainer reasoning."
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
                "# Stage10107 Real Session Review Priority Shortcut Atlas",
                "",
                f"Passed: `{summary['passed']}`",
                f"Packet rows: `{built['metrics']['packet_rows']}`",
                f"High-risk rows: `{built['metrics']['high_risk_rows']}`",
                f"Medium-risk rows: `{built['metrics']['medium_risk_rows']}`",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"], "next_best_step": next_step}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
