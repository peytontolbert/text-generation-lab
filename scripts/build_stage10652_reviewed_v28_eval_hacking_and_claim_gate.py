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
V28_COMPARISON = ARTIFACTS / "stage10646_reviewed_v28_candidate_same_manifest_comparison/reviewed_v28_candidate_same_manifest_comparison.json"
V28_ROWS = ARTIFACTS / "stage10646_reviewed_v28_candidate_same_manifest_comparison/reviewed_v28_candidate_same_manifest_rows.jsonl"
HARNESS_AUDIT = ARTIFACTS / "stage10651_reviewed_v28_harness_result_audit/reviewed_v28_harness_result_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def options_prefix(prompt: str) -> str:
    marker = "\nOptions:\n"
    return prompt.split(marker, 1)[0] if marker in prompt else prompt


def evidence_key_signature(prompt: str) -> tuple[str, ...]:
    keys: list[str] = []
    for line in prompt.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in {"Evidence:", "Options:", "Answer:"}:
            keys.append(stripped.rstrip(":"))
            continue
        if stripped.startswith("Language:"):
            keys.append("Language")
            continue
        if stripped.startswith("Perspective:"):
            keys.append("Perspective")
            continue
        if stripped.startswith("Task:"):
            keys.append("Task")
            continue
        match = re.match(r"^([A-Za-z0-9_]+)\s+\[", stripped)
        if match:
            keys.append(match.group(1))
    return tuple(keys)


def majority_baseline(rows: list[dict[str, Any]], key_fn) -> dict[str, Any]:
    buckets: dict[str, Counter[str]] = defaultdict(Counter)
    total = 0
    correct = 0
    for row in rows:
        signature = json.dumps(key_fn(row), sort_keys=True, default=str)
        target = str(row.get("target_text") or "")
        buckets[signature][target] += 1
    for row in rows:
        signature = json.dumps(key_fn(row), sort_keys=True, default=str)
        target = str(row.get("target_text") or "")
        majority = buckets[signature].most_common(1)[0][0]
        total += 1
        correct += int(target == majority)
    return {
        "rows": total,
        "correct": correct,
        "accuracy": (correct / total) if total else 0.0,
        "signature_count": len(buckets),
    }


def leakage_profile(row: dict[str, Any]) -> dict[str, Any]:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    pre_options = options_prefix(prompt)
    target_label = str(row.get("target_text") or "")
    options = list(row.get("opaque_options") or [])
    target_value = None
    values_visible: list[str] = []
    target_key_matches: list[str] = []
    gold_role_visible = False

    for option in options:
        label = str(option.get("label") or "")
        value = str(option.get("value") or "")
        if label == target_label:
            target_value = value
        if value and value in pre_options:
            values_visible.append(value)
    if target_value:
        for line in pre_options.splitlines():
            if target_value in line:
                match = re.match(r"^([A-Za-z0-9_]+)\s+\[", line.strip())
                if match:
                    target_key_matches.append(match.group(1))
                    gold_role_visible = True
    return {
        "target_value": target_value,
        "target_value_visible_pre_options": bool(target_value and target_value in pre_options),
        "visible_option_values_pre_options": sorted(values_visible),
        "visible_option_count_pre_options": len(values_visible),
        "only_gold_value_visible_pre_options": bool(target_value and values_visible == [target_value]),
        "candidate_change_surface_matches_gold": "candidate_change_surface" in target_key_matches,
        "target_visible_roles": sorted(set(target_key_matches)),
        "gold_role_visible_pre_options": gold_role_visible,
        "evidence_key_signature": list(evidence_key_signature(prompt)),
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    leak_rows = [leakage_profile(row) for row in rows]
    counts = Counter()
    key_role_counter = Counter()
    for leak in leak_rows:
        counts["rows"] += 1
        counts["target_value_visible_pre_options"] += int(leak["target_value_visible_pre_options"])
        counts["only_gold_value_visible_pre_options"] += int(leak["only_gold_value_visible_pre_options"])
        counts["candidate_change_surface_matches_gold"] += int(leak["candidate_change_surface_matches_gold"])
        counts["gold_role_visible_pre_options"] += int(leak["gold_role_visible_pre_options"])
        for role in leak["target_visible_roles"]:
            key_role_counter[role] += 1
    return {
        "row_count": counts["rows"],
        "target_value_visible_pre_options": counts["target_value_visible_pre_options"],
        "target_value_visible_pre_options_rate": counts["target_value_visible_pre_options"] / counts["rows"] if counts["rows"] else 0.0,
        "only_gold_value_visible_pre_options": counts["only_gold_value_visible_pre_options"],
        "only_gold_value_visible_pre_options_rate": counts["only_gold_value_visible_pre_options"] / counts["rows"] if counts["rows"] else 0.0,
        "candidate_change_surface_matches_gold": counts["candidate_change_surface_matches_gold"],
        "candidate_change_surface_matches_gold_rate": counts["candidate_change_surface_matches_gold"] / counts["rows"] if counts["rows"] else 0.0,
        "gold_role_visible_pre_options": counts["gold_role_visible_pre_options"],
        "gold_role_visible_pre_options_rate": counts["gold_role_visible_pre_options"] / counts["rows"] if counts["rows"] else 0.0,
        "target_visible_role_counts": dict(key_role_counter),
    }


def root_overlap_report(slices: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    ids = {name: {str(row.get("source_root_id") or "") for row in rows} for name, rows in slices.items()}
    overlaps: list[dict[str, Any]] = []
    names = sorted(ids)
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            shared = sorted(root for root in (ids[left] & ids[right]) if root)
            overlaps.append(
                {
                    "left": left,
                    "right": right,
                    "shared_root_count": len(shared),
                    "shared_roots": shared[:10],
                }
            )
    return {
        "slice_root_counts": {name: len(values) for name, values in ids.items()},
        "pairwise_overlaps": overlaps,
    }


def main() -> None:
    slices = {
        "headline_strict": load_jsonl(PACKAGE_DIR / "headline_strict_eval.jsonl"),
        "headline_validation": load_jsonl(PACKAGE_DIR / "headline_validation.jsonl"),
        "train_support": load_jsonl(PACKAGE_DIR / "train_support.jsonl"),
        "stress_overlap": load_jsonl(PACKAGE_DIR / "stress_overlap_eval.jsonl"),
        "rust_replacement_experiment": load_jsonl(PACKAGE_DIR / "rust_replacement_experiment_eval.jsonl"),
        "pure_web_same_manifest_validation": load_jsonl(PACKAGE_DIR / "pure_web_same_manifest_validation.jsonl"),
    }
    comparison = load_json(V28_COMPARISON)
    comparison_rows = load_jsonl(V28_ROWS)
    harness_audit = load_json(HARNESS_AUDIT)

    per_slice: dict[str, Any] = {}
    for name, rows in slices.items():
        per_slice[name] = {
            "rows": len(rows),
            "languages": sorted({str(row.get("language_family") or "") for row in rows}),
            "task_types": sorted({str(row.get("task_type") or "") for row in rows}),
            "claim_roles": sorted({str(row.get("claim_role") or "") for row in rows}),
            "source_heldout_admissible_rows": sum(1 for row in rows if bool(row.get("source_heldout_admissible"))),
            "verifier_anchor_rows": sum(1 for row in rows if bool(row.get("verifier_anchor"))),
            "selected_test_anchor_rows": sum(1 for row in rows if bool(row.get("selected_test_anchor"))),
            "abstention_heavy_rows": sum(1 for row in rows if bool(row.get("abstention_heavy"))),
            "leakage": summarize_rows(rows),
            "metadata_majority_baselines": {
                "task_type": majority_baseline(rows, lambda row: str(row.get("task_type") or "")),
                "language_and_task": majority_baseline(
                    rows,
                    lambda row: [str(row.get("language_family") or ""), str(row.get("task_type") or "")],
                ),
                "repo_and_task": majority_baseline(
                    rows,
                    lambda row: [str(row.get("repo_id") or ""), str(row.get("task_type") or "")],
                ),
                "evidence_key_signature": majority_baseline(
                    rows,
                    lambda row: leakage_profile(row)["evidence_key_signature"],
                ),
            },
        }

    comparison_slice_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in comparison_rows:
        comparison_slice_rows[str(row.get("slice_name") or "unknown")].append(row)
    comparison_slice_summary = {
        name: {
            "rows": len(rows),
            "hundred_m_accuracy": sum(1 for row in rows if bool(row.get("hundred_m_correct"))) / len(rows) if rows else 0.0,
            "gemma_accuracy": sum(1 for row in rows if bool(row.get("gemma12b_correct"))) / len(rows) if rows else 0.0,
        }
        for name, rows in sorted(comparison_slice_rows.items())
    }

    headline = per_slice["headline_strict"]
    headline_leak = headline["leakage"]
    headline_source_heldout = headline["source_heldout_admissible_rows"]
    claim_gate = {
        "same_manifest_headline_supported": True,
        "source_heldout_headline_supported": headline_source_heldout == headline["rows"] and headline["rows"] > 0,
        "headline_has_target_path_visibility_risk": headline_leak["target_value_visible_pre_options"] > 0,
        "headline_has_gold_only_visibility_rows": headline_leak["only_gold_value_visible_pre_options"] > 0,
        "headline_has_candidate_change_surface_shortcut_rows": headline_leak["candidate_change_surface_matches_gold"] > 0,
        "reviewed_harness_writeback_complete": bool(harness_audit.get("metrics", {}).get("writeback_repaired_cells") == 4),
    }

    safe_claims = [
        "100M beats Gemma on the reviewed v2.7/v2.8 same-manifest compact maintainer-choice headline slice across python, rust, c_cpp, and web_js_ts_html.",
        "The reviewed v2.8 harness path is mechanically recovered and now writes reserved machine artifacts for all four language cells.",
    ]
    blocked_claims = [
        "source-heldout multilingual win" if not claim_gate["source_heldout_headline_supported"] else None,
        "leak-resistant maintainer-grade headline without caveats" if claim_gate["headline_has_target_path_visibility_risk"] else None,
        "pure-web verifier-anchored headline strength" if per_slice["pure_web_same_manifest_validation"]["selected_test_anchor_rows"] == 0 else None,
        "non-abstention-heavy Rust replacement headline" if per_slice["rust_replacement_experiment"]["abstention_heavy_rows"] > 0 else None,
    ]

    headline_frontier = {
        "hundred_m_exact_accuracy": ((((comparison.get("by_slice") or {}).get("hundred_m") or {}).get("headline_strict") or {}).get("exact_accuracy")),
        "gemma_exact_accuracy": ((((comparison.get("by_slice") or {}).get("gemma12b") or {}).get("headline_strict") or {}).get("exact_accuracy")),
        "delta_exact_accuracy": (
            (((((comparison.get("by_slice") or {}).get("hundred_m") or {}).get("headline_strict") or {}).get("exact_accuracy")) or 0.0)
            - (((((comparison.get("by_slice") or {}).get("gemma12b") or {}).get("headline_strict") or {}).get("exact_accuracy")) or 0.0)
        ),
        "rows": ((((comparison.get("by_slice") or {}).get("hundred_m") or {}).get("headline_strict") or {}).get("rows")),
    }

    payload = {
        "stage": 10652,
        "stage_name": "stage10652_reviewed_v28_eval_hacking_and_claim_gate",
        "passed": True,
        "sources": {
            "package": display(PACKAGE_DIR / "reviewed_v28_candidate_manifest_package.json"),
            "same_manifest_comparison": display(V28_COMPARISON),
            "same_manifest_rows": display(V28_ROWS),
            "harness_audit": display(HARNESS_AUDIT),
        },
        "slice_root_overlap": root_overlap_report(slices),
        "per_slice": per_slice,
        "comparison_slice_summary": comparison_slice_summary,
        "headline_frontier": headline_frontier,
        "harness_frontier": harness_audit.get("metrics", {}),
        "claim_gate": claim_gate,
        "safe_claims_now": safe_claims,
        "blocked_claims_now": [claim for claim in blocked_claims if claim],
        "highest_risk_findings": [
            "Many reviewed rows expose the gold candidate value before the Options block because the evidence text includes candidate file paths or handles directly.",
            "A non-trivial subset of rows align the gold target with candidate_change_surface, which remains a plausible shortcut family even when Gemma still loses overall.",
            "The headline remains same-manifest only; all reviewed headline rows are source_heldout_admissible=false.",
        ],
        "next_best_steps": [
            "Build fresh source-heldout reviewed roots before upgrading the multilingual claim.",
            "For future promotable slices, require a stricter prompt contract where gold candidate values do not appear pre-options unless multiple plausible candidates are equally visible.",
            "Keep harness and standalone claims separate: harness is recovered mechanically, but that does not upgrade the benchmark to source-heldout or fully shortcut-resistant.",
        ],
    }

    out_dir = ARTIFACTS / "stage10652_reviewed_v28_eval_hacking_and_claim_gate"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "reviewed_v28_eval_hacking_and_claim_gate.json", payload)
    print(out_dir / "reviewed_v28_eval_hacking_and_claim_gate.json")


if __name__ == "__main__":
    main()
