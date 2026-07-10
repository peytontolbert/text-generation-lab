#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10104
NAME = "stage10104_real_session_bootstrap_review_packets"
SOURCE_PACKET = ROOT / "runs/local/artifacts/stage10103_real_session_candidate_competition_bootstrap_packet/real_session_candidate_competition_bootstrap_packet.jsonl"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage10103_real_session_candidate_competition_bootstrap_packet/real_session_candidate_competition_bootstrap_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKETS = OUT_DIR / "real_session_bootstrap_review_packets.jsonl"
MANIFEST = OUT_DIR / "real_session_bootstrap_review_manifest.json"
AUDIT = OUT_DIR / "real_session_bootstrap_review_audit.json"
WORKBOOK = OUT_DIR / "real_session_bootstrap_signoff_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_SESSION_BOOTSTRAP_REVIEW_PACKETS_STAGE10104.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

RUBRIC_LINES = [
    "visible_evidence_supports_one_candidate",
    "candidate_set_is_maintainer_plausible",
    "raw_changed_path_list_not_exposed",
    "visible_snippets_are_sufficient_for_local_reasoning",
    "abstention_would_be_more_honest_if_evidence_is_insufficient",
]
ANTI_CHEAT_LINES = [
    "changed_path_signature_leakage",
    "candidate_position_or_id_bias",
    "test_name_or_entrypoint_name_proxy",
    "cross_repo_analogue_surface_leakage",
    "review_scope_matches_prompt_visible_evidence_only",
]


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
    rows = [
        row
        for row in registry.get("rows", [])
        if row.get("stage") != STAGE and row.get("stage_name") != NAME
    ]
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


def packet_dir(row_id: str) -> Path:
    safe = row_id.replace("::", "__").replace("/", "_")
    return OUT_DIR / "review_packets" / safe


def review_paths(row_id: str) -> dict[str, str]:
    base = packet_dir(row_id)
    return {
        "packet_dir": display(base),
        "expert_maintainer_rubric_review": display(base / "expert_maintainer_rubric_review.json"),
        "anti_cheat_review_card": display(base / "anti_cheat_review_card.json"),
    }


def _rubric_stub(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_id": row["row_id"],
        "language_family": row["language_family"],
        "competition_template": row["competition_template"],
        "status": "pending_human_review",
        "passed": False,
        "rubric_version": "expert_maintainer_v1",
        "required_human_action": "Review only the prompt-visible evidence and decide whether exactly one candidate is maintainer-justified. If not, mark the row insufficient rather than forcing a label.",
        "gold_label_slot": {
            "selected_candidate_id": None,
            "abstain_due_to_insufficient_evidence": None,
            "reviewer_rationale": "",
        },
        "rubric_lines": {line: None for line in RUBRIC_LINES},
    }


def _anti_cheat_stub(row: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_id": row["row_id"],
        "language_family": row["language_family"],
        "competition_template": row["competition_template"],
        "status": "pending_human_review",
        "passed": False,
        "required_human_action": "Check whether any visible clue still proxies the right answer without real maintenance reasoning, especially candidate IDs, snippet asymmetry, or latent changed-path hints.",
        "machine_context": {
            "stage10103_supports_training_or_scoring_now": ((audit.get("claim_boundary") or {}).get("supports_training_or_scoring_now")),
            "raw_change_paths_withheld_from_prompt": bool((row.get("hidden_metadata") or {}).get("raw_change_paths_withheld_from_prompt")),
            "candidate_count": len(((row.get("prompt_surface") or {}).get("candidate_choices") or [])),
        },
        "challenge_lines": {line: None for line in ANTI_CHEAT_LINES},
        "reviewer_notes": "",
    }


def build() -> dict[str, Any]:
    audit = load_json(SOURCE_AUDIT)
    rows = load_jsonl(SOURCE_PACKET)
    failures: list[str] = []
    if audit.get("passed") is not True:
        failures.append("stage10103_not_passed")
    if len(rows) != 33:
        failures.append("stage10103_rows_not_33")

    packet_rows: list[dict[str, Any]] = []
    workbook_rows: list[dict[str, Any]] = []
    language_counts = Counter()
    template_counts = Counter()
    queue_position = 1
    for row in rows:
        row_id = str(row.get("row_id") or "")
        base = packet_dir(row_id)
        base.mkdir(parents=True, exist_ok=True)
        rubric = _rubric_stub(row)
        anti_cheat = _anti_cheat_stub(row, audit)
        paths = review_paths(row_id)
        write_json(base / "expert_maintainer_rubric_review.json", rubric)
        write_json(base / "anti_cheat_review_card.json", anti_cheat)
        packet_rows.append(
            {
                "row_id": row_id,
                "language_family": row.get("language_family"),
                "competition_template": row.get("competition_template"),
                "candidate_count": len(((row.get("prompt_surface") or {}).get("candidate_choices") or [])),
                **paths,
            }
        )
        workbook_rows.append(
            {
                "queue_position": queue_position,
                "row_id": row_id,
                "language_family": row.get("language_family"),
                "competition_template": row.get("competition_template"),
                "task": "expert_maintainer_rubric_review",
                "review_file": paths["expert_maintainer_rubric_review"],
                "required_human_action": rubric["required_human_action"],
            }
        )
        queue_position += 1
        workbook_rows.append(
            {
                "queue_position": queue_position,
                "row_id": row_id,
                "language_family": row.get("language_family"),
                "competition_template": row.get("competition_template"),
                "task": "cell_specific_anti_cheat_review",
                "review_file": paths["anti_cheat_review_card"],
                "required_human_action": anti_cheat["required_human_action"],
            }
        )
        queue_position += 1
        language_counts[str(row.get("language_family") or "")] += 1
        template_counts[str(row.get("competition_template") or "")] += 1

    write_jsonl(PACKETS, packet_rows)
    write_json(MANIFEST, {"rows": len(packet_rows), "language_counts": dict(sorted(language_counts.items())), "template_counts": dict(sorted(template_counts.items()))})
    write_json(WORKBOOK, {"rows": workbook_rows, "row_count": len(workbook_rows)})

    metrics = {
        "review_packet_rows": len(packet_rows),
        "workbook_rows": len(workbook_rows),
        "rubric_tasks": sum(1 for row in workbook_rows if row["task"] == "expert_maintainer_rubric_review"),
        "anti_cheat_tasks": sum(1 for row in workbook_rows if row["task"] == "cell_specific_anti_cheat_review"),
        "language_counts": dict(sorted(language_counts.items())),
        "template_counts": dict(sorted(template_counts.items())),
    }
    if metrics["review_packet_rows"] != 33:
        failures.append("review_packet_rows_not_33")
    if metrics["workbook_rows"] != 66:
        failures.append("workbook_rows_not_66")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    built = build()
    write_json(AUDIT, {"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]})
    next_step = "Use these row-level review packets to adjudicate gold labels and anti-cheat status for the 33 surviving real-session competition rows before any shortcut rerun, training, or Gemma comparison."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "packets": display(PACKETS),
            "manifest": display(MANIFEST),
            "workbook": display(WORKBOOK),
            "audit": display(AUDIT),
            "doc": display(DOC),
        },
        "decision": "Materialized row-level expert-maintainer and anti-cheat review packets for the 33 surviving real-session bootstrap rows so adjudication can attach directly to the exact provisional packet.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10104 Real Session Bootstrap Review Packets",
                "",
                f"Passed: `{summary['passed']}`",
                f"Review packet rows: `{built['metrics']['review_packet_rows']}`",
                f"Workbook rows: `{built['metrics']['workbook_rows']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
