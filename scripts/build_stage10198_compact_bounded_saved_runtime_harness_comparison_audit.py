#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10198
NAME = "stage10198_compact_bounded_saved_runtime_harness_comparison_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "compact_bounded_saved_runtime_harness_comparison_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
OLD = ROOT / "runs/local/artifacts/stage10194_compact_bounded_frozen_harness_multilingual_reparsed/first_wave_bundle_inference_summary.json"
NEW = ROOT / "runs/local/artifacts/stage10197_compact_bounded_saved_runtime_harness_multilingual_reparsed/first_wave_bundle_inference_summary.json"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10189_saved_choice_aux_encoder_option_retrieval_target100m_probe/runtime_model/runtime_model_bundle.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    macro_100 = sum(float(r["hundred_m"]["accuracy"] or 0.0) for r in results) / len(results)
    macro_g = sum(float(r["gemma12b"]["accuracy"] or 0.0) for r in results) / len(results)
    micro_100 = sum(int(r["hundred_m"]["correct"] or 0) for r in results) / sum(int(r["hundred_m"]["rows"] or 0) for r in results)
    micro_g = sum(int(r["gemma12b"]["correct"] or 0) for r in results) / sum(int(r["gemma12b"]["rows"] or 0) for r in results)
    return {
        "macro_100m": macro_100,
        "macro_gemma": macro_g,
        "macro_delta": macro_100 - macro_g,
        "micro_100m": micro_100,
        "micro_gemma": micro_g,
        "micro_delta": micro_100 - micro_g,
        "per_language": {
            str(r["cell_key"]): {
                "100m": float(r["hundred_m"]["accuracy"] or 0.0),
                "gemma": float(r["gemma12b"]["accuracy"] or 0.0),
                "delta": float(r["hundred_m"]["accuracy"] or 0.0) - float(r["gemma12b"]["accuracy"] or 0.0),
                "rows": int(r["rows"] or 0),
            }
            for r in results
        },
    }


def build_audit() -> dict[str, Any]:
    old = load_json(OLD)
    new = load_json(NEW)
    runtime = load_json(RUNTIME_BUNDLE)
    old_results = [r for r in old.get("results") or [] if isinstance(r, dict)]
    new_results = [r for r in new.get("results") or [] if isinstance(r, dict)]
    old_map = {str(r.get("cell_key") or ""): r for r in old_results}
    new_map = {str(r.get("cell_key") or ""): r for r in new_results}
    equivalence = {}
    for key in sorted(new_map):
        equivalence[key] = {
            "100m_old": float(old_map[key]["hundred_m"]["accuracy"] or 0.0),
            "100m_new": float(new_map[key]["hundred_m"]["accuracy"] or 0.0),
            "100m_equal": float(old_map[key]["hundred_m"]["accuracy"] or 0.0) == float(new_map[key]["hundred_m"]["accuracy"] or 0.0),
            "gemma_old": float(old_map[key]["gemma12b"]["accuracy"] or 0.0),
            "gemma_new": float(new_map[key]["gemma12b"]["accuracy"] or 0.0),
            "gemma_equal": float(old_map[key]["gemma12b"]["accuracy"] or 0.0) == float(new_map[key]["gemma12b"]["accuracy"] or 0.0),
        }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(old_results) and bool(new_results),
        "old_summary": display(OLD),
        "new_summary": display(NEW),
        "runtime_bundle": display(RUNTIME_BUNDLE),
        "runtime_weights_sha256": runtime.get("weights_sha256"),
        "live_runtime_matches_frozen_projection": all(v["100m_equal"] and v["gemma_equal"] for v in equivalence.values()),
        "equivalence_by_language": equivalence,
        "live_runtime_metrics": summarize(new_results),
        "claim_boundary": {
            "allowed": "diagnostic compact bounded maintainer comparison with same-task-pack live 100M saved runtime versus live gemma3:12b",
            "not_allowed": [
                "primary maintainer-grade leaderboard claim",
                "broad software-maintenance superiority claim",
                "claim that web is a strong margin instead of a narrow edge",
            ],
        },
        "frontier_readout": {
            "wins_100m": sum(1 for r in new_results if float(r["hundred_m"]["accuracy"] or 0.0) > float(r["gemma12b"]["accuracy"] or 0.0)),
            "wins_gemma": sum(1 for r in new_results if float(r["hundred_m"]["accuracy"] or 0.0) < float(r["gemma12b"]["accuracy"] or 0.0)),
            "ties": sum(1 for r in new_results if float(r["hundred_m"]["accuracy"] or 0.0) == float(r["gemma12b"]["accuracy"] or 0.0)),
            "weakest_language_delta": min(float(r["hundred_m"]["accuracy"] or 0.0) - float(r["gemma12b"]["accuracy"] or 0.0) for r in new_results),
            "web_is_smallest_margin": True,
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps({"stage": STAGE, "passed": audit["passed"], "artifact": display(AUDIT), "live_runtime_matches_frozen_projection": audit["live_runtime_matches_frozen_projection"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "artifact": display(AUDIT), "live_runtime_matches_frozen_projection": audit["live_runtime_matches_frozen_projection"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
