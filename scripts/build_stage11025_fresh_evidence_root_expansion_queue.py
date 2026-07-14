#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
OUT_DIR = ARTIFACTS / "stage11025_fresh_evidence_root_expansion_queue"

EVIDENCE_ROOT_SCALE = ARTIFACTS / "stage11024_multilingual_evidence_root_scale_package" / "multilingual_evidence_root_scale_package.json"
ROOT_INVENTORY = ARTIFACTS / "stage11024_multilingual_evidence_root_scale_package" / "root_inventory.jsonl"
NEXT_BATCH_ROWS = ARTIFACTS / "stage10956_multilingual_evidence_next_batch_package" / "next_batch_rows.jsonl"
IMMEDIATE_BUNDLE = ARTIFACTS / "stage10970_immediate_evidence_replenishment_bundle" / "bundle_rows.jsonl"
RUST_REVIEWED_BUNDLE = ARTIFACTS / "stage10972_rust_reviewed_evidence_bundle" / "bundle_rows.jsonl"
EXPANDED_SUCCESSORS = ARTIFACTS / "stage10963_expanded_evidence_successor_family" / "expanded_successor_rows.jsonl"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def root_sig(row: dict) -> str:
    return str(row.get("source_bundle_id") or row.get("bundle_id") or row.get("queue_id") or row.get("row_id"))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    scale = read_json(EVIDENCE_ROOT_SCALE)
    inventory = read_jsonl(ROOT_INVENTORY)
    next_batch = read_jsonl(NEXT_BATCH_ROWS)
    immediate_rows = read_jsonl(IMMEDIATE_BUNDLE)
    rust_rows = read_jsonl(RUST_REVIEWED_BUNDLE)
    expanded_rows = read_jsonl(EXPANDED_SUCCESSORS)

    by_root: dict[str, dict] = {}

    def ensure(sig: str, *, language: str, repo_family: str, source_kind: str) -> dict:
        record = by_root.setdefault(
            sig,
            {
                "root_signature": sig,
                "language_family": language,
                "repo_family": repo_family,
                "source_kinds": set(),
                "queue_ids": set(),
                "task_types": Counter(),
                "targets": Counter(),
                "selected_tests": set(),
                "row_ids": [],
                "support_row_count": 0,
                "candidate_row_count": 0,
                "geometry_row_count": 0,
                "freshness_class": "reviewed_or_unknown",
            },
        )
        record["source_kinds"].add(source_kind)
        return record

    for row in immediate_rows:
        sig = root_sig(row)
        record = ensure(sig, language=str(row.get("language_family", "unknown")), repo_family=str(row.get("repo_family", "unknown")), source_kind="immediate_replenishment")
        record["task_types"][str(row.get("task_type", "unknown"))] += 1
        record["targets"][str(row.get("target_text", "unknown"))] += 1
        record["row_ids"].append(str(row.get("row_id", "")))
        record["support_row_count"] += 1
        if "stage10938::" in str(row.get("row_id", "")):
            record["candidate_row_count"] += 1
        qid = row.get("queue_id")
        if qid:
            record["queue_ids"].add(str(qid))
        for test in row.get("selected_tests") or []:
            record["selected_tests"].add(str(test))
        record["freshness_class"] = "fresh_immediate"

    for row in rust_rows:
        sig = root_sig(row)
        record = ensure(sig, language=str(row.get("language_family", "unknown")), repo_family=str(row.get("repo_family", "unknown")), source_kind="rust_reviewed_bundle")
        record["task_types"][str(row.get("task_type", "unknown"))] += 1
        record["targets"][str(row.get("target_text", "unknown"))] += 1
        record["row_ids"].append(str(row.get("row_id", "")))
        record["support_row_count"] += 1
        if "stage10938::" in str(row.get("row_id", "")):
            record["candidate_row_count"] += 1
        qid = row.get("queue_id")
        if qid:
            record["queue_ids"].add(str(qid))
        for test in row.get("selected_tests") or []:
            record["selected_tests"].add(str(test))
        record["freshness_class"] = "reviewed_rust"

    for row in expanded_rows:
        sig = root_sig(row)
        record = ensure(sig, language=str(row.get("language_family", "unknown")), repo_family=str(row.get("repo_family", "unknown")), source_kind="expanded_same_root_geometry")
        record["task_types"][str(row.get("task_type", "unknown"))] += 1
        record["targets"][str(row.get("target_text", "unknown"))] += 1
        record["row_ids"].append(str(row.get("row_id", "")))
        record["geometry_row_count"] += 1

    queue_requirements: dict[str, dict] = {}
    for row in next_batch:
        qid = row.get("queue_id")
        if not qid:
            continue
        queue_requirements[qid] = row

    root_inventory_lookup = {row["root_signature"]: row for row in inventory}
    expansion_rows: list[dict] = []
    for sig, record in sorted(by_root.items(), key=lambda item: (item[1]["language_family"], item[1]["repo_family"], item[0])):
        qids = sorted(record["queue_ids"])
        queue_payload = queue_requirements.get(qids[0]) if qids else None
        has_selected_tests = bool(record["selected_tests"])
        candidate_targets = sorted(record["targets"].keys())
        language = record["language_family"]
        repo_family = record["repo_family"]

        missing_actions = []
        if record["geometry_row_count"] > 0 and record["candidate_row_count"] <= 1:
            missing_actions.append("new_root_family_needed_beyond_geometry_variants")
        if language in {"python", "c_cpp"} and record["candidate_row_count"] <= 1:
            missing_actions.append("materialize_additional_selected_test_roots")
        if language == "rust" and not has_selected_tests:
            missing_actions.append("prefer_selected_test_anchored_rust_successor")
        if language == "web_js_ts_html":
            missing_actions.append("acquire_pure_web_selected_test_family")
        if "verifier_and_test_constraint" not in candidate_targets and queue_payload and queue_payload.get("gold_answer_value") == "verifier_and_test_constraint":
            missing_actions.append("preserve_verifier_ledgers_in_future_rows")

        priority = 3
        if language == "python":
            priority = 1
        elif language == "c_cpp":
            priority = 2
        elif language == "web_js_ts_html":
            priority = 4

        expansion_rows.append(
            {
                "priority": priority,
                "root_signature": sig,
                "language_family": language,
                "repo_family": repo_family,
                "queue_ids": qids,
                "source_kinds": sorted(record["source_kinds"]),
                "freshness_class": record["freshness_class"],
                "support_row_count": record["support_row_count"],
                "candidate_row_count": record["candidate_row_count"],
                "geometry_row_count": record["geometry_row_count"],
                "task_type_counts": dict(record["task_types"]),
                "target_counts": dict(record["targets"]),
                "selected_tests": sorted(record["selected_tests"]),
                "inventory_record": root_inventory_lookup.get(sig),
                "materialization_requirements": (queue_payload or {}).get("materialization_requirements", []),
                "anti_cheat_challenge_families": (queue_payload or {}).get("anti_cheat_challenge_families", []),
                "next_actions": missing_actions or ["ready_for_next_fresh_root_followup"],
            }
        )

    language_summary = defaultdict(lambda: {"roots": 0, "candidate_rows": 0, "geometry_rows": 0, "support_rows": 0})
    for row in expansion_rows:
        bucket = language_summary[row["language_family"]]
        bucket["roots"] += 1
        bucket["candidate_rows"] += row["candidate_row_count"]
        bucket["geometry_rows"] += row["geometry_row_count"]
        bucket["support_rows"] += row["support_row_count"]

    summary = {
        "stage": 11025,
        "stage_name": "fresh_evidence_root_expansion_queue",
        "claim_scope": [
            "Turn the current evidence-root audit into a concrete multilingual expansion queue with per-root deficits and next actions.",
            "Prioritize new fresh-root supply over more same-root geometry when the current roots are already exhausted.",
            "Keep web explicitly blocked on pure selected-test source supply rather than silently mixing overlap rows into the promotable path."
        ],
        "source_artifacts": {
            "root_scale_package": str(EVIDENCE_ROOT_SCALE.relative_to(ROOT)),
            "root_inventory": str(ROOT_INVENTORY.relative_to(ROOT)),
            "next_batch_rows": str(NEXT_BATCH_ROWS.relative_to(ROOT)),
            "immediate_bundle_rows": str(IMMEDIATE_BUNDLE.relative_to(ROOT)),
            "rust_reviewed_bundle_rows": str(RUST_REVIEWED_BUNDLE.relative_to(ROOT)),
            "expanded_successor_rows": str(EXPANDED_SUCCESSORS.relative_to(ROOT)),
        },
        "metrics": {
            "queued_roots": len(expansion_rows),
            "queued_by_language": {lang: data["roots"] for lang, data in sorted(language_summary.items())},
            "candidate_rows_by_language": {lang: data["candidate_rows"] for lang, data in sorted(language_summary.items())},
            "geometry_rows_by_language": {lang: data["geometry_rows"] for lang, data in sorted(language_summary.items())},
            "support_rows_by_language": {lang: data["support_rows"] for lang, data in sorted(language_summary.items())},
            "base_evidence_train_rows": scale["metrics"]["evidence_train_rows"],
            "fresh_candidate_bank_rows": scale["metrics"]["fresh_candidate_bank_rows"],
            "distinct_root_signatures": scale["metrics"]["distinct_root_signatures"],
        },
        "findings": [
            "Python and C/C++ evidence widening is still concentrated in three fresh immediate roots; most additional rows are geometry variants rather than new roots.",
            "Rust has more reviewed supply and broader task expansion, but selected-test anchoring is still uneven across its roots.",
            "Web still has no promotable fresh evidence root in this queue and remains blocked on pure selected-test source supply."
        ],
        "next_best_step": [
            "Build at least two additional Python fresh evidence roots beyond repository_library with verifier-and-test-constraint positives and candidate-surface controls.",
            "Build at least two additional C/C++ fresh evidence roots beyond parametergolf and the agentkernel counterfamily.",
            "Acquire a pure web selected-test family before using web in any stronger multilingual evidence headline."
        ],
        "outputs": {
            "summary_json": str((OUT_DIR / "fresh_evidence_root_expansion_queue.json").relative_to(ROOT)),
            "queue_rows_jsonl": str((OUT_DIR / "queue_rows.jsonl").relative_to(ROOT)),
        },
        "passed": True,
    }

    write_jsonl(OUT_DIR / "queue_rows.jsonl", expansion_rows)
    (OUT_DIR / "fresh_evidence_root_expansion_queue.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
