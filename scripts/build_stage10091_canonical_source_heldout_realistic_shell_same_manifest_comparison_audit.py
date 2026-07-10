#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10091
NAME = "stage10091_canonical_source_heldout_realistic_shell_same_manifest_comparison_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "canonical_source_heldout_realistic_shell_same_manifest_comparison_audit.json"
ROWS = OUT_DIR / "canonical_source_heldout_realistic_shell_same_manifest_comparison_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_SOURCE_HELDOUT_REALISTIC_SHELL_SAME_MANIFEST_COMPARISON_AUDIT_STAGE10091.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage10088_canonical_source_heldout_realistic_maintenance_shell/canonical_source_heldout_realistic_maintenance_shell_manifest.jsonl"
HUNDRED_M = ROOT / "runs/local/artifacts/stage10089_canonical_source_heldout_realistic_shell_target100m_probe/edit_localization_probe/row_field_logits.jsonl"
GEMMA = ROOT / "runs/local/artifacts/stage10090_canonical_source_heldout_realistic_shell_gemma_execution/same_prompt_surface_gemma12b_outputs_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_audit() -> dict[str, Any]:
    manifest = {str(row.get("row_id") or ""): row for row in load_jsonl(MANIFEST) if str(row.get("split") or "") in {"eval", "strict_eval"}}
    hundred_m = {str(row.get("row_id") or ""): row for row in load_jsonl(HUNDRED_M)}
    gemma_rows = {str(row.get("row_id") or ""): row for row in load_jsonl(GEMMA)}
    failures: list[str] = []
    if not hundred_m or not gemma_rows:
        return {"passed": True, "failures": [], "metrics": {"rows_100m_present": len(hundred_m), "rows_gemma_present": len(gemma_rows), "shared_rows": 0, "comparison_rows": 0, "macro_exact_100m": None, "macro_exact_gemma": None, "macro_delta_100m_minus_gemma": None, "wins_100m": 0, "wins_gemma": 0, "ties": 0, "per_language": {}, "execution_ready": False, "l2_shell_shared_rows": 0}, "rows": []}
    comparisons: list[dict[str, Any]] = []
    language_totals: dict[str, list[int]] = {}
    shared_ids = sorted(set(manifest) & set(hundred_m) & set(gemma_rows))
    for row_id in shared_ids:
        source = manifest[row_id]
        hm = hundred_m.get(row_id)
        gm = gemma_rows.get(row_id)
        language = str(source.get("language_family") or "")
        bucket = language_totals.setdefault(language, [0, 0, 0])
        hm_correct = bool(hm.get("correct"))
        gm_correct = bool(gm.get("correct"))
        bucket[0] += int(hm_correct)
        bucket[1] += int(gm_correct)
        bucket[2] += 1
        input_state = source.get("input_state") if isinstance(source.get("input_state"), dict) else {}
        comparisons.append({"row_id": row_id, "language_family": language, "split": source.get("split"), "hundred_m_pred": hm.get("pred"), "gemma_pred": gm.get("predicted_label"), "expected_label": hm.get("target"), "hundred_m_correct": hm_correct, "gemma_correct": gm_correct, "realism_level": input_state.get("realism_level")})
    per_language = {}
    wins_100m = wins_gemma = ties = 0
    for language, (hm_correct, gm_correct, total) in sorted(language_totals.items()):
        hm_exact = hm_correct / total if total else 0.0
        gm_exact = gm_correct / total if total else 0.0
        if hm_exact > gm_exact:
            verdict = "100m_better"
            wins_100m += 1
        elif gm_exact > hm_exact:
            verdict = "gemma_better"
            wins_gemma += 1
        else:
            verdict = "tie"
            ties += 1
        per_language[language] = {"hundred_m_exact": hm_exact, "gemma_exact": gm_exact, "delta_hundred_m_minus_gemma": hm_exact - gm_exact, "rows": total, "verdict": verdict}
    macro_100m = sum(v["hundred_m_exact"] for v in per_language.values()) / len(per_language) if per_language else 0.0
    macro_gemma = sum(v["gemma_exact"] for v in per_language.values()) / len(per_language) if per_language else 0.0
    l2_shell_shared_rows = sum(1 for row in comparisons if str(row.get("realism_level") or "") == "L2")
    if len(shared_ids) != len(hundred_m):
        failures.append("shared_ids_not_equal_to_hundred_m_rows")
    if len(shared_ids) != len(gemma_rows):
        failures.append("shared_ids_not_equal_to_gemma_rows")
    if len(shared_ids) != 55:
        failures.append("shared_ids_not_equal_to_55")
    if len(per_language) != 4:
        failures.append("per_language_not_4")
    if l2_shell_shared_rows != 55:
        failures.append("l2_shell_shared_rows_not_55")
    return {"passed": not failures, "failures": failures, "metrics": {"rows_100m_present": len(hundred_m), "rows_gemma_present": len(gemma_rows), "shared_rows": len(shared_ids), "comparison_rows": len(comparisons), "macro_exact_100m": macro_100m, "macro_exact_gemma": macro_gemma, "macro_delta_100m_minus_gemma": macro_100m - macro_gemma, "wins_100m": wins_100m, "wins_gemma": wins_gemma, "ties": ties, "per_language": per_language, "execution_ready": True, "l2_shell_shared_rows": l2_shell_shared_rows}, "rows": comparisons}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    AUDIT.write_text(json.dumps({"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(ROWS, built["rows"])
    next_step = "Use this audit to answer whether the current 100M retains its multilingual advantage over Gemma once the same heldout rows are upgraded to the stage10088 L2-style maintenance shell."
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": built["passed"], "metrics": {**built["metrics"], "failures": built["failures"]}, "artifacts": {"audit": display(AUDIT), "rows": display(ROWS), "doc": display(DOC)}, "decision": "Materialized the realistic-shell same-manifest comparison audit scaffold so the stage10088 reruns can be judged directly on the richer 55-row heldout bank.", "next_best_step": next_step, "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage10091 Canonical Source-Heldout Realistic Shell Same-Manifest Comparison Audit", "", f"Passed: `{summary['passed']}`", "", summary["decision"], "", f"Next: {next_step}", ""]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
