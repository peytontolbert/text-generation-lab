#!/usr/bin/env python3
"""Run a bounded Ollama software repair baseline on Stage1104 targets."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {name}: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _ollama_generate(*, model: str, prompt: str, host: str, timeout: float, num_predict: int) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "num_predict": int(num_predict)},
    }
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return str(data.get("response", ""))


def _clean_code(text: str) -> str:
    text = str(text).strip()
    fence = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    match = re.search(r"def\s+[A-Za-z_][A-Za-z0-9_]*\([^)]*\):.*", text, flags=re.DOTALL)
    if match:
        text = match.group(0).strip()
    return text + ("\n" if text and not text.endswith("\n") else "")


def _prompt(target: dict[str, Any]) -> str:
    return "\n".join([
        "/no_think",
        "Repair the Python function below.",
        "Return only the complete corrected Python function.",
        "Do not explain.",
        "",
        str(target["prompt"]),
    ])


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("runs/local/artifacts/stage1104_diverse_100m_training_package/manifest.json"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--split", choices=["eval", "hidden"], default="eval")
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    parser.add_argument("--max-rows", type=int, default=32)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--num-predict", type=int, default=192)
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1106_ollama_software_repair_baseline"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1106_ollama_software_repair_baseline_summary.json"))
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    targets = _iter_jsonl(Path(manifest[f"{args.split}_targets_path"]))[: int(args.max_rows)]
    predictions: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    start = time.time()
    for index, target in enumerate(targets):
        prompt = _prompt(target)
        try:
            raw = _ollama_generate(model=str(args.model), prompt=prompt, host=str(args.host), timeout=float(args.timeout), num_predict=int(args.num_predict))
            code = _clean_code(raw)
        except Exception as exc:  # noqa: BLE001
            raw = f"ERROR: {type(exc).__name__}: {exc}"
            code = ""
        predictions.append({"task_id": target["task_id"], "direct_code_output": code})
        raw_rows.append({"row_number": index, "task_id": target["task_id"], "raw_response": raw, "clean_code": code})

    args.output_dir.mkdir(parents=True, exist_ok=True)
    pred_path = args.output_dir / f"{args.split}_{args.model.replace(':', '_')}_predictions.jsonl"
    raw_path = args.output_dir / f"{args.split}_{args.model.replace(':', '_')}_raw.jsonl"
    _write_jsonl(pred_path, predictions)
    _write_jsonl(raw_path, raw_rows)

    stage1097 = _load_module("stage1097_score", args.repo_root / "scripts/score_stage1097_100m_software_target_predictions.py")
    stage1086 = _load_module("stage1086_score", args.repo_root / "scripts/score_stage1086_software_kbpp_predictions.py")
    pred_map = stage1097._load_predictions(pred_path)
    score_summary, score_rows = stage1097._score(stage1086, targets, pred_map)
    scores_path = args.output_dir / f"{args.split}_{args.model.replace(':', '_')}_scores.jsonl"
    _write_jsonl(scores_path, score_rows)
    summary = {
        "artifact_kind": "stage1106_ollama_software_repair_baseline",
        "status": "completed_bounded_ollama_software_repair_baseline",
        "model": str(args.model),
        "manifest": str(args.manifest),
        "split": str(args.split),
        "rows": len(targets),
        "predictions_jsonl": str(pred_path),
        "raw_jsonl": str(raw_path),
        "scores_jsonl": str(scores_path),
        "elapsed_seconds": time.time() - start,
        **score_summary,
        "decision": "Bounded local Ollama software repair baseline. This is a smoke baseline, not a full model comparison unless rows cover the full split.",
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
