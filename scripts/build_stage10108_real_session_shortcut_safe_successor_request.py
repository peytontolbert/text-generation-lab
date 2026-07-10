#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10108
NAME = "stage10108_real_session_shortcut_safe_successor_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "real_session_shortcut_safe_successor_request.json"
SAFE_ROWS = OUT_DIR / "real_session_low_risk_carryforward_rows.jsonl"
QUARANTINED_ROWS = OUT_DIR / "real_session_quarantined_shortcut_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_SESSION_SHORTCUT_SAFE_SUCCESSOR_REQUEST_STAGE10108.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

PACKET = ROOT / "runs/local/artifacts/stage10103_real_session_candidate_competition_bootstrap_packet/real_session_candidate_competition_bootstrap_packet.jsonl"
ATLAS = ROOT / "runs/local/artifacts/stage10107_real_session_review_priority_shortcut_atlas/real_session_review_priority_shortcut_atlas.json"
QUEUE = ROOT / "runs/local/artifacts/stage10107_real_session_review_priority_shortcut_atlas/real_session_review_priority_queue.jsonl"


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
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _successor_rulebook(language: str) -> list[str]:
    common = [
        "Do not expose raw changed-path lists in the model-visible prompt.",
        "Do not include literal `Verification target:` or equivalent direct test-target phrasing.",
        "Require at least one concrete failure/assertion/trace cue plus at least one code or config snippet.",
        "Use opaque candidate IDs and support candidate-order permutation.",
        "Require anti-cheat review against length asymmetry, candidate-role priors, and path-signature leakage.",
    ]
    if language == "python":
        return common + [
            "Replace implementation-vs-test binary rows with competition among at least two maintainer-plausible non-test surfaces whenever possible.",
            "If a test candidate is unavoidable, pair it with another candidate whose prompt-visible evidence is equally concrete and equally short/long.",
        ]
    if language == "web_js_ts_html":
        return common + [
            "Rebuild the dropped web rows with real entrypoint-vs-implementation evidence only if both sides have balanced snippet materialization.",
            "Avoid entrypoint naming cues that directly reveal the answer without failure reasoning.",
        ]
    if language == "rust":
        return common + [
            "Replenish fresh source-backed Rust roots because no credible real-session competition rows currently survive.",
        ]
    if language == "c_cpp":
        return common + [
            "Expand beyond the three low-risk native rows so the maintainer packet is not dominated by Python.",
        ]
    return common


def build() -> dict[str, Any]:
    packet_rows = load_jsonl(PACKET)
    queue_rows = load_jsonl(QUEUE)
    atlas = load_json(ATLAS)
    failures: list[str] = []
    if len(packet_rows) != 33:
        failures.append("stage10103_packet_rows_not_33")
    if len(queue_rows) != 33:
        failures.append("stage10107_queue_rows_not_33")

    packet_by_row = {str(row.get("row_id") or ""): row for row in packet_rows}
    carryforward_rows: list[dict[str, Any]] = []
    quarantined_rows: list[dict[str, Any]] = []
    quarantine_counts = Counter()
    carryforward_counts = Counter()

    for risk_row in queue_rows:
        row_id = str(risk_row.get("row_id") or "")
        base_row = packet_by_row.get(row_id)
        if not base_row:
            failures.append(f"row_missing_from_stage10103:{row_id}")
            continue
        entry = {
            "row_id": row_id,
            "repo_id": base_row.get("repo_id"),
            "language_family": base_row.get("language_family"),
            "competition_template": base_row.get("competition_template"),
            "risk_score": risk_row.get("risk_score"),
            "risk_severity": risk_row.get("risk_severity"),
            "risk_reasons": risk_row.get("risk_reasons"),
            "surface_pair": risk_row.get("surface_pair"),
        }
        if risk_row.get("risk_severity") == "low":
            carryforward_rows.append(entry)
            carryforward_counts[str(entry["language_family"] or "")] += 1
        else:
            quarantined_rows.append(entry)
            quarantine_counts[str(entry["language_family"] or "")] += 1

    replacement_request = {
        "python": {
            "replacement_rows_required": int(quarantine_counts.get("python", 0)),
            "why": "The current Python real-session slice is dominated by implementation-vs-test rows with direct visible verification-target cues and strong snippet-length asymmetry.",
            "required_candidate_geometries": [
                "implementation_vs_implementation",
                "implementation_vs_entrypoint",
                "implementation_vs_config",
                "symbol_vs_symbol",
            ],
            "rulebook": _successor_rulebook("python"),
        },
        "web_js_ts_html": {
            "replacement_rows_required": 5,
            "why": "The original real-session web candidates dropped during materialization and need balanced snippet evidence before they can support a maintainer-grade comparison.",
            "required_candidate_geometries": [
                "entrypoint_vs_implementation",
                "implementation_vs_config",
            ],
            "rulebook": _successor_rulebook("web_js_ts_html"),
        },
        "rust": {
            "replacement_rows_required": 12,
            "why": "No credible source-backed Rust competition rows currently survive the bootstrap path, so multilingual maintainer claims remain unsupported.",
            "required_candidate_geometries": [
                "implementation_vs_implementation",
                "symbol_vs_symbol",
                "implementation_vs_config",
            ],
            "rulebook": _successor_rulebook("rust"),
        },
        "c_cpp": {
            "replacement_rows_required": 9,
            "why": "The three surviving native rows are low risk but too few to anchor a serious multilingual maintainer evaluation.",
            "required_candidate_geometries": [
                "implementation_vs_implementation",
                "symbol_vs_symbol",
            ],
            "rulebook": _successor_rulebook("c_cpp"),
        },
    }

    metrics = {
        "packet_rows": len(packet_rows),
        "carryforward_rows": len(carryforward_rows),
        "quarantined_rows": len(quarantined_rows),
        "carryforward_language_counts": dict(sorted(carryforward_counts.items())),
        "quarantined_language_counts": dict(sorted(quarantine_counts.items())),
        "high_risk_rows_from_stage10107": int((atlas.get("metrics") or {}).get("high_risk_rows", 0)),
    }
    request = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifacts": {
            "stage10103_packet": display(PACKET),
            "stage10107_atlas": display(ATLAS),
            "stage10107_queue": display(QUEUE),
            "carryforward_rows": display(SAFE_ROWS),
            "quarantined_rows": display(QUARANTINED_ROWS),
        },
        "intent": "Quarantine the shortcut-prone real-session slice and issue a successor request that replenishes multilingual maintainer-grade competition rows with safer candidate geometry.",
        "metrics": metrics,
        "claim_boundary": {
            "supports_training_or_scoring_now": False,
            "python_real_session_slice_must_be_rebuilt": metrics["quarantined_language_counts"].get("python", 0) > 0,
            "only_low_risk_native_rows_can_be_carried_forward_now": metrics["carryforward_rows"] == 3,
            "rust_replenishment_required": True,
            "web_replenishment_required": True,
        },
        "replacement_request": replacement_request,
        "failures": failures,
        "next_best_step": "Use this successor request to rebuild shortcut-safe Python/Web/Rust/C++ real-session competition rows, then rerun the shortcut atlas before any adjudication, training, or Gemma comparison.",
    }
    write_json(REQUEST, request)
    write_jsonl(SAFE_ROWS, carryforward_rows)
    write_jsonl(QUARANTINED_ROWS, quarantined_rows)
    return request


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    built = build()
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": built["artifacts"],
        "decision": "Quarantined the shortcut-prone real-session rows and converted the maintainer-eval gap into an explicit multilingual successor request with safer candidate geometry requirements.",
        "next_best_step": built["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10108 Real Session Shortcut Safe Successor Request",
                "",
                f"Passed: `{summary['passed']}`",
                f"Carryforward rows: `{built['metrics']['carryforward_rows']}`",
                f"Quarantined rows: `{built['metrics']['quarantined_rows']}`",
                "",
                summary["decision"],
                "",
                f"Next: {built['next_best_step']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"], "next_best_step": built["next_best_step"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
