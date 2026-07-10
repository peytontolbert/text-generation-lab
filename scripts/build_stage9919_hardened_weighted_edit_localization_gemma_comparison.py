#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9919
NAME = "stage9919_hardened_weighted_edit_localization_gemma_comparison"
MANIFEST = ROOT / "runs/local/artifacts/stage9917_hardened_weighted_structured_execution_review/tiny_structured_manifests/edit_localization_tiny.jsonl"
ROWS_100M = ROOT / "runs/local/artifacts/stage9917_hardened_weighted_structured_execution_review/surface_runs/edit_localization/row_field_logits.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ROWS_OUT = OUT_DIR / "hardened_weighted_edit_localization_gemma_rows.jsonl"
AUDIT = OUT_DIR / "hardened_weighted_edit_localization_gemma_comparison.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "HARDENED_WEIGHTED_EDIT_LOCALIZATION_GEMMA_COMPARISON_STAGE9919.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MODEL_ID = "gemma3:12b"
FIELD = "edit_localization"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
SPLITS = ("eval", "strict_eval")


def _load_symbol(module_name: str, path: Path, symbol: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


_row_text = _load_symbol("stage9919_training_data", ROOT / "legacy_src/agentkernel_lite/training_data.py", "_row_text")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_prompt(row: dict[str, Any]) -> str:
    return "\n".join([
        "You are evaluating a structured software-maintenance state.",
        "Return only the exact option label for `edit_localization`.",
        "Do not explain your answer. Output one option label only.",
        "",
        "Structured input surface:",
        _row_text(row),
    ])


def expected_label(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    return str(target.get("decoder_text") or clean.get("edit_localization") or target.get("edit_localization") or "")


def rows_by_bucket(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        split = str(row.get("split") or "")
        lang = str(row.get("language_family") or "")
        if split in SPLITS and lang in LANGS:
            grouped[(lang, split)].append(row)
    for key in grouped:
        grouped[key].sort(key=lambda row: str(row.get("row_id") or ""))
    return grouped


def model_bucket_metrics(model_rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, float | int]]:
    counts: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for row in model_rows:
        lang = str((row.get("cell_key") or "").split("::")[0] if "::" in str(row.get("cell_key") or "") else "")
        split = str(row.get("split") or "")
        if split not in SPLITS or lang not in LANGS:
            continue
        counts[(lang, split)][1] += 1
        counts[(lang, split)][0] += int(str(row.get("pred") or "") == str(row.get("target") or ""))
    return {
        key: {"correct": value[0], "total": value[1], "exact": (value[0] / value[1]) if value[1] else 0.0}
        for key, value in counts.items()
    }


def ollama_generate(prompt: str) -> str:
    payload = json.dumps({"model": MODEL_ID, "prompt": prompt, "stream": False, "options": {"seed": 0, "temperature": 0.0}}).encode("utf-8")
    request = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response") or "").strip()


def build_audit(*, execute_gemma: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_rows = load_jsonl(MANIFEST)
    model_rows = load_jsonl(ROWS_100M)
    grouped = rows_by_bucket(manifest_rows)
    model_metrics = model_bucket_metrics(model_rows)
    gemma_rows: list[dict[str, Any]] = []
    comparisons: dict[str, dict[str, Any]] = {}
    wins_100m = wins_gemma = ties = 0
    for lang in LANGS:
        for split in SPLITS:
            rows = grouped.get((lang, split), [])
            correct = 0
            for row in rows:
                prompt = build_prompt(row)
                raw = "[dry-run]" if not execute_gemma else ollama_generate(prompt)
                pred = raw.splitlines()[0].strip() if raw else ""
                expected = expected_label(row)
                ok = bool(execute_gemma and pred == expected)
                if execute_gemma:
                    correct += int(ok)
                gemma_rows.append({
                    "language": lang,
                    "split": split,
                    "row_id": row.get("row_id"),
                    "expected_label": expected,
                    "predicted_label": pred,
                    "correct": ok,
                    "raw_output": raw,
                    "decoder_seed": 0,
                    "decoder_temperature": 0.0,
                    "prompt": prompt,
                })
            gemma_exact = (correct / len(rows)) if execute_gemma and rows else None
            hundred = model_metrics.get((lang, split), {"exact": 0.0, "correct": 0, "total": 0})
            verdict = "tie"
            if gemma_exact is not None:
                if float(hundred["exact"]) > gemma_exact:
                    verdict = "100m_better"
                    wins_100m += 1
                elif float(hundred["exact"]) < gemma_exact:
                    verdict = "gemma_better"
                    wins_gemma += 1
                else:
                    ties += 1
            comparisons[f"{lang}:{split}"] = {
                "hundred_m_exact": float(hundred["exact"]),
                "hundred_m_correct": int(hundred["correct"]),
                "hundred_m_total": int(hundred["total"]),
                "gemma_exact": gemma_exact,
                "rows": len(rows),
                "verdict": verdict,
            }
    audit = {
        "passed": True,
        "stage": STAGE,
        "stage_name": NAME,
        "model_id": MODEL_ID,
        "surface_manifest": str(MANIFEST.relative_to(ROOT)),
        "model_rows": str(ROWS_100M.relative_to(ROOT)),
        "field": FIELD,
        "splits": list(SPLITS),
        "gemma_executed": execute_gemma,
        "comparisons": comparisons,
        "wins_100m": wins_100m,
        "wins_gemma": wins_gemma,
        "ties": ties,
        "authority": dict(AUTHORITY_CLOSED),
    }
    return audit, gemma_rows


def main() -> None:
    execute_gemma = "--dry-run" not in sys.argv[1:]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit, gemma_rows = build_audit(execute_gemma=execute_gemma)
    write_jsonl(ROWS_OUT, gemma_rows)
    write_json(AUDIT, audit)
    next_step = "Use this integrated weighted same-surface comparison to decide whether the hardened v2.7 mix now beats Gemma across the multilingual edit-localization packet, then attach updated review evidence for any surviving winner cells."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": True,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "wins_100m": audit["wins_100m"], "wins_gemma": audit["wins_gemma"], "ties": audit["ties"], "gemma_executed": execute_gemma},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "rows": str(ROWS_OUT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Compared local Gemma against the weighted hardened integrated edit-localization packet using Stage9917 row-level 100M outputs and the same no-label-list opaque-choice prompt surface.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9919 Hardened Weighted Edit Localization Gemma Comparison",
        "",
        f"Passed: `{summary['passed']}`",
        f"100M wins: `{audit['wins_100m']}`",
        f"Gemma wins: `{audit['wins_gemma']}`",
        f"Ties: `{audit['ties']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": True, "wins_100m": audit["wins_100m"], "wins_gemma": audit["wins_gemma"], "ties": audit["ties"], "gemma_executed": execute_gemma}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
