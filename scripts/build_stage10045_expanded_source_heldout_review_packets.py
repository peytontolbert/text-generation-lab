#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10045
NAME = "stage10045_expanded_source_heldout_review_packets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKETS = OUT_DIR / "expanded_source_heldout_review_packets.jsonl"
MANIFEST = OUT_DIR / "expanded_source_heldout_review_manifest.json"
AUDIT = OUT_DIR / "expanded_source_heldout_review_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EXPANDED_SOURCE_HELDOUT_REVIEW_PACKETS_STAGE10045.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUEST = ROOT / "runs/local/artifacts/stage10037_expanded_source_heldout_target100m_execution_request/surface_requests/edit_localization.json"
HANDOFF = ROOT / "runs/local/artifacts/stage10038_expanded_source_heldout_same_manifest_handoff_bundle/expanded_source_heldout_same_manifest_handoff_bundle.json"
REVIEW_PACKET = ROOT / "runs/local/artifacts/stage10042_expanded_source_heldout_review_packet/expanded_source_heldout_review_rows.jsonl"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
CHALLENGE_FAMILIES = [
    "target_and_teacher_leakage",
    "label_proxy_shortcuts",
    "raw_source_or_symbol_leakage",
    "source_lineage_and_gate_integrity",
    "same_manifest_cross_model_fairness",
    "fresh_heldout_discipline",
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
    return OUT_DIR / "review_packets" / f"expanded_source_heldout_target100m__{language}__edit_localization"


def packet_paths(language: str) -> dict[str, str]:
    base = packet_dir(language)
    return {
        "packet_dir": display(base),
        "expert_maintainer_rubric_review": display(base / "expert_maintainer_rubric_review.json"),
        "anti_cheat_review_card": display(base / "anti_cheat_review_card.json"),
    }


def build_packets() -> dict[str, Any]:
    request = load_json(REQUEST)
    handoff = load_json(HANDOFF)
    fresh_rows = load_jsonl(REVIEW_PACKET)
    failures: list[str] = []

    manifest_path = ROOT / str(request.get("manifest") or "")
    rows = load_jsonl(manifest_path) if manifest_path.exists() else []
    compare_rows = [row for row in rows if str(row.get("split") or "") in {"eval", "strict_eval"}]
    handoff_bundle = handoff.get("handoff_bundle") if isinstance(handoff.get("handoff_bundle"), dict) else {}
    row_contract = handoff_bundle.get("row_contract") if isinstance(handoff_bundle.get("row_contract"), dict) else {}

    if request.get("surface") != "edit_localization":
        failures.append("stage10037_request_not_edit_localization")
    if handoff.get("passed") is not True:
        failures.append("stage10038_not_passed")
    if len(compare_rows) != int(row_contract.get("same_manifest_compare_rows") or -1):
        failures.append("same_manifest_compare_rows_mismatch")
    if len(fresh_rows) != 18:
        failures.append("fresh_review_rows_not_18")

    review_rows: list[dict[str, Any]] = []
    language_cards: list[dict[str, Any]] = []
    fresh_counts = Counter(str(row.get("language_family") or "") for row in fresh_rows)

    for language in LANGS:
        lang_rows = [row for row in rows if str(row.get("language_family") or "") == language]
        lang_compare = [row for row in compare_rows if str(row.get("language_family") or "") == language]
        lang_fresh = [row for row in fresh_rows if str(row.get("language_family") or "") == language]
        metrics = {
            "rows": len(lang_rows),
            "compare_rows": len(lang_compare),
            "fresh_rows": len(lang_fresh),
            "split_counts": dict(sorted(Counter(str(row.get("split") or "") for row in lang_rows).items())),
            "all_fresh_rows_require_review": all(bool((row.get("anti_cheat_flags") or {}).get("requires_expert_maintainer_review_before_promotion")) for row in lang_fresh) if lang_fresh else True,
        }
        paths = packet_paths(language)
        rubric_stub = {
            "cell_key": f"expanded_source_heldout_target100m::{language}::edit_localization::same_manifest_review",
            "language_family": language,
            "status": "pending_real_outputs_and_human_review",
            "passed": False,
            "same_manifest_rows": metrics["compare_rows"],
            "fresh_rows": metrics["fresh_rows"],
            "required_human_action": "Score only the in-scope localization/evidence-grounding rubric lines after reviewing the real same-manifest 100M and Gemma outputs.",
        }
        anti_cheat_stub = {
            "cell_key": rubric_stub["cell_key"],
            "language_family": language,
            "status": "pending_real_outputs_and_human_review",
            "passed": False,
            "challenge_families": list(CHALLENGE_FAMILIES),
            "required_human_action": "Confirm the machine-supported anti-cheat signals on the expanded heldout packet, then recheck them against real stage10040 and stage10041 outputs.",
            "machine_supported_checks": {
                "compare_rows": metrics["compare_rows"],
                "fresh_rows": metrics["fresh_rows"],
                "all_fresh_rows_require_review": metrics["all_fresh_rows_require_review"],
            },
        }
        base = packet_dir(language)
        base.mkdir(parents=True, exist_ok=True)
        (base / "expert_maintainer_rubric_review.json").write_text(json.dumps(rubric_stub, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (base / "anti_cheat_review_card.json").write_text(json.dumps(anti_cheat_stub, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        review_rows.append(
            {
                "cell_key": rubric_stub["cell_key"],
                "language_family": language,
                "metrics": metrics,
                **paths,
            }
        )
        language_cards.append(
            {
                "language_family": language,
                "same_manifest_compare_rows": metrics["compare_rows"],
                "fresh_rows": metrics["fresh_rows"],
                "packet_paths": paths,
            }
        )

    write_jsonl(PACKETS, review_rows)
    write_json(
        MANIFEST,
        {
            "source_manifest": display(manifest_path),
            "compare_rows": len(compare_rows),
            "fresh_review_rows": len(fresh_rows),
            "languages": language_cards,
        },
    )

    metrics = {
        "language_packets": len(language_cards),
        "compare_rows": len(compare_rows),
        "fresh_review_rows": len(fresh_rows),
        "fresh_language_counts": dict(sorted(fresh_counts.items())),
    }
    if metrics["language_packets"] != 4:
        failures.append("language_packets_not_4")
    if metrics["compare_rows"] != 55:
        failures.append("compare_rows_not_55")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "language_cards": language_cards,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packets()
    write_json(AUDIT, {"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]})
    next_step = "Use these reviewer-facing expanded same-manifest packets to attach real stage10040 and stage10041 outputs, then complete maintainer and anti-cheat signoff before promoting any stronger heldout multilingual claim."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"packets": display(PACKETS), "manifest": display(MANIFEST), "audit": display(AUDIT), "doc": display(DOC)},
        "decision": "Materialized reviewer-facing expanded source-heldout same-manifest packets so expert-maintainer and anti-cheat review stay tied to the exact 95-row manifest, 55 compare rows, and 18 fresh Python/C++ rows.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10045 Expanded Source Heldout Review Packets",
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
