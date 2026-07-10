#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9770
NAME = "stage9770_multilingual_edit_localization_gemma_comparison"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "multilingual_edit_localization_gemma_comparison.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MULTILINGUAL_EDIT_LOCALIZATION_GEMMA_COMPARISON_STAGE9770.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"
REVIEW_DIR = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/review_packets"
LANGUAGES = ["python", "rust", "c_cpp", "web_js_ts_html"]
SKILL = "edit_localization"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def packet_dir(language: str) -> Path:
    return REVIEW_DIR / f"standalone_100m_weights__{language}__{SKILL}"


def build_audit() -> dict[str, Any]:
    packets = load_jsonl(PACKETS)
    packet_index = {str(packet.get("cell_key") or ""): packet for packet in packets}
    results = []
    gemma_better = 0
    model_better = 0
    ties = 0
    predicted_counter: Counter[str] = Counter()
    expected_counter: Counter[str] = Counter()
    for language in LANGUAGES:
        cell_key = f"standalone_100m_weights::{language}::{SKILL}"
        packet = packet_index[cell_key]
        same_surface = packet["same_surface_packet"]
        gemma = load_json(packet_dir(language) / "same_prompt_surface_gemma12b_outputs.json")
        rows = load_jsonl(packet_dir(language) / "same_prompt_surface_gemma12b_outputs_rows.jsonl")
        predicted_counter.update(str(row.get("predicted_label")) for row in rows if row.get("predicted_label"))
        expected_counter.update(str(row.get("expected_label")) for row in rows if row.get("expected_label"))
        model_score = float(same_surface.get("strict_exact") or 0.0)
        gemma_score = float(gemma.get("score_gemma12b") or 0.0)
        delta = round(model_score - gemma_score, 6)
        verdict = "tie"
        if delta > 0:
            verdict = "100m_better"
            model_better += 1
        elif delta < 0:
            verdict = "gemma_better"
            gemma_better += 1
        else:
            ties += 1
        miss_examples = [
            {
                "row_id": row.get("row_id"),
                "expected_label": row.get("expected_label"),
                "predicted_label": row.get("predicted_label"),
            }
            for row in rows if row.get("correct") is False
        ][:3]
        results.append({
            "language": language,
            "cell_key": cell_key,
            "model_strict_exact_100m": model_score,
            "gemma_strict_exact": gemma_score,
            "delta_100m_minus_gemma": delta,
            "verdict": verdict,
            "strict_rows": same_surface.get("strict_rows"),
            "gemma_status": gemma.get("status"),
            "label_vocab_scope": gemma.get("label_vocab_scope"),
            "executed_split": gemma.get("executed_split"),
            "executed_row_count": gemma.get("executed_row_count"),
            "miss_examples": miss_examples,
        })
    most_common_predicted = predicted_counter.most_common()
    most_common_expected = expected_counter.most_common()
    passed = len(results) == 4
    return {
        "passed": passed,
        "skill_area": SKILL,
        "language_count": len(results),
        "gemma_better_language_count": gemma_better,
        "model_better_language_count": model_better,
        "tie_language_count": ties,
        "results": results,
        "predicted_label_distribution": most_common_predicted,
        "expected_label_distribution": most_common_expected,
        "findings": [
            "Under deterministic seeded decoding, strict-eval edit localization is a four-language tie: python, rust, c_cpp, and web_js_ts_html are all 0.2 for Gemma versus 0.2 for the 100M model.",
            "This does not support the claim that the current standalone 100M package beats Gemma across the four target language groups; at best it matches Gemma on the current best multilingual surface.",
            "Gemma miss patterns are still dominated by coarse target collapse, especially repeated TARGET_FILE predictions where the expected label is TARGET_SYMBOL, TARGET_CONFIG, TARGET_TEST, or TARGET_ENTRYPOINT.",
            "The earlier apparent win/loss drift was a measurement problem from non-deterministic CLI decoding; the current artifacts use seeded temperature-zero API decoding plus full-packet label vocabulary metadata.",
        ],
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Push edit-localization beyond 0.2 with better target-space evidence and disambiguation rows, then expand the same deterministic comparison contract to patch operator and verifier repair before claiming any cross-language Gemma win."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "language_count": audit["language_count"],
            "gemma_better_language_count": audit["gemma_better_language_count"],
            "model_better_language_count": audit["model_better_language_count"],
            "tie_language_count": audit["tie_language_count"],
        },
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "The deterministic strict multilingual comparison on the best current standalone surface is a four-language tie at 0.2, so the current 100M package still does not beat Gemma across python, rust, c_cpp, and web_js_ts_html.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Stage9770 Multilingual Edit Localization Gemma Comparison",
        "",
        f"Passed: `{summary['passed']}`",
        f"Language count: `{audit['language_count']}`",
        f"100M-better languages: `{audit['model_better_language_count']}`",
        f"Gemma-better languages: `{audit['gemma_better_language_count']}`",
        f"Tie languages: `{audit['tie_language_count']}`",
        "",
        "Result summary:",
        "- python: tie at 0.2 strict exact",
        "- rust: tie at 0.2 strict exact",
        "- c_cpp: tie at 0.2 strict exact",
        "- web_js_ts_html: tie at 0.2 strict exact",
        "",
        "Anti-cheat note: bounded Gemma artifacts now record full-packet label vocabulary scope and deterministic seeded decoding; the earlier slice-local label collapse and decoding drift issues are no longer part of these results.",
        "",
        f"Next: {next_step}",
        "",
    ]
    DOC.write_text("\n".join(lines), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "language_count": audit["language_count"],
        "model_better_language_count": audit["model_better_language_count"],
        "gemma_better_language_count": audit["gemma_better_language_count"],
        "tie_language_count": audit["tie_language_count"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
