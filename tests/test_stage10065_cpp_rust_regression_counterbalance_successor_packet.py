import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10065_cpp_rust_regression_counterbalance_successor_packet.py"
PACKET = ROOT / "runs/local/artifacts/stage10065_cpp_rust_regression_counterbalance_successor_packet/cpp_rust_regression_counterbalance_successor_packet.json"


def test_stage10065_counterbalance_packet_builds():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    payload = json.loads(PACKET.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["metrics"]["fresh_source_rows"] == 9
    assert payload["metrics"]["selected_counts"] == {
        "c_cpp:A": 1,
        "c_cpp:B": 3,
        "c_cpp:C": 1,
        "c_cpp:E": 2,
        "rust:B": 1,
        "rust:C": 1,
    }
