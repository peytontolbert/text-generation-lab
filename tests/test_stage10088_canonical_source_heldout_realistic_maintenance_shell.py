import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10088_canonical_source_heldout_realistic_maintenance_shell.py"
PACKET = ROOT / "runs/local/artifacts/stage10088_canonical_source_heldout_realistic_maintenance_shell/canonical_source_heldout_realistic_maintenance_shell.json"
MANIFEST = ROOT / "runs/local/artifacts/stage10088_canonical_source_heldout_realistic_maintenance_shell/canonical_source_heldout_realistic_maintenance_shell_manifest.jsonl"


def test_stage10088_realistic_maintenance_shell_builds():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert packet["passed"] is True
    assert packet["metrics"]["rows"] == 95
    assert packet["metrics"]["heldout_rows"] == 55
    assert packet["metrics"]["rows_marked_l2"] == 95
    assert packet["claim_boundary"]["supports_shell_level_l2_prompt_design"] is True
    assert packet["claim_boundary"]["supports_final_expert_maintainer_claim"] is False
    sample = rows[0]["input_state"]
    assert sample["realism_level"] == "L2"
    assert sample["failure_text"]
    assert sample["trace_excerpt"]
    assert sample["relevant_snippets"]
    assert sample["candidate_paths"]
    assert sample["candidate_descriptions"]
