#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
PACKAGE_DIR = ARTIFACTS / "stage10645_reviewed_v28_candidate_manifest_package"

SLICE_FILES = {
    "headline_strict": "headline_strict_eval.jsonl",
    "headline_validation": "headline_validation.jsonl",
    "rust_replacement_experiment": "rust_replacement_experiment_eval.jsonl",
    "pure_web_same_manifest_validation": "pure_web_same_manifest_validation.jsonl",
    "stress_overlap": "stress_overlap_eval.jsonl",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def options_prefix(prompt: str) -> str:
    marker = "\nOptions:\n"
    return prompt.split(marker, 1)[0] if marker in prompt else prompt


def leakage_detail(row: dict[str, Any]) -> dict[str, Any]:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    prefix = options_prefix(prompt)
    target_label = str(row.get("target_text") or "")
    gold_value = None
    for option in row.get("opaque_options") or []:
        if str(option.get("label") or "") == target_label:
            gold_value = str(option.get("value") or "")
            break

    matching_roles: list[str] = []
    matching_lines: list[str] = []
    if gold_value:
        for line in prefix.splitlines():
            if gold_value and gold_value in line:
                matching_lines.append(line[:500])
                match = re.match(r"^([A-Za-z0-9_]+)\s+\[", line.strip())
                matching_roles.append(match.group(1) if match else "unknown")
    return {
        "gold_value": gold_value,
        "target_visible_pre_options": bool(gold_value and gold_value in prefix),
        "matching_roles": sorted(set(matching_roles)),
        "matching_lines": matching_lines,
    }


def recommended_action(slice_name: str, row: dict[str, Any], leak: dict[str, Any]) -> tuple[str, str, bool]:
    task_type = str(row.get("task_type") or "")
    roles = set(leak.get("matching_roles") or [])

    if slice_name == "stress_overlap":
        return (
            "diagnostic_only",
            "Keep as stress-only. Repo-overlap and prompt visibility make this unsuitable for any promotable claim path.",
            False,
        )
    if task_type == "evidence_citation":
        return (
            "rewrite_evidence_keys_to_opaque_ids",
            "Replace visible evidence-role target strings with opaque evidence IDs like E01/E02 and move semantic role mapping outside the prompt-visible contract.",
            slice_name != "stress_overlap",
        )
    if roles & {"candidate_change_surface", "symptom_or_call_path_analogue", "verifier_and_test_constraint", "algorithmic_background_reference", "nearby_definition_or_usage_context"}:
        return (
            "mask_candidate_path_in_visible_evidence_header",
            "Hide the gold candidate path/value in visible evidence headers or snippets, preserving semantics while preventing direct copy from pre-options evidence.",
            slice_name == "headline_strict",
        )
    return (
        "manual_review",
        "Row needs manual contract review because the gold value is visible pre-options through a non-standard path.",
        False,
    )


def severity(slice_name: str, leak: dict[str, Any], row: dict[str, Any]) -> str:
    if not leak["target_visible_pre_options"]:
        return "none"
    if slice_name == "headline_strict":
        return "critical"
    if slice_name in {"pure_web_same_manifest_validation", "stress_overlap"}:
        return "high"
    if str(row.get("task_type") or "") == "evidence_citation":
        return "high"
    return "medium"


def main() -> None:
    row_queue: list[dict[str, Any]] = []
    slice_summary: dict[str, Any] = {}
    action_counter: Counter[str] = Counter()
    severity_counter: Counter[str] = Counter()
    role_counter: Counter[str] = Counter()

    for slice_name, filename in SLICE_FILES.items():
        rows = load_jsonl(PACKAGE_DIR / filename)
        flagged = 0
        blocked = 0
        for row in rows:
            leak = leakage_detail(row)
            if not leak["target_visible_pre_options"]:
                continue
            flagged += 1
            action, rationale, potentially_headline_safe_after_rewrite = recommended_action(slice_name, row, leak)
            sev = severity(slice_name, leak, row)
            headline_blocked_now = slice_name == "headline_strict"
            blocked += int(headline_blocked_now)
            action_counter[action] += 1
            severity_counter[sev] += 1
            for role in leak["matching_roles"]:
                role_counter[role] += 1
            row_queue.append(
                {
                    "slice_name": slice_name,
                    "row_id": row["row_id"],
                    "language_family": row["language_family"],
                    "task_type": row["task_type"],
                    "repo_id": row["repo_id"],
                    "source_bundle_id": row["source_bundle_id"],
                    "severity": sev,
                    "headline_blocked_now": headline_blocked_now,
                    "potentially_headline_safe_after_rewrite": potentially_headline_safe_after_rewrite,
                    "recommended_action": action,
                    "rewrite_rationale": rationale,
                    "gold_value": leak["gold_value"],
                    "matching_roles": leak["matching_roles"],
                    "matching_lines": leak["matching_lines"],
                    "selected_test_anchor": bool(row.get("selected_test_anchor")),
                    "verifier_anchor": bool(row.get("verifier_anchor")),
                    "abstention_heavy": bool(row.get("abstention_heavy")),
                    "claim_role": row.get("claim_role"),
                }
            )
        slice_summary[slice_name] = {
            "rows": len(rows),
            "flagged_visible_gold_rows": flagged,
            "headline_blocked_rows": blocked,
        }

    payload = {
        "stage": 10653,
        "stage_name": "stage10653_reviewed_v28_prompt_contract_repair_queue",
        "passed": True,
        "sources": {name: str((PACKAGE_DIR / filename).relative_to(ROOT)) for name, filename in SLICE_FILES.items()},
        "slice_summary": slice_summary,
        "repair_action_counts": dict(action_counter),
        "severity_counts": dict(severity_counter),
        "matching_role_counts": dict(role_counter),
        "headline_repair_verdict": {
            "headline_visible_gold_rows": slice_summary["headline_strict"]["flagged_visible_gold_rows"],
            "headline_rows_blocked_now": slice_summary["headline_strict"]["headline_blocked_rows"],
            "headline_can_remain_same_manifest_if_rewritten": True,
            "headline_can_be_upgraded_to_source_heldout_by_rewrite_alone": False,
        },
        "priority_order": [
            "Rewrite the four headline_strict visible-gold rows first; they are the only rows directly blocking a cleaner same-manifest headline.",
            "Then rewrite pure_web_same_manifest_validation and rust_replacement_experiment rows if those slices are needed as stronger supporting evidence.",
            "Keep stress_overlap rows non-promotable even after rewrite because overlap remains the dominant claim boundary.",
        ],
        "repair_queue": row_queue,
    }

    out_dir = ARTIFACTS / "stage10653_reviewed_v28_prompt_contract_repair_queue"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "reviewed_v28_prompt_contract_repair_queue.json", payload)
    write_json(out_dir / "reviewed_v28_prompt_contract_flagged_rows.json", row_queue)
    print(out_dir / "reviewed_v28_prompt_contract_repair_queue.json")


if __name__ == "__main__":
    main()
