#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"

STAGE = 11468
NAME = "stage11468_selected_runtime_harness_promotion_gate_audit"
OUT = ART / NAME
OUT_JSON = OUT / "selected_runtime_harness_promotion_gate_audit.json"

PAYLOAD = ART / "stage11464_selected_runtime_harness_payload/selected_runtime_harness_payload.json"
RESULT = ART / "stage11467_selected_runtime_harness_result_audit/selected_runtime_harness_result_audit.json"

ROLE_MARKERS = (
    "candidate_change_surface",
    "symptom_or_call_path_analogue",
    "verifier_and_test_constraint",
    "nearby_definition_or_usage_context",
    "algorithmic_background_reference",
    "external_analogue_reference",
)


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def label_value(row: dict[str, Any]) -> str:
    target = str(row.get("expected_label") or row.get("target_text") or "")
    for option in row.get("opaque_options") or []:
        if isinstance(option, dict) and str(option.get("label") or "") == target:
            return str(option.get("value") or "")
    return ""


def before_options(prompt: str) -> str:
    return prompt.split("Options:", 1)[0]


def row_audit(row: dict[str, Any]) -> dict[str, Any]:
    prompt = str(row.get("prompt") or row.get("prompt_text") or "")
    prompt_prefix = before_options(prompt)
    value = label_value(row)
    options = [opt for opt in row.get("opaque_options") or [] if isinstance(opt, dict)]
    anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    prompt_target_value_leak = bool(value and value != "ABSTAIN_INSUFFICIENT_EVIDENCE" and value in prompt_prefix)
    label = str(row.get("expected_label") or "")
    prompt_target_label_leak = bool(label and label in prompt_prefix.splitlines())
    role_markers = [marker for marker in ROLE_MARKERS if marker in prompt_prefix]
    return {
        "row_id": row.get("row_id"),
        "language_family": row.get("language_family"),
        "repo_family": row.get("repo_family"),
        "source_root_id": row.get("source_root_id"),
        "task_type": row.get("task_type"),
        "expected_label": label,
        "expected_value": value,
        "option_count": len(options),
        "singleton_options": len(options) <= 1,
        "source_heldout_admissible": bool(row.get("source_heldout_admissible")),
        "selected_test_anchor": bool(row.get("selected_test_anchor")),
        "verifier_anchor": bool(row.get("verifier_anchor")),
        "deterministic_option_shuffle": bool(anti.get("deterministic_option_shuffle")),
        "opaque_labels": bool(anti.get("opaque_labels")),
        "reviewed_bundle_source": bool(anti.get("reviewed_bundle_source")),
        "prompt_target_value_leak": prompt_target_value_leak,
        "prompt_target_label_leak": prompt_target_label_leak,
        "role_marker_count": len(role_markers),
        "role_markers": role_markers,
    }


def main() -> None:
    payload = load_json(PAYLOAD)
    result = load_json(RESULT)
    row_records = []
    run_records = []
    for run in payload.get("runs") or []:
        if not isinstance(run, dict):
            continue
        task_pack = run.get("task_pack") if isinstance(run.get("task_pack"), dict) else {}
        rows = [row for row in task_pack.get("rows") or [] if isinstance(row, dict)]
        manifest_rows_by_id = {
            str(row.get("row_id") or ""): row
            for row in task_pack.get("manifest_rows") or []
            if isinstance(row, dict)
        }
        verifier_rows = [row for row in task_pack.get("verifier_rows") or [] if isinstance(row, dict)]
        patch_rows = [row for row in task_pack.get("patch_rows") or [] if isinstance(row, dict)]
        for row in rows:
            merged = dict(row)
            manifest = manifest_rows_by_id.get(str(row.get("row_id") or ""))
            if manifest:
                merged.update({k: v for k, v in manifest.items() if k not in merged or merged.get(k) is None})
            row_records.append(row_audit(merged))
        run_records.append(
            {
                "cell_key": run.get("cell_key"),
                "language_family": task_pack.get("language_family"),
                "rows": len(rows),
                "verifier_rows": len(verifier_rows),
                "patch_rows": len(patch_rows),
                "manifest_mode": task_pack.get("manifest_mode"),
                "train_eligible": task_pack.get("train_eligible"),
                "split_role": task_pack.get("split_role"),
            }
        )

    languages = Counter(str(row.get("language_family") or "") for row in row_records)
    tasks = Counter(str(row.get("task_type") or "") for row in row_records)
    repo_families = Counter(str(row.get("repo_family") or "") for row in row_records)
    roots_by_language: dict[str, set[str]] = defaultdict(set)
    for row in row_records:
        language = str(row.get("language_family") or "")
        root = str(row.get("source_root_id") or "")
        if root:
            roots_by_language[language].add(root)

    counts = {
        "rows": len(row_records),
        "runs": len(run_records),
        "languages": dict(sorted(languages.items())),
        "task_types": dict(sorted(tasks.items())),
        "repo_families": dict(sorted(repo_families.items())),
        "unique_roots": len({str(row.get("source_root_id") or "") for row in row_records if row.get("source_root_id")}),
        "unique_roots_by_language": {lang: len(roots) for lang, roots in sorted(roots_by_language.items())},
        "source_heldout_admissible_rows": sum(1 for row in row_records if row["source_heldout_admissible"]),
        "selected_test_anchor_rows": sum(1 for row in row_records if row["selected_test_anchor"]),
        "verifier_anchor_rows": sum(1 for row in row_records if row["verifier_anchor"]),
        "deterministic_option_shuffle_rows": sum(1 for row in row_records if row["deterministic_option_shuffle"]),
        "singleton_option_rows": sum(1 for row in row_records if row["singleton_options"]),
        "prompt_target_value_leak_rows": sum(1 for row in row_records if row["prompt_target_value_leak"]),
        "prompt_target_label_leak_rows": sum(1 for row in row_records if row["prompt_target_label_leak"]),
        "rows_with_role_markers": sum(1 for row in row_records if row["role_marker_count"]),
        "runs_with_verifier_rows": sum(1 for run in run_records if run["verifier_rows"] > 0),
        "runs_with_patch_rows": sum(1 for run in run_records if run["patch_rows"] > 0),
    }

    gate_checks = {
        "current_harness_execution_passed": bool(result.get("passed")),
        "hundred_m_beats_gemma_on_this_slice": (
            (result.get("metrics") or {}).get("hundred_m_accuracy", 0)
            > (result.get("metrics") or {}).get("gemma12b_accuracy", 0)
        ),
        "all_rows_source_heldout_admissible": counts["source_heldout_admissible_rows"] == counts["rows"],
        "all_rows_option_shuffle_hardened": counts["deterministic_option_shuffle_rows"] == counts["rows"],
        "no_singleton_option_rows": counts["singleton_option_rows"] == 0,
        "no_prompt_target_value_leaks": counts["prompt_target_value_leak_rows"] == 0,
        "all_languages_have_at_least_two_roots": all(value >= 2 for value in counts["unique_roots_by_language"].values()),
        "all_runs_have_verifier_rows": counts["runs_with_verifier_rows"] == counts["runs"],
        "all_runs_have_patch_or_abstain_rows": counts["runs_with_patch_rows"] == counts["runs"],
        "web_has_selected_test_anchor": any(
            row["language_family"] == "web_js_ts_html" and row["selected_test_anchor"] for row in row_records
        ),
        "rust_has_non_singleton_verifier_rows": any(
            row["language_family"] == "rust" and row["task_type"] == "verifier_outcome" and not row["singleton_options"]
            for row in row_records
        ),
    }
    promotion_ready = all(gate_checks.values())
    blockers = [name for name, passed in gate_checks.items() if not passed]

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "promotion_ready": promotion_ready,
        "decision": "do_not_promote_broad_full_product_claim" if not promotion_ready else "promotion_ready",
        "claim_scope": [
            "Eval-hacking and promotion gate audit for the Stage11444 selected-runtime harness writeback.",
            "This audit intentionally can pass while promotion_ready is false; it surfaces risk rather than hiding the current win.",
        ],
        "current_result_metrics": result.get("metrics"),
        "counts": counts,
        "gate_checks": gate_checks,
        "promotion_blockers": blockers,
        "run_records": run_records,
        "high_risk_rows": [
            row
            for row in row_records
            if row["singleton_options"]
            or row["prompt_target_value_leak"]
            or not row["source_heldout_admissible"]
            or not row["deterministic_option_shuffle"]
        ],
        "interpretation": [
            "The Stage11467 harness result is valid as a current-runtime compact bounded-choice maintainer slice.",
            "It is not sufficient for a broad full-product software-repair claim because the packet has no executable verifier/patch rows and is not source-heldout admissible.",
            "The Rust verifier singleton remains a real anti-cheat weakness and should be replaced before using Rust verifier performance as a discriminative claim.",
            "Future promotable harness packets should use root-disjoint/source-heldout rows, deterministic option shuffles, verifier_rows, and patch_or_abstain rows.",
        ],
        "recommended_next_actions": [
            "Replace the Rust singleton verifier row with a non-singleton verifier-transition row from a clean Rust root.",
            "Materialize verifier_rows and patch_rows/abstain rows for each language cell before promoting full-product harness claims.",
            "Build a source-heldout harness successor with at least two independent roots per language and deterministic option shuffling.",
            "Keep Stage11467 as the selected-runtime harness regression/win slice, not the final product claim.",
        ],
        "source_artifacts": {
            "payload": rel(PAYLOAD),
            "result": rel(RESULT),
        },
        "outputs": {"summary": rel(OUT_JSON)},
    }
    write_json(OUT_JSON, audit)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUT_JSON, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "promotion_ready": promotion_ready,
                "decision": audit["decision"],
                "counts": counts,
                "promotion_blockers": blockers,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
