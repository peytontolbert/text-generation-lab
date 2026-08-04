#!/usr/bin/env python3
"""Build an identity-only, fail-closed protected-universe overlap gate."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12558_combined_protected_universe_gate"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
INPUTS = {
    "candidates": ROOT / "runs/local/artifacts/stage12555_swe_rebench_identity_adapter/exact_task_authority_bindings.jsonl",
    "swe_bench_verified": ROOT / "runs/local/artifacts/stage12554_authority_inventory_and_overlap_gate/protected_swe_bench_verified_manifest.json",
    "sealed_transition_atlas": ROOT / "runs/local/artifacts/stage12105_sealed_transition_candidate_atlas/sealed_transition_candidate_rows.jsonl",
    "locked_benchmark_packs": ROOT / "runs/local/artifacts/stage8672_locked_benchmark_pack_manifest/locked_benchmark_packs.jsonl",
    "locked_acceptance_ledger": ROOT / "runs/local/artifacts/stage9718_locked_multilingual_acceptance_evidence_ledger/locked_multilingual_acceptance_evidence_ledger.json",
    "scratchpad_exclusions": ROOT / "runs/local/artifacts/stage12037_scratchpad_contamination_exclusion_audit/scratchpad_excluded_keys.jsonl",
    "training_scratchpad_exclusions": ROOT / "runs/local/artifacts/stage12040_training_data_scratchpad_contamination_gate/training_scratchpad_excluded_keys.jsonl",
}
ZERO = {
    "admission_allowed": False,
    "training_allowed": False,
    "replay_allowed": False,
    "root_credit": False,
    "repair_credit": False,
    "level3_credit": False,
    "strict_eval_eligible": False,
    "gpu_allowed": False,
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_repo(value: Any) -> str | None:
    text = str(value or "").strip().replace("\\", "/").removesuffix(".git").strip("/").lower()
    parts = text.split("/")
    if len(parts) != 2 or any(not part or part in {".", ".."} for part in parts):
        return None
    return "/".join(parts)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def identity(row: dict[str, Any]) -> tuple[str, str, str] | None:
    item = row.get("task_identity") if isinstance(row.get("task_identity"), dict) else row
    repo = canonical_repo(item.get("canonical_repo") or item.get("repo"))
    instance = str(item.get("instance_id") or "").strip()
    commit = str(item.get("base_commit") or "").strip().lower()
    if repo is None or not instance or len(commit) != 40:
        return None
    return repo, instance, commit


def adjudicate(candidates: list[dict[str, Any]], universes: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_keys = {key for row in candidates if (key := identity(row)) is not None}
    candidate_repos = {key[0] for key in candidate_keys}
    records: list[dict[str, Any]] = []
    all_complete = True
    any_overlap = False
    any_repo_overlap = False
    for universe in universes:
        rows = universe.get("tasks") if isinstance(universe.get("tasks"), list) else []
        keys = {key for row in rows if isinstance(row, dict) and (key := identity(row)) is not None}
        complete = bool(universe.get("declared_complete")) and bool(universe.get("canonical_lineage_complete"))
        complete = complete and bool(SHA256_RE.fullmatch(str(universe.get("source_sha256") or "")))
        complete = complete and len(keys) == len(rows) and bool(rows)
        overlap = sorted(candidate_keys & keys)
        repo_overlap = sorted(candidate_repos & {key[0] for key in keys})
        all_complete &= complete
        any_overlap |= bool(overlap)
        any_repo_overlap |= bool(repo_overlap)
        records.append({
            "universe_id": universe.get("universe_id"),
            "source_path": universe.get("source_path"),
            "source_sha256": universe.get("source_sha256"),
            "declared_task_count": len(rows),
            "canonical_identity_count": len(keys),
            "coverage_complete": complete,
            "exact_task_overlap_count": len(overlap),
            "canonical_repo_overlap_count": len(repo_overlap),
            "overlap_identity_sha256": hashlib.sha256(json.dumps(overlap, sort_keys=True).encode()).hexdigest(),
        })
    clearance = bool(candidate_keys) and bool(universes) and all_complete and not any_overlap and not any_repo_overlap
    return {"records": records, "candidate_identity_count": len(candidate_keys), "all_universes_complete": all_complete,
            "any_exact_task_overlap": any_overlap, "any_canonical_repo_overlap": any_repo_overlap,
            "protected_clearance": clearance}


def _manifest_tasks(value: Any) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if {"instance_id", "repo", "base_commit"}.issubset(value):
            tasks.append(value)
        for child in value.values():
            tasks.extend(_manifest_tasks(child))
    elif isinstance(value, list):
        for child in value:
            tasks.extend(_manifest_tasks(child))
    return tasks


def build(inputs: dict[str, Path] = INPUTS) -> dict[str, Any]:
    candidates = read_jsonl(inputs["candidates"])
    universes: list[dict[str, Any]] = []
    for name, path in inputs.items():
        if name == "candidates":
            continue
        exists = path.is_file()
        # Legacy universes are digest-bound but not parsed because they lack a
        # certified canonical identity schema and may contain protected content.
        tasks = _manifest_tasks(read_json(path)) if exists and name == "swe_bench_verified" else []
        complete = name == "swe_bench_verified" and bool(tasks)
        universes.append({"universe_id": name, "source_path": str(path), "source_sha256": file_sha256(path),
                          "declared_complete": complete, "canonical_lineage_complete": complete, "tasks": tasks})
    result = adjudicate(candidates, universes)
    unresolved = [row["universe_id"] for row in result["records"] if not row["coverage_complete"]]
    summary = {
        "stage": STAGE,
        "record_type": "stage12558_combined_protected_universe_gate_summary_v1",
        "candidate_count": len(candidates),
        "candidate_identity_count": result["candidate_identity_count"],
        "universe_count": len(result["records"]),
        "complete_universe_count": sum(row["coverage_complete"] for row in result["records"]),
        "unresolved_universes": unresolved,
        "any_exact_task_overlap": result["any_exact_task_overlap"],
        "any_canonical_repo_overlap": result["any_canonical_repo_overlap"],
        "protected_clearance": result["protected_clearance"],
        "forbidden_content_fields_read": [],
        "identity_only": True,
        **ZERO,
    }
    return {"records": result["records"], "summary": summary}


def main() -> int:
    result = build()
    write_jsonl(OUT / "universe_coverage.jsonl", result["records"])
    write_json(OUT / "summary.json", result["summary"])
    write_json(SUMMARY, result["summary"])
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
