#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from artifact_paths import (
    arxiv_is_backup_only,
    assert_allowed_storage_path,
    load_storage_policy,
    stage_artifact_dir,
    stage_summary_path,
)

STAGE_NAME = "stage8653_focused_storage_and_single_cleanup_policy"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    errors: list[str] = []
    policy = load_storage_policy()
    out_dir = stage_artifact_dir(STAGE_NAME)
    out_dir.mkdir(parents=True, exist_ok=True)

    required_locations = [
        "stage_summaries",
        "stage_artifacts",
        "probe_outputs",
        "docs",
        "configs",
        "tests",
        "scripts",
    ]
    locations = policy.get("allowed_write_locations", {})
    if not isinstance(locations, dict):
        errors.append("allowed_write_locations missing or invalid")
        locations = {}

    focused_roots: dict[str, str] = {}
    for key in required_locations:
        rel = locations.get(key)
        if not isinstance(rel, str):
            errors.append(f"missing focused storage root: {key}")
            continue
        path = assert_allowed_storage_path(ROOT / rel)
        path.mkdir(parents=True, exist_ok=True)
        focused_roots[key] = _rel(path)

    cleanup_entrypoint = policy.get("single_cleanup_entrypoint")
    if cleanup_entrypoint != "scripts/safe_cleanup.py":
        errors.append("single cleanup entrypoint must be scripts/safe_cleanup.py")

    cleanup_named_scripts = sorted(
        _rel(path) for path in (ROOT / "scripts").glob("*.py") if "cleanup" in path.name and path.name != "safe_cleanup.py"
    )
    if cleanup_named_scripts:
        errors.append("unexpected cleanup-named scripts: " + ", ".join(cleanup_named_scripts))

    destructive_tokens = ["shutil." + "rmtree", ".un" + "link(", "os." + "remove", "rmdir" + "(", "rm " + "-rf"]
    allowed_destructive_files = {
        "scripts/safe_cleanup.py",
        "scripts/safe_paths.py",
        "tests/test_safe_cleanup.py",
        "scripts/audit_stage8651_no_destructive_training_preflight.py",
    }
    destructive_hits = []
    for root_name in ["legacy_src", "scripts", "tests"]:
        base = ROOT / root_name
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            rel = _rel(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            for token in destructive_tokens:
                if token in text:
                    destructive_hits.append({"path": rel, "token": token})
                    if rel not in allowed_destructive_files:
                        errors.append(f"destructive token outside allowlist: {rel} {token}")

    gates = {
        "focused_storage_policy_present": (ROOT / "configs" / "storage" / "focused_storage_policy_v1.json").is_file(),
        "focused_roots_present": len(focused_roots) == len(required_locations),
        "single_cleanup_entrypoint": cleanup_entrypoint == "scripts/safe_cleanup.py",
        "no_extra_cleanup_scripts": not cleanup_named_scripts,
        "arxiv_backup_only": arxiv_is_backup_only(),
        "arxiv_forbidden_cleanup_target": "/arxiv" in policy.get("forbidden_cleanup_targets", []),
        "destructive_tokens_allowlisted": not [hit for hit in destructive_hits if hit["path"] not in allowed_destructive_files],
    }
    for key, passed in gates.items():
        if not passed:
            errors.append(f"gate failed: {key}")

    tests = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_artifact_paths.py", "tests/test_safe_cleanup.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    gates["storage_and_cleanup_tests_pass"] = tests.returncode == 0
    if tests.returncode != 0:
        errors.append("storage/safe cleanup tests failed: " + tests.stdout[-800:] + tests.stderr[-800:])

    card = {
        "stage": 8653,
        "stage_name": STAGE_NAME,
        "passed": not errors,
        "authority": AUTHORITY_CLOSED,
        "model_execution_authorized": False,
        "decoder_ce_training_authorized": False,
        "focused_roots": focused_roots,
        "single_cleanup_entrypoint": cleanup_entrypoint,
        "safe_path_module": policy.get("safe_path_module"),
        "canonical_artifact_paths_module": policy.get("canonical_artifact_paths_module"),
        "arxiv_policy": policy.get("backup_locations", {}).get("/arxiv", {}),
        "gates": gates,
        "destructive_token_hits": destructive_hits,
        "allowed_destructive_files": sorted(allowed_destructive_files),
        "pytest_output": tests.stdout.strip(),
        "errors": errors,
        "next_best_step": "Use scripts/artifact_paths.py for all new summaries/artifacts/probes and keep scripts/safe_cleanup.py as the only cleanup entrypoint; no training or mining is authorized by this stage.",
    }
    summary_path = stage_summary_path(STAGE_NAME)
    summary_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "focused_storage_policy_audit.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
