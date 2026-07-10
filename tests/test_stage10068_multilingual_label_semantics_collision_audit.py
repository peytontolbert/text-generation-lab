import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10068_multilingual_label_semantics_collision_audit.py"
AUDIT = ROOT / "runs/local/artifacts/stage10068_multilingual_label_semantics_collision_audit/multilingual_label_semantics_collision_audit.json"


def test_stage10068_collision_audit_builds():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["metrics"]["collision_label_count"] >= 1
    assert "python" in payload["metrics"]["per_language_label_map"]
