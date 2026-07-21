#!/usr/bin/env python3
"""Queue build-verifier sealed roots from Stage12108 missing-test candidates."""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
STAGE = 12109
NAME = "stage12109_build_verifier_gap_fill_queue"
OUT = ART / NAME
SUMMARY = OUT / "build_verifier_gap_fill_queue.json"
MIRROR = SUM / f"{NAME}.json"
WORK_ITEMS = OUT / "build_verifier_gap_fill_work_items.jsonl"

STAGE12107 = SUM / "stage12107_fresh_sealed_transition_root_materializer.json"
STAGE12108_REJECTED = ART / "stage12108_fresh_sealed_gap_fill_atlas/fresh_sealed_gap_fill_rejected.jsonl"


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


def slug(value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "")).strip("_")


def command_plan(lane: str, manifests: list[str]) -> dict[str, list[str]]:
    if "package.json" in manifests or lane == "web_js_ts_html":
        return {
            "build_probe": ["npm", "run", "build", "--if-present"],
            "test_probe": ["npm", "test", "--", "--runInBand"],
            "not_exercised_probe": ["npm", "test", "--", "stage12109_nonexistent_filter"],
        }
    if "CMakeLists.txt" in manifests:
        return {
            "build_probe": ["cmake", "-S", ".", "-B", "/data/tmp/stage12109_cmake_build"],
            "test_probe": ["ctest", "--test-dir", "/data/tmp/stage12109_cmake_build", "--output-on-failure"],
            "not_exercised_probe": ["ctest", "--test-dir", "/data/tmp/stage12109_cmake_build", "-R", "stage12109_nonexistent_filter"],
        }
    if "Makefile" in manifests:
        return {
            "build_probe": ["make", "-n"],
            "test_probe": ["make", "test"],
            "not_exercised_probe": ["make", "-n", "stage12109_nonexistent_target"],
        }
    return {
        "build_probe": ["python", "-m", "py_compile", "."],
        "test_probe": ["python", "-m", "pytest", "-q"],
        "not_exercised_probe": ["python", "-m", "pytest", "-q", "-k", "stage12109_nonexistent_filter"],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12107 = read_json(STAGE12107)
    rejected = read_jsonl(STAGE12108_REJECTED)
    work = []
    counts = Counter()

    for row in rejected:
        reasons = set(row.get("reasons") or [])
        lane = row.get("lane")
        if reasons != {"missing_test_marker"}:
            continue
        if lane not in {"c_cpp", "web_js_ts_html", "mixed_build_config_dependency"}:
            continue
        source_path = str(row.get("source_path") or "")
        item_id = "stage12109::" + slug(source_path)[-96:]
        manifests = row.get("manifests") or []
        item = {
            "stage12109_build_verifier_gap_fill": True,
            "work_item_id": item_id,
            "root_id": item_id,
            "root_lineage_key": item_id,
            "repo_family": row.get("repo_family"),
            "source_path": source_path,
            "language_lane": lane,
            "language_guess": row.get("language_guess") or [],
            "manifests": manifests,
            "test_markers": row.get("test_markers") or [],
            "sealed_split_role": "sealed_confirm_only",
            "train_support_only": False,
            "strict_eval_eligible": True,
            "source_heldout_admissible": True,
            "do_not_train": True,
            "build_verifier_only": True,
            "claim_boundary": "May support build/config transition rows, not selected-test verifier claims unless a later execution finds real tests.",
            "command_plan": command_plan(lane, manifests),
            "allowed_projection_rows": [
                "transition_next_action",
                "transition_candidate_selection",
                "transition_verifier_transition",
                "transition_continue_or_stop",
            ],
            "required_candidate_semantics": [
                "BUILD_PROBE",
                "RUN_TEST_IF_AVAILABLE",
                "NOT_EXERCISED_OR_NO_SELECTED_TEST",
                "INSUFFICIENT_EVIDENCE",
            ],
            "anti_cheat_contract": {
                "deterministic_option_shuffle": True,
                "singleton_options": False,
                "target_label_not_visible_before_options": True,
                "target_value_not_visible_before_options": True,
                "semantic_candidate_identity_eval": True,
                "root_lineage_disjoint_from_prior_transition_stages": True,
                "build_only_not_misrepresented_as_selected_test": True,
            },
        }
        work.append(item)
        counts[lane] += 1

    prior_lane_counts = Counter(stage12107["lane_counts"])
    combined = prior_lane_counts + counts
    target = {
        "c_cpp": 25,
        "mixed_build_config_dependency": 15,
        "python": 20,
        "rust": 20,
        "web_js_ts_html": 20,
    }
    remaining = {lane: max(0, need - combined.get(lane, 0)) for lane, need in target.items()}
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "build_verifier_gap_fill_queue_ready_partial",
        "do_not_train": True,
        "work_items": len(work),
        "work_items_by_lane": dict(sorted(counts.items())),
        "combined_with_stage12107_by_lane": dict(sorted(combined.items())),
        "remaining_after_build_verifier_gap_fill": remaining,
        "claim_boundary": [
            "These roots can only become sealed rows if execution captures build/verifier evidence.",
            "Rows with no selected test must be labeled as build/config or insufficient-evidence transitions.",
            "This still does not fill the Rust sealed-root gap.",
        ],
        "next_stage_recommendation": {
            "stage": "stage12110_execute_sealed_build_verifier_probes_or_acquire_rust_web",
            "action": "Execute Stage12107 + Stage12109 probes where safe, and acquire fresh Rust plus additional Web/C++ roots outside prior transition families.",
            "remaining_hard_gap": remaining,
        },
        "source_artifacts": {
            "stage12107_summary": rel(STAGE12107),
            "stage12108_rejected_rows": rel(STAGE12108_REJECTED),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "summary_mirror": rel(MIRROR),
            "work_items": rel(WORK_ITEMS),
        },
    }
    write_jsonl(WORK_ITEMS, work)
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        "decision": summary["decision"],
        "work_items": len(work),
        "work_items_by_lane": summary["work_items_by_lane"],
        "remaining_after_build_verifier_gap_fill": remaining,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
