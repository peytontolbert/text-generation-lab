#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from repository_universe_builder import build_repository_universe

STAGE = 8784
NAME = "stage8784_repository_universe_builder_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPOSITORY_UNIVERSE_BUILDER_READINESS_STAGE8784.md"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}
REPOS = [
    {"repo_id": "python_api", "languages": ["python"], "dependencies": ["pytest", "fastapi"], "files": ["app/api.py", "tests/test_api.py"]},
    {"repo_id": "python_cli", "languages": ["python"], "dependencies": ["pytest", "click"], "files": ["cli.py", "tests/test_cli.py"]},
    {"repo_id": "rust_service", "languages": ["rust"], "dependencies": ["tokio"], "files": ["src/main.rs"]},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_repository_universe_builder.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    sample = build_repository_universe(REPOS, dim=16, k=1)
    sample_path = OUT_DIR / "repository_universe_builder_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures = []
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["repo_count"] != 3:
        failures.append("sample_repo_count_wrong")
    if sample["metrics"]["edge_count"] != 3:
        failures.append("sample_edge_count_wrong")
    if sample["metrics"]["authority_rows"] != 0 or sample["metrics"]["raw_source_rows"] != 0:
        failures.append("authority_or_raw_source_rows_nonzero")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "sample_repos": sample["metrics"]["repo_count"],
            "sample_edges": sample["metrics"]["edge_count"],
            "vector_dim": sample["metrics"]["vector_dim"],
            "authority_rows": sample["metrics"]["authority_rows"],
            "raw_source_rows": sample["metrics"]["raw_source_rows"],
            "failures": failures,
        },
        "artifacts": {
            "sample_card": str(sample_path.relative_to(ROOT)),
            "module": "scripts/repository_universe_builder.py",
            "tests": "tests/test_repository_universe_builder.py",
        },
        "decision": (
            "Repository universe builder is ready as a deterministic no-authority source-inventory extension for repo vectors, 3D coordinates, and k-NN repo edges."
            if not failures
            else "Repository universe builder readiness failed."
        ),
        "next_best_step": "Recover traced_eval_observability, then rerun the module/submodule readiness audit without changing registry or central spine concurrently.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage8784 Repository Universe Builder Readiness",
                "",
                f"Passed: `{card['passed']}`",
                "",
                "Recovered a deterministic repository-universe scaffold for source-backed curriculum sampling: repo vectors, simple 3D coordinates, and k-NN similarity edges.",
                "",
                "This is not a learned embedding run and does not mine `/arxiv`; it only defines the local no-authority builder contract.",
                "",
                "Authority remains closed. This does not train, execute, score, emit source/body, or promote.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
