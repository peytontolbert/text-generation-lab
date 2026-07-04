#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "runs" / "summaries" / "stage8651_no_destructive_training_preflight.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8651_no_destructive_training_preflight"
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
ALLOWED_DESTRUCTIVE_FILES = {
    "scripts/safe_cleanup.py",
    "scripts/safe_paths.py",
    "tests/test_safe_cleanup.py",
}
TOKENS = ["shutil." + "rmtree", ".un" + "link(", "os." + "remove", "rmdir" + "(", "rm " + "-rf"]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    hits = []
    for root_name in ["legacy_src", "scripts", "tests"]:
        for path in (ROOT / root_name).rglob("*.py"):
            rel = str(path.relative_to(ROOT))
            text = path.read_text(encoding="utf-8", errors="replace")
            for token in TOKENS:
                if token in text:
                    hits.append({"path": rel, "token": token})
                    if rel not in ALLOWED_DESTRUCTIVE_FILES and rel != "scripts/audit_stage8651_no_destructive_training_preflight.py":
                        errors.append(f"destructive token {token} found outside allowlist: {rel}")
    safe_tests = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_safe_cleanup.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    if safe_tests.returncode != 0:
        errors.append("safe cleanup tests failed: " + safe_tests.stdout[-500:] + safe_tests.stderr[-500:])
    trainer = (ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py").read_text(encoding="utf-8")
    safe_paths = (ROOT / "scripts/safe_paths.py").read_text(encoding="utf-8")
    gates = {
        "destructive_tokens_allowlisted": not [h for h in hits if h["path"] not in ALLOWED_DESTRUCTIVE_FILES and h["path"] != "scripts/audit_stage8651_no_destructive_training_preflight.py"],
        "safe_cleanup_tests_pass": safe_tests.returncode == 0,
        "trainer_uses_safe_cleanup_only": "safe_cleanup_checkpoints" in trainer and "shutil.rmtree" not in trainer and ".unlink(" not in trainer,
        "safe_paths_forbids_repo_root": "repo" in safe_paths and "refusing unsafe output_dir" in safe_paths,
        "safe_paths_requires_marker": "cleanup marker missing" in safe_paths and "cleanup marker does not contain run_id" in safe_paths,
        "safe_paths_refuses_symlink": "refusing symlink cleanup target" in safe_paths,
    }
    for key, value in gates.items():
        if not value:
            errors.append(f"gate failed: {key}")
    card = {
        "stage": 8651,
        "stage_name": "stage8651_no_destructive_training_preflight",
        "passed": not errors,
        "authority": AUTHORITY_CLOSED,
        "model_execution_authorized": False,
        "decoder_ce_training_authorized": False,
        "gates": gates,
        "destructive_token_hits": hits,
        "allowed_destructive_files": sorted(ALLOWED_DESTRUCTIVE_FILES),
        "safe_cleanup_test_output": safe_tests.stdout.strip(),
        "errors": errors,
        "next_best_step": "Prepare non-executing structured probe enablement card; execution remains closed until user/stage authorization.",
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "no_destructive_training_preflight_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
