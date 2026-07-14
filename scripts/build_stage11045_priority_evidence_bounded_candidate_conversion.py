#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11045
NAME = "stage11045_priority_evidence_bounded_candidate_conversion"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "priority_evidence_bounded_candidate_conversion.json"
ROWS_JSONL = OUT_DIR / "bounded_candidate_rows.jsonl"

PREVIEW_ROWS = ARTIFACTS / "stage11044_priority_evidence_ledger_projection_preview" / "projected_evidence_ledgers.jsonl"


ROLE_TO_VALUE = {
    "candidate_change_surface": "candidate_change_surface",
    "verifier_and_test_constraint": "verifier_and_test_constraint",
    "symptom_or_call_path_analogue": "symptom_or_call_path_analogue",
    "external_analogue_reference": "external_analogue_reference",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def group_candidates(projected: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {
        "verification_constraint": [],
        "seed_change": [],
        "trace_analogue": [],
        "external_reference": [],
    }
    for item in projected:
        role = str(item.get("role") or "")
        path = str(item.get("path") or "")
        if role == "verification_constraint":
            grouped["verification_constraint"].append(item)
        elif role == "seed_change":
            grouped["seed_change"].append(item)
        elif role == "trace_analogue":
            if "codex_sessions/" in path:
                grouped["trace_analogue"].append(item)
            else:
                grouped["external_reference"].append(item)
        else:
            grouped["external_reference"].append(item)
    return grouped


def summarize_paths(items: list[dict[str, Any]], limit: int = 3) -> str:
    paths = []
    seen = set()
    for item in items:
        path = str(item.get("path") or "").strip()
        if path.startswith("codex_sessions/"):
            path = "session_trace_excerpt"
        if not path or path in seen:
            continue
        seen.add(path)
        paths.append(path)
        if len(paths) >= limit:
            break
    return "; ".join(paths) if paths else "none"


def evidence_line_for(index: int, role_key: str, groups: dict[str, list[dict[str, Any]]], verification_targets: list[str]) -> str:
    tag = f"E{index:02d}"
    if role_key == "verifier_and_test_constraint":
        items = groups["verification_constraint"]
        return (
            f"{tag} [{summarize_paths(items)}]: "
            f"Selected-test evidence aligns directly with these verifier targets: {'; '.join(verification_targets[:3])}."
        )
    if role_key == "candidate_change_surface":
        items = groups["seed_change"]
        return (
            f"{tag} [{summarize_paths(items)}]: "
            "Changed-file evidence points to edited implementation or benchmark surfaces, but does not by itself prove which verifier target matters most."
        )
    if role_key == "symptom_or_call_path_analogue":
        items = groups["trace_analogue"]
        return (
            f"{tag} [{summarize_paths(items)}]: "
            "Trace-style analogues describe execution flow or retrieval route context around the failure."
        )
    items = groups["external_reference"]
    return (
        f"{tag} [{summarize_paths(items)}]: "
        "External or long-join analogue material appears related but is weaker than direct verifier-target evidence."
    )


def build_options(preview: dict[str, Any]) -> tuple[list[dict[str, str]], str]:
    grouped = group_candidates(list(preview.get("projected_evidence_candidates") or []))
    role_order = [
        "candidate_change_surface",
        "verifier_and_test_constraint",
        "symptom_or_call_path_analogue",
        "external_analogue_reference",
    ]
    options = [{"value": ROLE_TO_VALUE[role], "label": "?"} for role in role_order]
    seed = f"{preview['root_id']}::{preview['row_id']}"
    ordered_values = sorted([opt["value"] for opt in options], key=lambda value: hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest())
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    relabeled = [{"label": labels[idx], "value": value} for idx, value in enumerate(ordered_values)]
    gold_value = "verifier_and_test_constraint"
    target_label = next(item["label"] for item in relabeled if item["value"] == gold_value)
    return relabeled, target_label


def build_prompt(preview: dict[str, Any], options: list[dict[str, str]]) -> str:
    grouped = group_candidates(list(preview.get("projected_evidence_candidates") or []))
    role_order = [
        "candidate_change_surface",
        "verifier_and_test_constraint",
        "symptom_or_call_path_analogue",
        "external_analogue_reference",
    ]
    evidence_lines = [
        evidence_line_for(idx + 1, role, grouped, list(preview.get("verification_targets") or []))
        for idx, role in enumerate(role_order)
    ]
    option_lines = [f"{item['label']}. {item['value']}" for item in options]
    return "\n".join(
        [
            f"Repository: {preview['repo_family']}",
            f"Language: {preview['language_family']}",
            f"Promotion lane: {preview['promotion_lane']}",
            "Task: Choose the visible evidence role that most specifically justifies which verifier-target evidence should dominate the maintenance decision.",
            f"Context: {preview['query_text']}",
            "Evidence:",
            *evidence_lines,
            "Options:",
            *option_lines,
            "Answer:",
            "",
        ]
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    previews = load_jsonl(PREVIEW_ROWS)
    rows: list[dict[str, Any]] = []

    for preview in previews:
        options, target_label = build_options(preview)
        prompt = build_prompt(preview, options)
        rows.append(
            {
                "row_id": f"stage11045::{preview['row_id']}::bounded_evidence_role_candidate_v1",
                "source_root_id": preview.get("root_id"),
                "source_preview_row_id": preview.get("row_id"),
                "repo_id": preview.get("repo_family"),
                "repo_family": preview.get("repo_family"),
                "language_family": preview.get("language_family"),
                "task_type": "evidence_citation",
                "objective_family": "bounded_decoder_ce",
                "split": "strict_eval_candidate",
                "split_role": "heldout_candidate_not_admitted",
                "surface": "maintainer_bundle_compact_bounded_choice",
                "train_support_only": False,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "decoder_text": target_label,
                "target_text": target_label,
                "target_token_len": 1,
                "input_text": prompt,
                "prompt_text": prompt,
                "query_text": f"stage11045::{preview['language_family']}::{preview['promotion_lane']}::{preview['root_id']}",
                "opaque_options": options,
                "loss_mask": {"decoder_ce": True},
                "expected_enabled_loss": "decoder_ce",
                "anti_cheat": {
                    "opaque_labels": True,
                    "target_path_strings_hidden_pre_options": True,
                    "same_surface_eval_admissible": False,
                    "projected_visible_evidence": True,
                    "candidate_surface_distractor_preserved": True,
                },
                "standalone_projection_source": {
                    "projection_mode": "stage11045_priority_evidence_bounded_candidate_v1",
                    "gold_value": "verifier_and_test_constraint",
                    "opaque_options": options,
                    "verification_targets": list(preview.get("verification_targets") or []),
                    "expected_changed_files": list(preview.get("expected_changed_files") or []),
                    "projected_evidence_candidates": list(preview.get("projected_evidence_candidates") or []),
                },
            }
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(rows),
        "decision": "priority_evidence_bounded_candidates_built",
        "claim_scope": [
            "Convert the five stage11044 evidence-ledger previews into bounded candidate rows with opaque labels and visible role/path evidence.",
            "Preserve candidate-surface distractors while moving the blocked decisive-evidence lane toward honest scoreability.",
        ],
        "headline_findings": [
            f"Built {len(rows)} bounded candidate rows from the projected evidence ledgers.",
            "All rows currently target verifier_and_test_constraint as the strongest visible evidence role, while preserving candidate_change_surface and analogue distractors.",
            "These rows are candidate-only and still need anti-cheat review before any training or headline scoring use.",
        ],
        "metrics": {
            "row_count": len(rows),
            "by_language": {
                language: sum(1 for row in rows if str(row.get('language_family') or '') == language)
                for language in sorted({str(row.get('language_family') or '') for row in rows})
            },
            "by_repo_family": {
                repo: sum(1 for row in rows if str(row.get('repo_family') or '') == repo)
                for repo in sorted({str(row.get('repo_family') or '') for row in rows})
            },
        },
        "next_best_step": "Run an anti-cheat audit on these candidate rows, then decide whether the C/C++ rows are clean enough for reserved-candidate scoring and whether the Python rows should remain verifier-transition support only.",
        "source_artifacts": {
            "preview_rows": rel(PREVIEW_ROWS),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "row_jsonl": rel(ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(ROWS_JSONL, rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
