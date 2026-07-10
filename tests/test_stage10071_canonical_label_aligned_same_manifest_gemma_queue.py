import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10071_canonical_label_aligned_same_manifest_gemma_queue.py"
QUEUE = ROOT / "runs/local/artifacts/stage10071_canonical_label_aligned_same_manifest_gemma_queue/canonical_label_aligned_same_manifest_gemma_queue.json"


def test_stage10071_gemma_queue_builds():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    payload = json.loads(QUEUE.read_text(encoding="utf-8"))
    assert payload["queue_entries"][0]["ready_for_gemma_when_authorized"] is True
    assert payload["queue_entries"][0]["same_surface_packet"]["heldout_compare_rows"] == 55
