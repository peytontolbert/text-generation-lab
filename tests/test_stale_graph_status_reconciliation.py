import json
import subprocess
import sys
from pathlib import Path


def test_stage8869_reconciliation_script_compiles():
    subprocess.run([sys.executable, "-m", "py_compile", "scripts/build_stage8869_stale_graph_status_reconciliation.py"], check=True)


def test_stage8869_output_has_no_authority_if_present():
    p = Path("runs/summaries/stage8869_stale_graph_status_reconciliation.json")
    if not p.exists():
        return
    data = json.loads(p.read_text())
    assert data["passed"] is True
    assert data["metrics"]["stale_nodes_patched"] == data["metrics"]["stale_nodes_seen"]
    assert data["metrics"]["training_authorized"] is False
    assert data["metrics"]["decoder_ce_authorized"] is False
    assert data["metrics"]["commit_mining_authorized"] is False
