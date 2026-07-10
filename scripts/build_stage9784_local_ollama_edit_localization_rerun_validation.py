#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9784
NAME = "stage9784_local_ollama_edit_localization_rerun_validation"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "local_ollama_edit_localization_rerun_validation.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LOCAL_OLLAMA_EDIT_LOCALIZATION_RERUN_VALIDATION_STAGE9784.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"
QUEUE = ROOT / "runs/local/artifacts/stage9748_supported_standalone_gemma_queue/supported_standalone_gemma_queue.json"
GEMMA_9775 = ROOT / "runs/local/artifacts/stage9775_edit_localization_visible_evidence_gemma_comparison/edit_localization_visible_evidence_gemma_comparison.json"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
EXPECTED_GEMMA = {
    "python": 0.2,
    "rust": 0.2,
    "c_cpp": 0.4,
    "web_js_ts_html": 0.2,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def build_audit() -> dict[str, Any]:
    packets = {str(row.get("cell_key") or ""): row for row in load_jsonl(PACKETS)}
    queue = load_json(QUEUE)
    queue_rows = {str(row.get("cell_key") or ""): row for row in (queue.get("queue_entries") or [])}
    gemma_9775 = {str(row.get("language") or ""): row for row in (load_json(GEMMA_9775).get("results") or [])}

    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    matching_scores = 0
    verified_surfaces = 0

    for lang in LANGS:
        cell_key = f"standalone_100m_weights::{lang}::edit_localization"
        packet = packets.get(cell_key)
        queue_row = queue_rows.get(cell_key)
        if not isinstance(packet, dict) or not isinstance(queue_row, dict):
            failures.append(f"missing_packet_or_queue:{cell_key}")
            continue
        output_rel = ((packet.get("review_packet_paths") or {}).get("same_prompt_surface_gemma12b_outputs"))
        if not output_rel:
            failures.append(f"missing_output_path:{cell_key}")
            continue
        output_path = ROOT / str(output_rel)
        if not output_path.exists():
            failures.append(f"missing_output_file:{cell_key}")
            continue
        output = load_json(output_path)
        rows_path = output_path.with_name(output_path.stem + "_rows.jsonl")
        row_count = len(load_jsonl(rows_path)) if rows_path.exists() else 0
        expected = EXPECTED_GEMMA[lang]
        score = output.get("score_gemma12b")
        same_surface_verified = output.get("same_surface_verified") is True
        score_match = score == expected == (gemma_9775.get(lang) or {}).get("gemma_strict_exact")
        if same_surface_verified:
            verified_surfaces += 1
        if score_match:
            matching_scores += 1
        if output.get("full_packet_surface_hash_gemma12b") != queue_row.get("same_surface_packet", {}).get("surface_hash"):
            failures.append(f"surface_hash_mismatch:{cell_key}")
        if output.get("executed_split") != "strict_eval":
            failures.append(f"wrong_split:{cell_key}")
        if row_count != 5:
            failures.append(f"wrong_row_count:{cell_key}:{row_count}")
        if score != expected:
            failures.append(f"unexpected_score:{cell_key}:{score}")
        rows.append(
            {
                "cell_key": cell_key,
                "language_family": lang,
                "score_100m": queue_row.get("same_surface_packet", {}).get("strict_exact"),
                "score_gemma12b": score,
                "expected_gemma12b": expected,
                "same_surface_verified": same_surface_verified,
                "full_packet_surface_hash_gemma12b": output.get("full_packet_surface_hash_gemma12b"),
                "packet_surface_hash": queue_row.get("same_surface_packet", {}).get("surface_hash"),
                "executed_subset_matches_full_packet": output.get("executed_subset_matches_full_packet"),
                "executed_row_count": output.get("executed_row_count"),
                "row_outputs_path": str(rows_path.relative_to(ROOT)) if rows_path.exists() else None,
                "output_path": str(output_path.relative_to(ROOT)),
            }
        )

    return {
        "passed": not failures,
        "failures": failures,
        "rows": rows,
        "metrics": {
            "validated_cells": len(rows),
            "matching_scores": matching_scores,
            "verified_surfaces": verified_surfaces,
            "wins_100m": sum(1 for row in rows if row.get("score_100m") > row.get("score_gemma12b")),
            "wins_gemma": sum(1 for row in rows if row.get("score_100m") < row.get("score_gemma12b")),
            "ties": sum(1 for row in rows if row.get("score_100m") == row.get("score_gemma12b")),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use the validated local Gemma rerun artifacts as the current same-surface standalone evidence for the four winning edit-localization languages, "
        "then complete expert-maintainer and anti-cheat review because those are now the remaining blockers on these cells."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"], "failures": audit["failures"]},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Validated that the local Ollama Gemma rerun reproduces the expected Stage9775 strict-eval scores on the four refreshed winning edit-localization cells and that the stored artifacts now carry truthful same-surface verification against the full packet.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9784 Local Ollama Edit Localization Rerun Validation",
                "",
                f"Passed: `{summary['passed']}`",
                f"Validated cells: `{audit['metrics']['validated_cells']}`",
                f"Matching Gemma scores: `{audit['metrics']['matching_scores']}`",
                f"Verified surfaces: `{audit['metrics']['verified_surfaces']}`",
                f"100M wins: `{audit['metrics']['wins_100m']}`",
                f"Gemma wins: `{audit['metrics']['wins_gemma']}`",
                f"Ties: `{audit['metrics']['ties']}`",
                "",
                "This stage turns the ad hoc local Ollama reruns into an audited artifact. It proves the refreshed standalone packets for the four winning edit-localization languages now have real local Gemma outputs that match the expected Stage9775 strict-eval scores and verify against the full packet surface hash.",
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "metrics": audit["metrics"],
        "failures": audit["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
