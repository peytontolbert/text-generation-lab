import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10069_canonical_label_aligned_multilingual_successor_packet.py"
PACKET = ROOT / "runs/local/artifacts/stage10069_canonical_label_aligned_multilingual_successor_packet/canonical_label_aligned_multilingual_successor_packet.json"


def test_stage10069_aligned_packet_builds():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    payload = json.loads(PACKET.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["metrics"]["rows"] == 142
    assert payload["metrics"]["per_language_label_map"]["web_js_ts_html"]["A"] == "TARGET_TEST"
    assert payload["metrics"]["per_language_label_map"]["c_cpp"]["B"] == "TARGET_ENTRYPOINT"
