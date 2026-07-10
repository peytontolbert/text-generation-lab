#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import json
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9793
NAME = "stage9793_edit_localization_opaque_choice_gemma_comparison"
MANIFEST = ROOT / "runs/local/artifacts/stage9790_edit_localization_opaque_choice_surface/edit_localization_opaque_choice_surface.jsonl"
DEFAULT_MODEL_ROWS = ROOT / "runs/local/artifacts/stage9792_edit_localization_opaque_choice_exec/row_field_logits.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "edit_localization_opaque_choice_gemma_comparison.json"
ROWS_OUT = OUT_DIR / "edit_localization_opaque_choice_gemma_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MODEL_ID = "gemma3:12b"
SPLIT = "strict_eval"
FIELD = "edit_localization"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def _load_symbol(module_name: str, path: Path, symbol: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


build_prompt = _load_symbol(
    "stage9793_stage9748_runner",
    ROOT / "scripts/run_stage9748_standalone_gemma_queue_via_ollama.py",
    "build_prompt",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def label_vocab(rows: list[dict[str, Any]]) -> list[str]:
    labels = {
        str(((row.get("target") if isinstance(row.get("target"), dict) else {}).get("decoder_text") or ""))
        for row in rows
    }
    return sorted(label for label in labels if label)


def strict_rows_by_language(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if str(row.get("split") or "") != SPLIT:
            continue
        grouped[str(row.get("language_family") or "")].append(row)
    for lang in grouped:
        grouped[lang].sort(key=lambda row: str(row.get("row_id") or ""))
    return grouped


def model_language_slices(manifest_rows: list[dict[str, Any]], model_rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    row_index = {
        str(row.get("row_id") or ""): {
            "language_family": str(row.get("language_family") or ""),
            "split": str(row.get("split") or ""),
        }
        for row in manifest_rows
    }
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in model_rows:
        meta = row_index.get(str(row.get("row_id") or ""))
        if not meta or meta["split"] != SPLIT:
            continue
        lang = meta["language_family"]
        counts[lang][1] += 1
        counts[lang][0] += int(str(row.get("pred") or "") == str(row.get("target") or ""))
    return {
        lang: {
            "correct": counts[lang][0],
            "total": counts[lang][1],
            "strict_exact": (counts[lang][0] / counts[lang][1]) if counts[lang][1] else 0.0,
        }
        for lang in LANGS
    }


def ollama_generate(*, prompt: str) -> str:
    payload = json.dumps({
        "model": MODEL_ID,
        "prompt": prompt,
        "stream": False,
        "options": {"seed": 0, "temperature": 0.0},
    }).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response") or "").strip()


def build_audit(*, execute_gemma: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_rows = load_jsonl(MANIFEST)
    model_rows_path = Path(os.environ.get("STAGE9793_MODEL_ROWS", str(DEFAULT_MODEL_ROWS)))
    model_rows = load_jsonl(model_rows_path)
    labels = label_vocab(manifest_rows)
    grouped = strict_rows_by_language(manifest_rows)
    model_slices = model_language_slices(manifest_rows, model_rows)
    gemma_rows: list[dict[str, Any]] = []
    gemma_counts: Counter[str] = Counter()
    results: list[dict[str, Any]] = []
    wins_100m = 0
    wins_gemma = 0
    ties = 0
    for lang in LANGS:
        rows = grouped.get(lang, [])
        correct = 0
        for row in rows:
            prompt = build_prompt(row=row, field=FIELD, labels=labels)
            raw = "[dry-run]" if not execute_gemma else ollama_generate(prompt=prompt)
            pred = raw.splitlines()[0].strip() if raw else ""
            expected = str(((row.get("target") if isinstance(row.get("target"), dict) else {}).get("decoder_text") or ""))
            ok = bool(execute_gemma and pred == expected)
            if execute_gemma:
                correct += int(ok)
                gemma_counts[pred] += 1
            gemma_rows.append({
                "language": lang,
                "row_id": row.get("row_id"),
                "split": SPLIT,
                "expected_label": expected,
                "predicted_label": pred,
                "correct": ok,
                "raw_output": raw,
                "label_vocab_scope": "full_packet",
                "decoder_seed": 0,
                "decoder_temperature": 0.0,
                "prompt": prompt,
            })
        gemma_exact = (correct / len(rows)) if execute_gemma and rows else None
        model_exact = float(model_slices[lang]["strict_exact"])
        verdict = "tie"
        if gemma_exact is not None:
            if model_exact > gemma_exact:
                verdict = "100m_better"
                wins_100m += 1
            elif model_exact < gemma_exact:
                verdict = "gemma_better"
                wins_gemma += 1
            else:
                ties += 1
        results.append({
            "language": lang,
            "rows": len(rows),
            "gemma_strict_exact": gemma_exact,
            "model_strict_exact_100m": model_exact,
            "model_correct_100m": int(model_slices[lang]["correct"]),
            "verdict": verdict,
            "label_vocab_scope": "full_packet",
        })
    audit = {
        "passed": True,
        "stage": STAGE,
        "stage_name": NAME,
        "model_id": MODEL_ID,
        "surface_manifest": str(MANIFEST.relative_to(ROOT)),
        "model_rows": str(model_rows_path.relative_to(ROOT) if model_rows_path.is_absolute() and model_rows_path.is_relative_to(ROOT) else model_rows_path),
        "split": SPLIT,
        "field": FIELD,
        "decoder_seed": 0,
        "decoder_temperature": 0.0,
        "labels": labels,
        "gemma_executed": execute_gemma,
        "results": results,
        "wins_100m": wins_100m,
        "wins_gemma": wins_gemma,
        "ties": ties,
        "predicted_label_counts": dict(sorted(gemma_counts.items())),
        "authority": dict(AUTHORITY_CLOSED),
    }
    return audit, gemma_rows


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    execute_gemma = "--dry-run" not in sys.argv[1:]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    audit, gemma_rows = build_audit(execute_gemma=execute_gemma)
    ROWS_OUT.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in gemma_rows), encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Treat the opaque-choice surface as the current honest edit-localization comparator, "
        "then decide whether to retrain on opaque labels or pivot to stronger causal evidence before claiming a 100M win."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": True,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "wins_100m": audit["wins_100m"],
            "wins_gemma": audit["wins_gemma"],
            "ties": audit["ties"],
            "gemma_executed": execute_gemma,
        },
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "rows": str(ROWS_OUT.relative_to(ROOT)),
        },
        "decision": (
            "Compared deterministic Gemma against the Stage9790 opaque-choice edit-localization surface "
            "and paired it with the Stage9792 100M strict-eval rows."
        ),
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": True,
        "gemma_executed": execute_gemma,
        "wins_100m": audit["wins_100m"],
        "wins_gemma": audit["wins_gemma"],
        "ties": audit["ties"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
