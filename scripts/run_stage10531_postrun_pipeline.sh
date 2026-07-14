#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXECUTION_RESULT="$ROOT/runs/local/artifacts/stage10531_long_target_cap_corrected_probe/bounded_decoder_probe/execution_result.json"
RUNTIME_BUNDLE="$ROOT/runs/local/artifacts/stage10531_long_target_cap_corrected_probe/runtime_model/runtime_model_bundle.json"
LOG_DIR="$ROOT/runs/local/artifacts/stage10531_long_target_cap_corrected_probe/postrun_pipeline"
LOG_PATH="$LOG_DIR/postrun_pipeline.log"

mkdir -p "$LOG_DIR"

{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] waiting for stage10531 runtime artifacts"
  until [[ -f "$EXECUTION_RESULT" && -f "$RUNTIME_BUNDLE" ]]; do
    sleep 30
  done

  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] runtime artifacts detected"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] running stage10532 comparison"
  conda run -n trellis python "$ROOT/scripts/run_stage10532_long_target_cap_corrected_same_manifest_comparison.py"

  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] running stage10533 canary audit"
  conda run -n trellis python "$ROOT/scripts/build_stage10533_long_target_cap_corrected_canary_audit.py"

  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] postrun pipeline complete"
} >>"$LOG_PATH" 2>&1
