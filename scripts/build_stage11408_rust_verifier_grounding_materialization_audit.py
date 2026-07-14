#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11408
NAME = "stage11408_rust_verifier_grounding_materialization_audit"
OUT = ART / NAME
SUMMARY = OUT / "rust_verifier_grounding_materialization_audit.json"
QUEUE = OUT / "rust_verifier_grounding_materialization_queue.jsonl"

STAGE11406_ROOTS = ART / "stage11406_local_rust_source_acquisition_atlas/local_rust_source_roots.jsonl"
STAGE11405_REQUESTS = ART / "stage11405_rust_train_support_materialization_request/rust_train_support_materialization_requests.jsonl"

RESERVED_REPO_FAMILIES = {"rust", "rust-analyzer", "prusti-dev"}
WEAK_REPO_FAMILIES = {"tokenizers"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def path_exists(value: Any) -> bool:
    return bool(value) and Path(str(value)).exists()


def infer_cargo_command(crate_dir: str) -> str | None:
    path = Path(crate_dir)
    if not (path / "Cargo.toml").exists():
        return None
    return f"cargo test --manifest-path {path / 'Cargo.toml'}"


def has_inline_test(path: str | None) -> bool:
    if not path:
        return False
    p = Path(path)
    if not p.exists() or p.suffix != ".rs":
        return False
    try:
        for line in p.read_text(errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("#[test]") or stripped.startswith("#[cfg(test)]"):
                return True
    except OSError:
        return False
    return False


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    local_roots = read_jsonl(STAGE11406_ROOTS)
    prior_requests = read_jsonl(STAGE11405_REQUESTS)

    queue: list[dict[str, Any]] = []
    for root in local_roots:
        repo = str(root.get("repo_family") or "unknown")
        if repo in RESERVED_REPO_FAMILIES:
            continue
        source_path = root.get("candidate_change_surface_path")
        verifier_path = root.get("verifier_or_test_constraint_path")
        crate_dir = str(root.get("crate_dir") or "")
        cargo_cmd = infer_cargo_command(crate_dir)
        blockers: list[str] = []
        if repo in WEAK_REPO_FAMILIES:
            blockers.append("weak_or_quarantined_repo_family")
        if not path_exists(root.get("cargo_toml")):
            blockers.append("missing_cargo_or_workspace_marker")
        if not path_exists(source_path):
            blockers.append("missing_exact_rs_source_snippet_path")
        if not path_exists(verifier_path):
            blockers.append("missing_exact_test_or_verifier_path")
        if not cargo_cmd:
            blockers.append("missing_exact_verifier_command")
        if not (has_inline_test(str(verifier_path)) or (verifier_path and "/tests/" in str(verifier_path))):
            blockers.append("missing_selected_test_anchor")
        # This audit intentionally requires an observed log to prevent source-only rows from entering train.
        blockers.append("missing_actual_verifier_log_or_selected_test_execution_record")

        can_materialize_after_log = all(
            reason == "missing_actual_verifier_log_or_selected_test_execution_record"
            for reason in blockers
        )
        queue.append(
            {
                "root_id": root.get("root_id"),
                "repo_family": repo,
                "crate_dir": crate_dir,
                "cargo_toml": root.get("cargo_toml"),
                "candidate_change_surface_path": source_path,
                "verifier_or_test_constraint_path": verifier_path,
                "inferred_verifier_command": cargo_cmd,
                "required_actual_verifier_log": True,
                "required_role_distinct_evidence": [
                    "candidate_change_surface",
                    "symptom_or_call_path",
                    "verifier_and_test_constraint",
                ],
                "blockers": blockers,
                "can_materialize_after_verifier_log": can_materialize_after_log,
                "train_support_allowed_now": False,
            }
        )

    for request in prior_requests:
        if request.get("lane") != "blocked_source_row_materialization":
            continue
        queue.append(
            {
                "root_id": request.get("root_lineage_key"),
                "repo_family": request.get("repo_family") or "unknown",
                "source_row_id": request.get("source_row_id"),
                "blockers": [
                    "missing_local_or_fetchable_repo_snapshot",
                    "missing_exact_rs_source_snippet_path",
                    "missing_exact_test_or_verifier_path",
                    "missing_exact_verifier_command",
                    "missing_actual_verifier_log_or_selected_test_execution_record",
                ],
                "required_actual_verifier_log": True,
                "can_materialize_after_verifier_log": False,
                "train_support_allowed_now": False,
            }
        )

    blocker_counts = Counter(reason for item in queue for reason in item.get("blockers", []))
    repo_counts = Counter(str(item.get("repo_family") or "unknown") for item in queue)
    after_log_ready = [item for item in queue if item.get("can_materialize_after_verifier_log")]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "rust_verifier_grounding_audit_ready_no_train_rows",
        "counts": {
            "queue_items": len(queue),
            "local_roots_examined": len(local_roots),
            "blocked_source_rows_carried_forward": sum(1 for q in queue if q.get("source_row_id")),
            "can_materialize_after_verifier_log": len(after_log_ready),
            "train_support_allowed_now": 0,
            "minimum_clean_roots_required_before_probe": 10,
        },
        "by_repo_family": dict(sorted(repo_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "quality_gate": {
            "actual_verifier_logs_present": False,
            "train_rows_emitted": False,
            "stage11404_retry_warranted": False,
            "probe_ready": False,
        },
        "interpretation": (
            "Local Rust source roots are useful candidates, but none currently has a stored actual verifier log or selected-test "
            "execution record. They remain materialization queue items, not usable train supply."
        ),
        "recommended_next_action": (
            "Run or recover verifier logs for the candidates marked can_materialize_after_verifier_log, then build role-distinct "
            "candidate_change_surface, symptom_or_call_path, and verifier_and_test_constraint rows. Re-run the admission gate before training."
        ),
        "source_artifacts": {
            "stage11406_roots": rel(STAGE11406_ROOTS),
            "stage11405_requests": rel(STAGE11405_REQUESTS),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "queue": rel(QUEUE),
        },
    }
    write_jsonl(QUEUE, queue)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
