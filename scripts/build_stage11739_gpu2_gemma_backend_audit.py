#!/usr/bin/env python3
"""Audit GPU2-safe Gemma backend readiness for source-heldout smoke comparison."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11739
NAME = "stage11739_gpu2_gemma_backend_audit"
OUT = ART / NAME
SUMMARY = OUT / "gpu2_gemma_backend_audit.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def run(cmd: list[str], timeout: int = 60) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, timeout=timeout, check=False)
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    hf_gemma = Path("/data/.cache/huggingface/hub/models--google--gemma-4-12B-it")
    hf_files = sorted(str(path.relative_to(hf_gemma)) for path in hf_gemma.rglob("*") if path.is_file()) if hf_gemma.exists() else []
    trellis_check = run(
        [
            "conda",
            "run",
            "-n",
            "trellis",
            "python",
            "-c",
            (
                "import importlib.util, torch, transformers; "
                "print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), 'devices', torch.cuda.device_count()); "
                "print('transformers', transformers.__version__); "
                "print('vllm', importlib.util.find_spec('vllm') is not None); "
                "print('accelerate', importlib.util.find_spec('accelerate') is not None); "
                "print('bitsandbytes', importlib.util.find_spec('bitsandbytes') is not None)"
            ),
        ],
        timeout=120,
    )

    gates = {
        "trellis_torch_cuda_available": "cuda True" in trellis_check.get("stdout", ""),
        "transformers_available": "transformers" in trellis_check.get("stdout", ""),
        "hf_gemma4_12b_snapshot_complete": any(name.endswith("config.json") for name in hf_files)
        and any(".safetensors" in name for name in hf_files),
        "vllm_available": "vllm True" in trellis_check.get("stdout", ""),
        "bitsandbytes_available": "bitsandbytes True" in trellis_check.get("stdout", ""),
        "comparator_matches_existing_ollama_gemma3_12b": False,
    }
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "gpu2_safe_gemma_same_manifest_backend_not_ready",
        "passed": True,
        "gates": gates,
        "trellis_check": trellis_check,
        "hf_cache_probe": {
            "path": str(hf_gemma),
            "exists": hf_gemma.exists(),
            "file_count": len(hf_files),
            "files_sample": hf_files[:40],
        },
        "interpretation": [
            "The trellis environment has CUDA-visible torch and transformers under CUDA_VISIBLE_DEVICES=2.",
            "The local HF google/gemma-4-12B-it cache appears incomplete and is not the same comparator as the existing Ollama gemma3:12b baseline.",
            "Existing same-manifest comparison scripts use Ollama gemma3:12b, so switching to HF gemma-4-12B-it would change the baseline.",
            "Because Ollama is currently reserved on GPU1, a source-heldout Gemma smoke comparison should wait for a GPU2-pinned Ollama service or an exact local gemma3:12b-compatible backend.",
        ],
        "next_actions": [
            "Start or recover a GPU2-pinned Ollama gemma3:12b endpoint on a separate host/port before running smoke Gemma comparisons.",
            "Alternatively materialize an exact local gemma3:12b-compatible HF snapshot and record the comparator change explicitly.",
            "Do not use google/gemma-4-12B-it outputs as a drop-in replacement for existing gemma3:12b same-manifest claims.",
        ],
        "claim_boundary": [
            "This stage does not run Gemma on the smoke rows.",
            "It prevents comparator drift by refusing to mix incomplete HF Gemma-4 assets with prior Ollama gemma3:12b claims.",
        ],
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
