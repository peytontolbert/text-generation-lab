#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage10731_cpp_materialization_candidate_packet"

COMPILED_ROOTS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
BOOTSTRAP_ROWS = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/multitarget_bootstrap_with_heldout_rows.jsonl"
REVIEWED_ROOTS = ROOT / "runs/local/artifacts/stage10687_reviewed_v27_plus_two_fresh_rust_support_package/reviewed_v27_plus_two_fresh_rust_root_manifest.jsonl"
STAGE10730 = ROOT / "runs/local/artifacts/stage10730_multilingual_root_scale_frontier_queue/multilingual_root_scale_frontier_queue.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


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
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def root_lineage_key(root: dict[str, Any]) -> str:
    repo_id = str(root.get("repo_id") or "unknown")
    snapshot_id = str(root.get("snapshot_id") or root.get("root_id") or "unknown")
    return f"{repo_id}::{snapshot_id}"


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    compiled_roots = load_jsonl(COMPILED_ROOTS)
    bootstrap_rows = load_jsonl(BOOTSTRAP_ROWS)
    reviewed_roots = load_jsonl(REVIEWED_ROOTS)
    stage10730 = load_json(STAGE10730)

    reviewed_lineage = {
        root_lineage_key(row)
        for row in reviewed_roots
        if str(row.get("language_family") or "") == "c_cpp"
    }

    cpp_roots = {
        str(row["root_id"]): row
        for row in compiled_roots
        if str(row.get("language_family") or "") == "c_cpp"
    }

    agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "row_count": 0,
            "prompt_target_leak_rows": 0,
            "opaque_option_rows": 0,
            "target_subtypes": Counter(),
            "target_families": Counter(),
        }
    )
    for row in bootstrap_rows:
        if str(row.get("language_family") or "") != "c_cpp":
            continue
        entry = agg[str(row["root_id"])]
        entry["row_count"] += 1
        anti_cheat = row.get("anti_cheat") or {}
        if anti_cheat.get("prompt_target_leak"):
            entry["prompt_target_leak_rows"] += 1
        if anti_cheat.get("opaque_option_contract"):
            entry["opaque_option_rows"] += 1
        entry["target_subtypes"][str(row.get("target_subtype") or "unknown")] += 1
        entry["target_families"][str(row.get("target_family") or "unknown")] += 1

    clean_candidates: list[dict[str, Any]] = []
    quarantined_candidates: list[dict[str, Any]] = []

    for root_id, root in cpp_roots.items():
        meta = agg.get(root_id)
        if not meta:
            continue
        repo_family = str(root.get("repo_family") or root.get("repo_id") or "unknown")
        record = {
            "root_id": root_id,
            "repo_id": root.get("repo_id"),
            "repo_family": repo_family,
            "snapshot_id": root.get("snapshot_id"),
            "verifier_id": root.get("verifier_id"),
            "split_component": root.get("split_component"),
            "task_family": root.get("task_family"),
            "reviewed_overlap": root_lineage_key(root) in reviewed_lineage,
            "row_count": meta["row_count"],
            "prompt_target_leak_rows": meta["prompt_target_leak_rows"],
            "opaque_option_rows": meta["opaque_option_rows"],
            "target_subtypes": dict(meta["target_subtypes"]),
            "target_families": dict(meta["target_families"]),
            "target_richness_score": (
                len(meta["target_subtypes"])
                + len(meta["target_families"])
                + (1 if meta["target_subtypes"].get("patch_sketch") else 0)
                + (1 if meta["target_subtypes"].get("repair_intent") else 0)
            ),
        }

        if record["reviewed_overlap"]:
            record["quarantine_reason"] = "already_consumed_reviewed_lineage"
            quarantined_candidates.append(record)
            continue
        if record["prompt_target_leak_rows"] > 0:
            record["quarantine_reason"] = "prompt_target_leak_present"
            quarantined_candidates.append(record)
            continue
        if str(record["verifier_id"] or "") != "PASS_TARGETED_TEST_SELECTION":
            record["quarantine_reason"] = "missing_targeted_test_verifier"
            quarantined_candidates.append(record)
            continue
        clean_candidates.append(record)

    clean_candidates.sort(
        key=lambda row: (
            -int(row["target_richness_score"]),
            -int(row["row_count"]),
            row["repo_family"],
            row["root_id"],
        )
    )

    # Diversity cap to avoid flooding with parametergolf clones in the first packet.
    selected: list[dict[str, Any]] = []
    per_repo: Counter[str] = Counter()
    for row in clean_candidates:
        repo_family = row["repo_family"]
        cap = 3 if repo_family == "parametergolf" else 2
        if per_repo[repo_family] >= cap:
            continue
        selected.append(row)
        per_repo[repo_family] += 1
        if len(selected) >= 12:
            break

    quarantine_reason_counts = Counter(row.get("quarantine_reason", "unknown") for row in quarantined_candidates)

    summary = {
        "stage": 10731,
        "stage_name": "stage10731_cpp_materialization_candidate_packet",
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "cpp_materialization_candidate_packet_ready",
        "claim_scope": [
            "Turn the stage10730 C/C++ scaling lane into a concrete materialization packet.",
            "Separate clean bootstrap roots from quarantined roots with prompt-target leak or already-consumed lineage.",
            "Frontload diverse repo families so C/C++ can expand honestly without collapsing into parametergolf repetition.",
        ],
        "headline_findings": [
            f"C/C++ has {len(cpp_roots)} compiled roots total, but only {len(clean_candidates)} are currently clean enough for immediate materialization candidate use.",
            f"The first packet selects {len(selected)} clean roots across {len(per_repo)} repo families with a repo-cap to reduce duplicate-pattern inflation.",
            "Most audited bootstrap C/C++ roots remain quarantined because decisive_evidence/retrieve_answer_abstain rows still carry prompt-target leakage.",
        ],
        "lane_context": {
            "stage10730_lane_blocker": stage10730["language_lanes"]["c_cpp"]["lane_blocker"],
            "stage10730_strict_accuracy": stage10730["language_lanes"]["c_cpp"]["strict_accuracy"],
            "stage10730_compiled_root_count": stage10730["language_lanes"]["c_cpp"]["compiled_root_count"],
        },
        "packet_metrics": {
            "compiled_root_count": len(cpp_roots),
            "clean_candidate_count": len(clean_candidates),
            "selected_candidate_count": len(selected),
            "quarantined_root_count": len(quarantined_candidates),
            "selected_repo_family_counts": dict(per_repo),
            "quarantine_reason_counts": dict(quarantine_reason_counts),
        },
        "anti_cheat_contract": [
            "Do not materialize any root with prompt_target_leak_rows > 0 into promotable rows without first rewriting the evidence contract.",
            "Keep repo-family caps during first-wave materialization to avoid inflating one repeated pattern into faux scale.",
            "Preserve root-lineage disjointness against existing reviewed v2.7/v2.8 C/C++ roots.",
            "Require visible evidence support for each gold option before any new row enters train or eval.",
        ],
        "next_best_steps": [
            "Materialize the selected roots into reviewed maintainer bundles with real candidate paths, verifier anchors, and anti-cheat cards.",
            "Rewrite the quarantined audited C/C++ bootstrap roots only after removing prompt-target leakage from decisive_evidence contracts.",
            "Use the selected C/C++ packet as the first large-scale honest bundle-materialization lane from the long-context compiler.",
        ],
        "sources": {
            "compiled_roots": rel(COMPILED_ROOTS),
            "bootstrap_rows": rel(BOOTSTRAP_ROWS),
            "reviewed_roots": rel(REVIEWED_ROOTS),
            "stage10730_queue": rel(STAGE10730),
        },
        "output_files": {
            "summary_json": rel(ARTIFACT_DIR / "cpp_materialization_candidate_packet.json"),
            "selected_candidates_jsonl": rel(ARTIFACT_DIR / "cpp_materialization_selected_roots.jsonl"),
            "quarantined_candidates_jsonl": rel(ARTIFACT_DIR / "cpp_materialization_quarantined_roots.jsonl"),
        },
    }

    write_json(ARTIFACT_DIR / "cpp_materialization_candidate_packet.json", summary)
    write_jsonl(ARTIFACT_DIR / "cpp_materialization_selected_roots.jsonl", selected)
    write_jsonl(ARTIFACT_DIR / "cpp_materialization_quarantined_roots.jsonl", quarantined_candidates)
    print(ARTIFACT_DIR / "cpp_materialization_candidate_packet.json")


if __name__ == "__main__":
    main()
