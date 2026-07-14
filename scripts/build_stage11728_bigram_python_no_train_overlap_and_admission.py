#!/usr/bin/env python3
"""Audit and admit Stage11727 bigram Python source-heldout smoke rows."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROWS = ROOT / "runs/local/artifacts/stage11727_bigram_python_source_heldout_smoke_packet/bigram_python_smoke_rows.jsonl"
SOURCE = ROOT / "runs/local/artifacts/stage11727_bigram_python_source_heldout_smoke_packet/bigram_python_source_heldout_smoke_packet.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage11728_bigram_python_no_train_overlap_and_admission"
SUMMARY = ROOT / "runs/summaries/stage11728_bigram_python_no_train_overlap_and_admission.json"


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rg_files(pattern: str) -> list[Path]:
    cmd = ["rg", "-l", "-F", pattern, "runs/local/artifacts", "runs/summaries"]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if proc.returncode not in (0, 1):
        raise RuntimeError(proc.stderr)
    return [ROOT / line.strip() for line in proc.stdout.splitlines() if line.strip()]


def external_hits(files: list[Path]) -> list[str]:
    hits = []
    for path in files:
        relpath = rel(path)
        if "/stage11727_bigram_python_source_heldout_smoke_packet/" in relpath:
            continue
        if "/stage11728_bigram_python_no_train_overlap_and_admission/" in relpath:
            continue
        if relpath == "runs/summaries/stage11727_bigram_python_source_heldout_smoke_packet.json":
            continue
        if relpath == "runs/summaries/stage11728_bigram_python_no_train_overlap_and_admission.json":
            continue
        hits.append(relpath)
    return sorted(set(hits))


def admit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    admitted = []
    for row in rows:
        rr = dict(row)
        rr["row_id"] = rr["row_id"].replace("::candidate_v1", "::admitted_source_heldout_v1")
        rr["split"] = "strict_eval"
        rr["split_role"] = "strict_source_heldout_smoke"
        rr["strict_eval_eligible"] = True
        rr["source_heldout_admissible"] = True
        rr["source_heldout_attestation"] = "stage11728_pass_no_exact_new_root_train_overlap"
        rr["admission_stage"] = 11728
        rr["admission_evidence"] = {
            "no_train_overlap_audit": "runs/local/artifacts/stage11728_bigram_python_no_train_overlap_and_admission/bigram_python_no_train_overlap_and_admission.json",
            "source_packet": "runs/local/artifacts/stage11727_bigram_python_source_heldout_smoke_packet/bigram_python_source_heldout_smoke_packet.json",
        }
        rr["anti_cheat"] = dict(rr.get("anti_cheat") or {})
        rr["anti_cheat"]["source_heldout_admitted_after_no_train_overlap_audit"] = True
        rr["anti_cheat"]["requires_no_train_overlap_audit"] = False
        admitted.append(rr)
    return admitted


def main() -> None:
    source = read_json(SOURCE)
    rows = read_jsonl(ROWS)
    if not rows:
        raise SystemExit("no rows")
    root_id = rows[0]["root_id"]
    snapshot = rows[0]["source_snapshot_id"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)

    root_hits = external_hits(rg_files(root_id))
    snapshot_hits = external_hits(rg_files(snapshot))
    exact_hits = sorted(set(root_hits + snapshot_hits))
    passed = not exact_hits
    admitted = admit_rows(rows) if passed else []

    rows_out = OUT_DIR / "bigram_python_admitted_smoke_rows.jsonl"
    hits_out = OUT_DIR / "bigram_python_overlap_hits.jsonl"
    artifact_path = OUT_DIR / "bigram_python_no_train_overlap_and_admission.json"
    write_jsonl(rows_out, admitted)
    write_jsonl(hits_out, [{"hit": hit} for hit in exact_hits])

    artifact = {
        "stage": 11728,
        "stage_name": "bigram_python_no_train_overlap_and_admission",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "bigram_python_source_heldout_smoke_admitted"
        if passed
        else "bigram_python_source_heldout_smoke_blocked_by_exact_overlap",
        "passed": passed,
        "language_family": "python",
        "repo_family": "bigram_language_model",
        "root_id": root_id,
        "source_snapshot_id": snapshot,
        "source_stage_decision": source.get("decision"),
        "row_count": len(rows),
        "admitted_row_count": len(admitted),
        "exact_overlap_hit_count": len(exact_hits),
        "exact_overlap_hits": exact_hits[:50],
        "admission_basis": "pass_no_exact_new_root_train_overlap" if passed else "blocked_exact_root_or_snapshot_overlap",
        "remaining_limitations": [
            "Verifier transition is static selected-test anchoring, not executed fail/pass.",
            "Exact root/snapshot overlap passed, but broad repo-family/path overlap is not a repo-heldout proof.",
            "Rows support source-heldout compact smoke, not full-product patch repair.",
        ],
        "next_stage_acceptance": [
            "run Stage11507 selected product scorer on these 4 rows",
            "run diagnostic scorer sweep if selected product scorer fails",
            "run Gemma same-manifest only through GPU2-safe backend",
            "attach executable verifier/harness fields before full-product claim",
        ],
        "source_artifacts": {
            "stage11727_artifact": rel(SOURCE),
            "stage11727_rows": rel(ROWS),
        },
        "outputs": {
            "artifact": rel(artifact_path),
            "admitted_rows_jsonl": rel(rows_out),
            "overlap_hits_jsonl": rel(hits_out),
            "summary": rel(SUMMARY),
        },
    }
    write_json(artifact_path, artifact)
    shutil.copyfile(artifact_path, SUMMARY)
    print(json.dumps({"decision": artifact["decision"], "passed": passed, "admitted_rows": len(admitted), "exact_hits": len(exact_hits)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
