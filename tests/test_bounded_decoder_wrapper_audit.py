from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_stage8566_v27_bounded_decoder_ce_probe_wrapper_design.py"
AUDIT = ROOT / "scripts" / "audit_stage8567_v27_bounded_decoder_ce_probe_wrapper_design_audit.py"


def test_wrapper_design_and_audit_pass(tmp_path: Path) -> None:
    manifest = ROOT / "runs" / "local" / "artifacts" / "dummy_bounded_decoder_ce_manifest.jsonl"
    design = tmp_path / "design.json"
    audit = tmp_path / "audit.json"
    subprocess.run(
        [
            sys.executable,
            str(BUILD),
            "--repo-root",
            str(ROOT),
            "--manifest",
            str(manifest),
            "--output-dir",
            "runs/local/probes/test_stage8584",
            "--run-id",
            "test_stage8584",
            "--output",
            str(design),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    subprocess.run([sys.executable, str(AUDIT), str(design), "--output", str(audit)], check=True, text=True, capture_output=True)
    card = json.loads(audit.read_text())
    assert card["passed"] is True
    assert card["gates"]["trainer_help_exposes_required_flags"] is True
    assert card["gates"]["authority_closed"] is True
    payload = json.loads(design.read_text())
    assert "--contract-only" in payload["command"]


def test_wrapper_audit_rejects_output_outside_repo(tmp_path: Path) -> None:
    design = {
        "repo_root": str(ROOT),
        "trainer": str(ROOT / "legacy_src" / "scripts" / "train_agentkernel_lite_encdec.py"),
        "manifest": str(ROOT / "missing.jsonl"),
        "output_dir": str(tmp_path / "outside"),
        "command": ["python", "trainer.py", "--manifest", "x"],
        "constraints": {},
        "authority": {},
    }
    design_path = tmp_path / "bad_design.json"
    audit = tmp_path / "audit.json"
    design_path.write_text(json.dumps(design), encoding="utf-8")
    result = subprocess.run([sys.executable, str(AUDIT), str(design_path), "--output", str(audit)], text=True, capture_output=True)
    assert result.returncode == 1
    card = json.loads(audit.read_text())
    assert card["passed"] is False
    assert "output_dir is not under repo_root" in card["errors"]
