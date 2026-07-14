#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10221
NAME = "stage10221_adjudicated_projection_saved_runtime_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "adjudicated_projection_saved_runtime_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
SOURCE = ROOT / "runs/local/artifacts/stage10220_adjudicated_projection_saved_runtime_multilingual/first_wave_bundle_inference_summary.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    summary = load_json(SOURCE)
    results = [row for row in summary.get("results") or [] if isinstance(row, dict)]
    by_lang = defaultdict(list)
    bundle_cards = []
    hundred_macro = []
    gemma_macro = []
    hundred_correct = 0
    gemma_correct = 0
    total_rows = 0
    for row in results:
        language = str(row.get("bundle_id") or "").split("::")[-1]
        h = float(((row.get("hundred_m") or {}).get("accuracy") or 0.0))
        g = float(((row.get("gemma12b") or {}).get("accuracy") or 0.0))
        rows = int(row.get("rows") or 0)
        h_correct = int(((row.get("hundred_m") or {}).get("correct") or 0))
        g_correct = int(((row.get("gemma12b") or {}).get("correct") or 0))
        by_lang[language].append((h, g, rows, h_correct, g_correct))
        hundred_macro.append(h)
        gemma_macro.append(g)
        hundred_correct += h_correct
        gemma_correct += g_correct
        total_rows += rows
        bundle_cards.append({
            "bundle_id": row.get("bundle_id"),
            "language_family": language,
            "rows": rows,
            "hundred_m_accuracy": h,
            "gemma_accuracy": g,
            "delta": h - g,
            "hundred_m_bundle_solved": h_correct == rows and rows > 0,
            "gemma_bundle_solved": g_correct == rows and rows > 0,
        })
    per_language = {}
    for language, cards in sorted(by_lang.items()):
        h_accs = [c[0] for c in cards]
        g_accs = [c[1] for c in cards]
        rows = sum(c[2] for c in cards)
        h_correct = sum(c[3] for c in cards)
        g_correct = sum(c[4] for c in cards)
        per_language[language] = {
            "bundles": len(cards),
            "rows": rows,
            "hundred_m_macro": mean(h_accs),
            "gemma_macro": mean(g_accs),
            "delta_macro": mean(h_accs) - mean(g_accs),
            "hundred_m_micro": h_correct / rows if rows else 0.0,
            "gemma_micro": g_correct / rows if rows else 0.0,
            "delta_micro": (h_correct / rows if rows else 0.0) - (g_correct / rows if rows else 0.0),
        }
    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(results),
        "source_summary": display(SOURCE),
        "claim_scope": "adjudicated compact-bounded maintainer projection only; bundle-level diagnostic of current saved-runtime 100M versus live gemma3:12b",
        "metrics": {
            "bundle_count": len(results),
            "row_count": total_rows,
            "hundred_m_macro": mean(hundred_macro),
            "gemma_macro": mean(gemma_macro),
            "delta_macro": mean(hundred_macro) - mean(gemma_macro),
            "hundred_m_micro": hundred_correct / total_rows if total_rows else 0.0,
            "gemma_micro": gemma_correct / total_rows if total_rows else 0.0,
            "delta_micro": (hundred_correct / total_rows if total_rows else 0.0) - (gemma_correct / total_rows if total_rows else 0.0),
            "hundred_m_bundle_solved": sum(1 for c in bundle_cards if c["hundred_m_bundle_solved"]),
            "gemma_bundle_solved": sum(1 for c in bundle_cards if c["gemma_bundle_solved"]),
        },
        "per_language": per_language,
        "bundle_cards": bundle_cards,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps({"stage": STAGE, "passed": audit["passed"], "artifact": display(AUDIT), "metrics": audit["metrics"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "artifact": display(AUDIT), "metrics": audit["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
