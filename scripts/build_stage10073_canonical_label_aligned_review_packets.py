#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10073
NAME = "stage10073_canonical_label_aligned_review_packets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKETS = OUT_DIR / "canonical_label_aligned_review_packets.jsonl"
MANIFEST = OUT_DIR / "canonical_label_aligned_review_manifest.json"
AUDIT = OUT_DIR / "canonical_label_aligned_review_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_LABEL_ALIGNED_REVIEW_PACKETS_STAGE10073.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUEST = ROOT / "runs/local/artifacts/stage10084_canonical_label_aligned_source_heldout_target100m_execution_request/surface_requests/edit_localization.json"
QUEUE = ROOT / "runs/local/artifacts/stage10085_canonical_label_aligned_source_heldout_same_manifest_gemma_queue/canonical_label_aligned_source_heldout_same_manifest_gemma_queue.json"
COMPARISON = ROOT / "runs/local/artifacts/stage10086_canonical_label_aligned_source_heldout_same_manifest_comparison_audit/canonical_label_aligned_source_heldout_same_manifest_comparison_audit.json"
COMPARISON_ROWS = ROOT / "runs/local/artifacts/stage10086_canonical_label_aligned_source_heldout_same_manifest_comparison_audit/canonical_label_aligned_source_heldout_same_manifest_comparison_rows.jsonl"
COLLISION_AUDIT = ROOT / "runs/local/artifacts/stage10068_multilingual_label_semantics_collision_audit/multilingual_label_semantics_collision_audit.json"
PROBE_RESULT = ROOT / "runs/local/artifacts/stage10084_canonical_label_aligned_source_heldout_target100m_probe/edit_localization_probe/execution_result.json"
GEMMA_RESULT = ROOT / "runs/local/artifacts/stage10085_canonical_label_aligned_source_heldout_gemma_execution/same_prompt_surface_gemma12b_outputs.json"
MANIFEST_PATH = ROOT / "runs/local/artifacts/stage10083_canonical_label_aligned_source_heldout_successor_packet/canonical_label_aligned_source_heldout_manifest.jsonl"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
CHALLENGE_FAMILIES = [
    "canonical_label_semantics_alignment",
    "target_and_teacher_leakage",
    "label_proxy_shortcuts",
    "raw_source_or_symbol_leakage",
    "source_lineage_and_gate_integrity",
    "same_manifest_cross_model_fairness",
]


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
    return OUT_DIR / "review_packets" / f"canonical_label_aligned_target100m__{language}__edit_localization"


def packet_paths(language: str) -> dict[str, str]:
    base = packet_dir(language)
    return {
        "packet_dir": display(base),
        "expert_maintainer_rubric_review": display(base / "expert_maintainer_rubric_review.json"),
        "anti_cheat_review_card": display(base / "anti_cheat_review_card.json"),
    }


def build_packets() -> dict[str, Any]:
    request = load_json(REQUEST)
    queue = load_json(QUEUE)
    comparison = load_json(COMPARISON)
    comparison_rows = load_jsonl(COMPARISON_ROWS)
    collision = load_json(COLLISION_AUDIT)
    probe = load_json(PROBE_RESULT)
    gemma = load_json(GEMMA_RESULT)
    rows = load_jsonl(MANIFEST_PATH)
    failures: list[str] = []

    if request.get("surface") != "edit_localization":
        failures.append("stage10070_request_not_edit_localization")
    if comparison.get("passed") is not True:
        failures.append("stage10086_not_passed")
    if collision.get("passed") is not True:
        failures.append("stage10068_not_passed")
    if probe.get("runtime_executed") is not True:
        failures.append("stage10070_runtime_not_executed")
    if gemma.get("status") != "completed_gemma_execution":
        failures.append("stage10071_gemma_not_completed")

    compare_rows = [row for row in rows if str(row.get("split") or "") in {"eval", "strict_eval"}]
    if len(compare_rows) != 55:
        failures.append("compare_rows_not_55")

    compare_by_language = Counter(str(row.get("language_family") or "") for row in compare_rows)
    comparison_metrics = (comparison.get("metrics") or {}).get("per_language") or {}
    review_rows: list[dict[str, Any]] = []
    language_cards: list[dict[str, Any]] = []

    for language in LANGS:
        base = packet_dir(language)
        base.mkdir(parents=True, exist_ok=True)
        lang_rows = [row for row in compare_rows if str(row.get("language_family") or "") == language]
        lang_result = comparison_metrics.get(language) or {}
        lang_compare_records = [row for row in comparison_rows if str(row.get("language_family") or "") == language]
        hidden_targets = sorted({str((row.get("clean_state") or {}).get("edit_localization_target_hidden") or "") for row in lang_rows})
        rubric = {
            "cell_key": f"canonical_label_aligned_target100m::{language}::edit_localization::same_manifest_review",
            "language_family": language,
            "status": "pending_human_review",
            "passed": False,
            "same_manifest_rows": len(lang_rows),
            "machine_outcome": {
                "hundred_m_exact": lang_result.get("hundred_m_exact"),
                "gemma_exact": lang_result.get("gemma_exact"),
                "delta_hundred_m_minus_gemma": lang_result.get("delta_hundred_m_minus_gemma"),
                "verdict": lang_result.get("verdict"),
            },
            "hidden_target_families": hidden_targets,
            "required_human_action": "Review the attached same-manifest 100M and Gemma outputs and score whether visible evidence supports one expert-maintainer-justified edit-localization answer on these rows.",
            "supporting_evidence_paths": {
                "same_manifest_request": display(REQUEST),
                "same_manifest_comparison": display(COMPARISON),
                "same_manifest_rows": display(COMPARISON_ROWS),
                "target100m_execution_result": display(PROBE_RESULT),
                "gemma_execution_result": display(GEMMA_RESULT),
            },
        }
        anti = {
            "cell_key": rubric["cell_key"],
            "language_family": language,
            "status": "pending_human_review",
            "passed": False,
            "challenge_families": list(CHALLENGE_FAMILIES),
            "machine_supported_checks": {
                "same_manifest_rows": len(lang_rows),
                "label_semantics_collision_count": (collision.get("metrics") or {}).get("collision_label_count"),
                "canonical_remap_applied": True,
                "prompt_surface_same_for_gemma": bool(gemma.get("same_surface_verified") is True),
                "gemma_output_row_count": sum(1 for row in lang_compare_records if row.get("gemma_pred") is not None),
                "hundred_m_output_row_count": sum(1 for row in lang_compare_records if row.get("hundred_m_pred") is not None),
                "verdict": lang_result.get("verdict"),
            },
            "required_human_action": "Confirm the canonical-label remap removed cross-language label-semantic shortcuts and that the attached same-manifest outputs do not show leakage, metadata confounds, or unfair prompt divergence.",
            "supporting_evidence_paths": {
                "label_collision_audit": display(COLLISION_AUDIT),
                "canonical_manifest": display(MANIFEST_PATH),
                "same_manifest_gemma_queue": display(ROOT / "runs/local/artifacts/stage10085_canonical_label_aligned_source_heldout_same_manifest_gemma_queue/canonical_label_aligned_source_heldout_same_manifest_gemma_queue.json"),
                "gemma_execution_rows": display(ROOT / "runs/local/artifacts/stage10085_canonical_label_aligned_source_heldout_gemma_execution/same_prompt_surface_gemma12b_outputs_rows.jsonl"),
                "target100m_logits": display(ROOT / "runs/local/artifacts/stage10084_canonical_label_aligned_source_heldout_target100m_probe/edit_localization_probe/row_field_logits.jsonl"),
            },
        }
        write_json(base / "expert_maintainer_rubric_review.json", rubric)
        write_json(base / "anti_cheat_review_card.json", anti)
        review_rows.append(
            {
                "cell_key": rubric["cell_key"],
                "language_family": language,
                "same_manifest_rows": len(lang_rows),
                "hidden_target_families": hidden_targets,
                **packet_paths(language),
            }
        )
        language_cards.append(
            {
                "language_family": language,
                "same_manifest_rows": len(lang_rows),
                "verdict": lang_result.get("verdict"),
                "packet_paths": packet_paths(language),
            }
        )

    write_jsonl(PACKETS, review_rows)
    write_json(
        MANIFEST,
        {
            "source_manifest": display(MANIFEST_PATH),
            "compare_rows": len(compare_rows),
            "language_cards": language_cards,
            "queue_source": display(QUEUE),
        },
    )

    metrics = {
        "language_packets": len(language_cards),
        "compare_rows": len(compare_rows),
        "language_compare_rows": dict(sorted(compare_by_language.items())),
        "wins_100m": (comparison.get("metrics") or {}).get("wins_100m"),
        "wins_gemma": (comparison.get("metrics") or {}).get("wins_gemma"),
    }
    if metrics["language_packets"] != 4:
        failures.append("language_packets_not_4")
    if metrics["wins_100m"] != 4:
        failures.append("wins_100m_not_4")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "language_cards": language_cards}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packets()
    write_json(AUDIT, {"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]})
    next_step = "Work these canonical-label review packets language by language to complete expert-maintainer rubric and anti-cheat signoff on the actual stage10086 source-heldout winning surface."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"packets": display(PACKETS), "manifest": display(MANIFEST), "audit": display(AUDIT), "doc": display(DOC)},
        "decision": "Materialized reviewer-facing canonical-label source-heldout packets with the real stage10084 100M outputs, stage10085 Gemma outputs, and the stage10068 label-collision audit attached to each winning language cell.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10073 Canonical Label Aligned Review Packets",
                "",
                f"Passed: `{summary['passed']}`",
                f"Language packets: `{built['metrics']['language_packets']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
