#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9849
NAME = "stage9849_counterfactual_curriculum_gemma_comparison"
MANIFEST = ROOT / "runs/local/artifacts/stage9847_counterfactual_curriculum_manifest/counterfactual_curriculum_manifest.jsonl"
ROWS_100M = ROOT / "runs/local/artifacts/stage9848_direct_counterfactual_curriculum_exec/row_field_logits.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ROWS_OUT = OUT_DIR / "counterfactual_curriculum_gemma_rows.jsonl"
AUDIT = OUT_DIR / "counterfactual_curriculum_gemma_comparison.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COUNTERFACTUAL_CURRICULUM_GEMMA_COMPARISON_STAGE9849.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MODEL_ID = "gemma3:12b"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
SPLITS = ["eval", "strict_eval"]
LABELS = ["A", "B", "C", "D", "E"]


def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


_row_text = _load_symbol("stage9849_training_data", ROOT / "legacy_src/agentkernel_lite/training_data.py", "_row_text")


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
        "Return only the exact label for `edit_localization`.",
        f"Valid labels: {', '.join(LABELS)}",
        "Do not explain your answer. Output one label only.",
        "",
        "Structured input surface:",
        _row_text(row),
    ])


def expected_label(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    return str(clean.get("edit_localization") or target.get("edit_localization") or target.get("decoder_text") or "")


def ollama_generate(prompt: str) -> str:
    payload = json.dumps({"model": MODEL_ID, "prompt": prompt, "stream": False, "options": {"seed": 0, "temperature": 0.0}}).encode("utf-8")
    request = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response") or "").strip()


def run_gemma_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        prompt = build_prompt(row)
        raw = ollama_generate(prompt)
        pred = raw.splitlines()[0].strip() if raw else ""
        expected = expected_label(row)
        out.append({"row_id": row.get("row_id"), "language_family": row.get("language_family"), "split": row.get("split"), "counterfactual_role": row.get("counterfactual_role"), "expected_label": expected, "predicted_label": pred, "raw_output": raw, "correct": pred == expected, "prompt": prompt})
    return out


def normalize_100m_rows() -> list[dict[str, Any]]:
    rows = load_jsonl(ROWS_100M)
    out = []
    for row in rows:
        lang = str(row.get("cell_key") or "").split("::")[0]
        out.append({"language_family": lang, "split": row.get("split"), "correct": bool(row.get("correct"))})
    return out


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_bucket = {}
    macro_by_split = {}
    for split in SPLITS:
        vals = []
        for lang in LANGS:
            bucket = [row for row in rows if row.get("split") == split and row.get("language_family") == lang]
            correct = sum(1 for row in bucket if row.get("correct"))
            exact = (correct / len(bucket)) if bucket else 0.0
            by_bucket[f"{lang}:{split}"] = {"rows": len(bucket), "correct": correct, "exact": exact}
            vals.append(exact)
        macro_by_split[split] = sum(vals) / len(vals) if vals else 0.0
    return {"by_bucket": by_bucket, "macro_by_split": macro_by_split}


def build_audit(hundred_m_rows: list[dict[str, Any]], gemma_rows: list[dict[str, Any]]) -> dict[str, Any]:
    hundred = summarize(hundred_m_rows)
    gemma = summarize(gemma_rows)
    comparisons = {}
    wins_100m = wins_gemma = ties = 0
    for split in SPLITS:
        for lang in LANGS:
            key = f"{lang}:{split}"
            a = hundred["by_bucket"][key]["exact"]
            b = gemma["by_bucket"][key]["exact"]
            verdict = "tie"
            if a > b:
                verdict = "100m_win"
                wins_100m += 1
            elif b > a:
                verdict = "gemma_win"
                wins_gemma += 1
            else:
                ties += 1
            comparisons[key] = {"hundred_m_exact": a, "gemma_exact": b, "verdict": verdict}
    return {"passed": True, "hundred_m": hundred, "gemma": gemma, "comparisons": comparisons, "wins_100m": wins_100m, "wins_gemma": wins_gemma, "ties": ties, "macro_delta_by_split": {split: hundred["macro_by_split"][split] - gemma["macro_by_split"][split] for split in SPLITS}, "authority": dict(AUTHORITY_CLOSED)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    manifest_rows = [row for row in load_jsonl(MANIFEST) if str(row.get("split") or "") in SPLITS]
    gemma_rows = run_gemma_rows(manifest_rows)
    hundred_rows = normalize_100m_rows()
    write_jsonl(ROWS_OUT, gemma_rows)
    audit = build_audit(hundred_rows, gemma_rows)
    write_json(AUDIT, audit)
    next_step = "If this curriculum improves the harder multilingual comparison, fold it back into the anti-cheat review packet and consider scaling the same objective into the main v2.7 training path."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "wins_100m": audit["wins_100m"], "wins_gemma": audit["wins_gemma"], "ties": audit["ties"], "macro_delta_eval": audit["macro_delta_by_split"]["eval"], "macro_delta_strict_eval": audit["macro_delta_by_split"]["strict_eval"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "rows": str(ROWS_OUT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Ran local Gemma on the heldout counterfactual curriculum evaluation packet and compared it against the curriculum-trained 100M row-level outputs on the same harder multilingual surface.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9849 Counterfactual Curriculum Gemma Comparison",
        "",
        f"Passed: `{summary['passed']}`",
        f"100M wins: `{audit['wins_100m']}`",
        f"Gemma wins: `{audit['wins_gemma']}`",
        f"Ties: `{audit['ties']}`",
        f"Eval macro delta (100M-Gemma): `{audit['macro_delta_by_split']['eval']}`",
        f"Strict macro delta (100M-Gemma): `{audit['macro_delta_by_split']['strict_eval']}`",
        "",
        "This stage measures whether explicit curriculum training on missing-evidence and contradictory-evidence behaviors creates a stronger heldout multilingual comparison against Gemma.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "wins_100m": audit["wins_100m"], "wins_gemma": audit["wins_gemma"], "ties": audit["ties"], "macro_delta_by_split": audit["macro_delta_by_split"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
