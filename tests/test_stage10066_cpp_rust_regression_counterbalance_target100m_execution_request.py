import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10066_cpp_rust_regression_counterbalance_target100m_execution_request.py"
REQUEST = ROOT / "runs/local/artifacts/stage10066_cpp_rust_regression_counterbalance_target100m_execution_request/cpp_rust_regression_counterbalance_target100m_execution_request.json"


def test_stage10066_execution_request_builds():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    payload = json.loads(REQUEST.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["metrics"]["rows"] == 151
    assert payload["metrics"]["stage10065_train_rows"] == 9
    assert payload["metrics"]["language_counts"]["c_cpp"] == 45
    assert payload["metrics"]["language_counts"]["rust"] == 19
    command = payload["surface_requests"][0]["command"]
    assert any("stage10065_cpp_rust_regression_counterbalance_successor_packet/cpp_rust_regression_counterbalance_manifest.jsonl" in part for part in command)
