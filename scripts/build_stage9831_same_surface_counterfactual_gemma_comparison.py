#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import time
import urllib.request
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9831
NAME = "stage9831_same_surface_counterfactual_gemma_comparison"
MANIFEST = ROOT / "runs/local/artifacts/stage9829_current_winner_counterfactual_execution_manifest/current_winner_counterfactual_execution_manifest.jsonl"
STAGE9830_ROWS = ROOT / "runs/local/artifacts/stage9830_current_winner_counterfactual_exec/row_field_logits.jsonl"
STAGE9827_PACKET_MANIFEST = ROOT / "runs/local/artifacts/stage9827_current_multilingual_winner_review_packets/current_multilingual_winner_review_packet_manifest.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ROWS_OUT = OUT_DIR / "same_surface_counterfactual_gemma_rows.jsonl"
AUDIT = OUT_DIR / "same_surface_counterfactual_gemma_comparison.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SAME_SURFACE_COUNTERFACTUAL_GEMMA_COMPARISON_STAGE9831.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MODEL_ID = "gemma3:12b"
LABELS = ["A", "B", "C", "D", "E"]
COMPARE_SPLITS = ["eval", "strict_eval"]
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


_row_text = _load_symbol(
    "stage9831_training_data",
    ROOT / "legacy_src/agentkernel_lite/training_data.py",
    "_row_text",
)


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
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
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


def prompt_surface_hash(rows: list[dict[str, Any]]) -> str:
    payload = [
        {
            "row_id": row.get("row_id"),
            "split": row.get("split"),
            "language_family": row.get("language_family"),
            "encoder_text": _row_text(row),
        }
        for row in sorted(rows, key=lambda row: str(row.get("row_id") or ""))
    ]
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def build_prompt(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            "You are evaluating a structured software-maintenance state.",
            "Return only the exact label for `edit_localization`.",
            f"Valid labels: {', '.join(LABELS)}",
            "Do not explain your answer. Output one label only.",
            "",
            "Structured input surface:",
            _row_text(row),
        ]
    )


def expected_label(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    return str(clean.get("edit_localization") or target.get("edit_localization") or target.get("decoder_text") or "")


def ollama_generate(prompt: str) -> str:
    payload = json.dumps(
        {
            "model": MODEL_ID,
            "prompt": prompt,
            "stream": False,
            "options": {"seed": 0, "temperature": 0.0},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response") or "").strip()


def run_gemma_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for row in rows:
        prompt = build_prompt(row)
        raw = ollama_generate(prompt)
        pred = raw.splitlines()[0].strip() if raw else ""
        expected = expected_label(row)
        outputs.append(
            {
                "row_id": row.get("row_id"),
                "language_family": row.get("language_family"),
                "split": row.get("split"),
                "expected_label": expected,
                "predicted_label": pred,
                "raw_output": raw,
                "correct": pred == expected,
                "prompt": prompt,
            }
        )
    return outputs


def summarize_accuracy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_bucket: dict[str, dict[str, Any]] = {}
    macro_by_split: dict[str, float] = {}
    for split in COMPARE_SPLITS:
        split_scores = []
        for lang in LANGS:
            bucket = [row for row in rows if row.get("split") == split and row.get("language_family") == lang]
            correct = sum(1 for row in bucket if row.get("correct"))
            exact = (correct / len(bucket)) if bucket else 0.0
            by_bucket[f"{lang}:{split}"] = {"rows": len(bucket), "correct": correct, "exact": exact}
            split_scores.append(exact)
        macro_by_split[split] = (sum(split_scores) / len(split_scores)) if split_scores else 0.0
    return {"by_bucket": by_bucket, "macro_by_split": macro_by_split}


def load_stage9830_rows() -> list[dict[str, Any]]:
    rows = load_jsonl(STAGE9830_ROWS)
    return [
        {
            "row_id": row.get("row_id"),
            "language_family": str(row.get("cell_key") or "").split("::")[0],
            "split": row.get("split"),
            "correct": bool(row.get("correct")),
        }
        for row in rows
        if str(row.get("split") or "") in COMPARE_SPLITS
    ]


def risk_flags() -> dict[str, Any]:
    manifest = load_json(STAGE9827_PACKET_MANIFEST)
    rows = manifest.get("rows") if isinstance(manifest.get("rows"), list) else []
    flagged = []
    for row in rows:
        paths = row.get("review_packet_paths") if isinstance(row.get("review_packet_paths"), dict) else {}
        anti_path = ROOT / str(paths.get("anti_cheat_recommendation_draft") or "")
        anti = load_json(anti_path) if anti_path.exists() else {}
        judgments = anti.get("recommended_challenge_judgments") if isinstance(anti.get("recommended_challenge_judgments"), list) else []
        failed = [
            str(j.get("challenge_family") or "")
            for j in judgments
            if isinstance(j, dict) and j.get("recommended_pass") is False
        ]
        if failed:
            flagged.append({"cell_key": row.get("cell_key"), "failed_challenge_families": failed})
    return {"cells_with_shortcut_risk": len(flagged), "flagged_cells": flagged}


def build_audit(gemma_rows: list[dict[str, Any]], hundred_m_rows: list[dict[str, Any]], manifest_rows: list[dict[str, Any]]) -> dict[str, Any]:
    gemma_summary = summarize_accuracy(gemma_rows)
    hundred_m_summary = summarize_accuracy(hundred_m_rows)
    same_surface_hash = prompt_surface_hash([row for row in manifest_rows if str(row.get("split") or "") in COMPARE_SPLITS])
    comparisons: dict[str, Any] = {}
    wins_100m = 0
    wins_gemma = 0
    ties = 0
    for split in COMPARE_SPLITS:
        for lang in LANGS:
            key = f"{lang}:{split}"
            hundred_m_exact = hundred_m_summary["by_bucket"][key]["exact"]
            gemma_exact = gemma_summary["by_bucket"][key]["exact"]
            verdict = "tie"
            if hundred_m_exact > gemma_exact:
                verdict = "100m_win"
                wins_100m += 1
            elif gemma_exact > hundred_m_exact:
                verdict = "gemma_win"
                wins_gemma += 1
            else:
                ties += 1
            comparisons[key] = {
                "hundred_m_exact": hundred_m_exact,
                "gemma_exact": gemma_exact,
                "verdict": verdict,
            }
    macro_delta_by_split = {
        split: hundred_m_summary["macro_by_split"][split] - gemma_summary["macro_by_split"][split]
        for split in COMPARE_SPLITS
    }
    return {
        "passed": True,
        "rows_compared": len(gemma_rows),
        "same_surface_hash": same_surface_hash,
        "model_id": MODEL_ID,
        "splits": COMPARE_SPLITS,
        "language_families": LANGS,
        "hundred_m": hundred_m_summary,
        "gemma": gemma_summary,
        "comparisons": comparisons,
        "wins_100m": wins_100m,
        "wins_gemma": wins_gemma,
        "ties": ties,
        "macro_delta_by_split": macro_delta_by_split,
        "eval_hacking_risk": risk_flags(),
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    manifest_rows = [row for row in load_jsonl(MANIFEST) if str(row.get("split") or "") in COMPARE_SPLITS]
    gemma_rows = run_gemma_rows(manifest_rows)
    hundred_m_rows = load_stage9830_rows()
    write_jsonl(ROWS_OUT, gemma_rows)
    audit = build_audit(gemma_rows, hundred_m_rows, manifest_rows)
    write_json(AUDIT, audit)
    next_step = "Use this same-surface counterfactual comparison to decide whether the multilingual winner is actually robust enough to headline; if Gemma holds up on mixed-replay, improve the training/data surface before making stronger public win claims."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "rows_compared": audit["rows_compared"],
            "wins_100m": audit["wins_100m"],
            "wins_gemma": audit["wins_gemma"],
            "ties": audit["ties"],
            "macro_delta_eval": audit["macro_delta_by_split"]["eval"],
            "macro_delta_strict_eval": audit["macro_delta_by_split"]["strict_eval"],
            "cells_with_shortcut_risk": audit["eval_hacking_risk"]["cells_with_shortcut_risk"],
        },
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "rows": str(ROWS_OUT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Ran local Gemma-12B on the exact Stage9829 eval and strict-eval surface and compared it directly against the Stage9830 100M outputs, while carrying forward the known anti-cheat risk flags from the current winner review packets.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9831 Same-Surface Counterfactual Gemma Comparison",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows compared: `{audit['rows_compared']}`",
                f"100M wins: `{audit['wins_100m']}`",
                f"Gemma wins: `{audit['wins_gemma']}`",
                f"Ties: `{audit['ties']}`",
                f"Eval macro delta (100M-Gemma): `{audit['macro_delta_by_split']['eval']}`",
                f"Strict macro delta (100M-Gemma): `{audit['macro_delta_by_split']['strict_eval']}`",
                f"Shortcut-risk winning cells: `{audit['eval_hacking_risk']['cells_with_shortcut_risk']}`",
                "",
                "This stage compares Gemma-12B and the current 100M execution on the exact same counterfactual surface rather than mixing old frontier rows with newer robustness probes.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ) + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": audit["passed"],
                "wins_100m": audit["wins_100m"],
                "wins_gemma": audit["wins_gemma"],
                "ties": audit["ties"],
                "macro_delta_by_split": audit["macro_delta_by_split"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
