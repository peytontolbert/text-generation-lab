#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10235
NAME = "stage10235_fresh_maintainer_bundle_replenishment_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "fresh_maintainer_bundle_replenishment_request.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

LEDGER = ROOT / "runs/local/artifacts/stage10109_real_session_multilingual_replenishment_ledger/real_session_multilingual_replenishment_ledger.json"
CANDIDATES = ROOT / "runs/local/artifacts/stage10109_real_session_multilingual_replenishment_ledger/real_session_multilingual_replenishment_candidates.jsonl"
WEB_AUDIT = ROOT / "runs/local/artifacts/stage10175_web_root_supply_and_bundle_gap_audit/web_root_supply_and_bundle_gap_audit.json"
REFRESH_REVIEW = ROOT / "runs/local/artifacts/stage10234_ai_adjudicate_replenishment_candidates/ai_adjudicate_replenishment_candidates.json"
RUST_PREVIEW = ROOT / "runs/local/artifacts/stage10126_true_source_backed_rust_root_bundle_preview/true_source_backed_rust_root_bundle_preview.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    if not REGISTRY.exists():
        return
    registry = load_json(REGISTRY)
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    metrics = registry.get("metrics") or {}
    registry["metrics"] = {
        **metrics,
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int(metrics.get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _reviewed_bundle_ids() -> set[str]:
    bundle_ids: set[str] = set()
    for path in ROOT.glob("runs/local/artifacts/**/review_packets/*/expert_maintainer_rubric_review.json"):
        try:
            row = load_json(path)
        except Exception:
            continue
        bundle_id = str(row.get("bundle_id") or "").strip()
        if bundle_id:
            bundle_ids.add(bundle_id)
    return bundle_ids


def _episode_id_from_bundle(bundle_id: str) -> str:
    if "::" not in bundle_id:
        return ""
    return bundle_id.split("::", 1)[1].rsplit("::", 1)[0]


def _top_python_candidates(rows: list[dict[str, Any]], reviewed_episode_ids: set[str]) -> list[dict[str, Any]]:
    candidates = [
        row for row in rows
        if row.get("language_family") == "python"
        and bool(row.get("supports_shortcut_safe_successor"))
        and bool(row.get("query_text_present"))
        and len(row.get("selected_tests") or []) >= 6
        and str(row.get("episode_id") or "") not in reviewed_episode_ids
    ]
    candidates.sort(
        key=lambda row: (
            len(row.get("selected_tests") or []),
            len(row.get("change_paths_for_language") or []),
            row.get("repo_id") == "code_assist",
            row.get("repo_id") == "agentkernel",
            str(row.get("episode_id") or ""),
        ),
        reverse=True,
    )
    picked = []
    seen_repos: set[str] = set()
    for row in candidates:
        repo_id = str(row.get("repo_id") or "")
        if repo_id in seen_repos and len(picked) >= 2:
            continue
        picked.append(
            {
                "episode_id": row.get("episode_id"),
                "repo_id": row.get("repo_id"),
                "selected_tests_count": len(row.get("selected_tests") or []),
                "selected_tests": list(row.get("selected_tests") or []),
                "change_paths_for_language": list(row.get("change_paths_for_language") or []),
                "candidate_geometry_tags": list(row.get("candidate_geometry_tags") or []),
                "supports_shortcut_safe_successor": bool(row.get("supports_shortcut_safe_successor")),
                "recommended_builder_use": "fresh_python_maintainer_bundle",
            }
        )
        seen_repos.add(repo_id)
        if len(picked) >= 4:
            break
    return picked


def _top_cpp_candidates(rows: list[dict[str, Any]], reviewed_episode_ids: set[str]) -> list[dict[str, Any]]:
    candidates = [
        row for row in rows
        if row.get("language_family") == "c_cpp"
        and bool(row.get("supports_shortcut_safe_successor"))
        and bool(row.get("query_text_present"))
        and len(row.get("selected_tests") or []) >= 1
        and str(row.get("episode_id") or "") not in reviewed_episode_ids
    ]
    candidates.sort(key=lambda row: (len(row.get("selected_tests") or []), len(row.get("change_paths_for_language") or [])), reverse=True)
    return [
        {
            "episode_id": row.get("episode_id"),
            "repo_id": row.get("repo_id"),
            "selected_tests_count": len(row.get("selected_tests") or []),
            "selected_tests": list(row.get("selected_tests") or []),
            "change_paths_for_language": list(row.get("change_paths_for_language") or []),
            "candidate_geometry_tags": list(row.get("candidate_geometry_tags") or []),
            "supports_shortcut_safe_successor": bool(row.get("supports_shortcut_safe_successor")),
        }
        for row in candidates[:4]
    ]


def _rust_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        evidence = (row.get("maintainer_visible_evidence") or {}).get("verifier_and_test_constraint") or []
        out.append(
            {
                "bundle_id": row.get("bundle_id"),
                "selected_tests_count": len(row.get("selected_tests") or []),
                "selected_tests": list(row.get("selected_tests") or []),
                "candidate_paths": list(row.get("candidate_paths") or []),
                "verifier_constraint_paths": [item.get("path") for item in evidence if item.get("path")],
                "source_route": row.get("source_route"),
            }
        )
    return out


def main() -> None:
    ledger = load_json(LEDGER)
    rows = load_jsonl(CANDIDATES)
    web_audit = load_json(WEB_AUDIT)
    refresh = load_json(REFRESH_REVIEW)
    rust_preview = load_jsonl(RUST_PREVIEW)

    reviewed_bundle_ids = _reviewed_bundle_ids()
    reviewed_episode_ids = {_episode_id_from_bundle(bundle_id) for bundle_id in reviewed_bundle_ids if bundle_id.startswith("stage10119::localsess_")}

    python_candidates = _top_python_candidates(rows, reviewed_episode_ids)
    cpp_candidates = _top_cpp_candidates(rows, reviewed_episode_ids)
    rust_preview_status = _rust_status(rust_preview)

    code_assist_web = None
    for row in web_audit.get("replenishment_web_candidates", []):
        if row.get("repo_id") == "code_assist":
            code_assist_web = {
                "episode_id": row.get("episode_id"),
                "repo_id": row.get("repo_id"),
                "selected_tests_count": len(row.get("selected_tests") or []),
                "selected_tests": list(row.get("selected_tests") or []),
                "change_paths_for_language": list(row.get("change_paths_for_language") or []),
                "candidate_geometry_tags": list(row.get("candidate_geometry_tags") or []),
                "supports_shortcut_safe_successor": bool(row.get("supports_shortcut_safe_successor")),
                "required_filtering": [
                    "remove venv/site-packages repo_graph_neighbor rows",
                    "materialize only maintainer-relevant web evidence",
                    "keep raw backend orchestrator paths out of final candidate answers unless directly visible",
                ],
                "recommended_builder_use": "filtered_mixed_language_web_bundle",
            }
            break

    request = {
        "stage": STAGE,
        "name": NAME,
        "passed": True,
        "decision_boundary": "Advance multilingual maintainer-grade training/eval by using only fresh source-backed roots with visible verifier/test constraints or explicitly documented source gaps, rather than reusing the exhausted reviewed extra-bundle inventory.",
        "sources": {
            "replenishment_ledger": display(LEDGER),
            "replenishment_candidates": display(CANDIDATES),
            "web_gap_audit": display(WEB_AUDIT),
            "ai_adjudication_refresh": display(REFRESH_REVIEW),
            "rust_preview": display(RUST_PREVIEW),
        },
        "inventory_refresh": {
            "stale_candidates_cleared": bool(refresh.get("metrics", {}).get("packets_rejected") == 2),
            "remaining_current_inventory_same_language_replenishment_candidates": int(refresh.get("metrics", {}).get("remaining_current_inventory_same_language_replenishment_candidates") or 0),
            "reviewed_bundle_count": len(reviewed_bundle_ids),
            "reviewed_episode_ids_count": len(reviewed_episode_ids),
        },
        "fresh_builder_targets": {
            "python": {
                "status": "ready_now",
                "recommended_episode_targets": python_candidates,
                "builder_contract": [
                    "must preserve selected test visibility in verifier_and_test_constraint",
                    "must keep candidate paths within maintainer-plausible neighboring surfaces",
                    "must route through rubric, anti-cheat, and gold adjudication before train/eval use",
                ],
            },
            "web_js_ts_html": {
                "status": "ready_now_with_filtering",
                "recommended_episode_target": code_assist_web,
                "builder_contract": [
                    "must filter venv and site-packages neighbors",
                    "must materialize web-facing failure and test evidence rather than backend-only surface hints",
                    "must route through rubric, anti-cheat, and gold adjudication before train/eval use",
                ],
            },
            "c_cpp": {
                "status": "source_gap_after_reviewed_inventory",
                "fresh_unreviewed_selected_test_candidates": cpp_candidates,
                "diagnosis": "The only c_cpp candidates with selected tests in the current real-session inventory are already reviewed bundles or single-test packet variants that failed adjudication. Fresh honest c_cpp replenishment now requires new source mining rather than more packet repair.",
            },
            "rust": {
                "status": "source_gap_after_invalid_preview_reservoir",
                "preview_status": rust_preview_status,
                "diagnosis": "Current rust preview supply is still not maintainer-grade: tokenizers ties bench candidates to a wasm test, candle-core has no selected tests, and candle-examples exposes a weak build.rs verifier surface. Fresh rust replenishment requires new source-backed roots or stronger test materialization.",
            },
        },
        "metrics": {
            "python_ready_now_targets": len(python_candidates),
            "web_ready_now_targets": 1 if code_assist_web else 0,
            "c_cpp_fresh_unreviewed_selected_test_candidates": len(cpp_candidates),
            "rust_preview_rows_inspected": len(rust_preview_status),
        },
        "next_best_step": "Build one fresh Python bundle and one filtered code_assist web bundle first, then mine new c_cpp and rust source-backed roots with explicit selected tests before the next multilingual maintainer-grade training/eval refresh.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    write_json(REQUEST, request)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": True,
        "metrics": request["metrics"],
        "artifacts": {"request": display(REQUEST)},
        "decision": "Converted the post-adjudication supply state into a fresh multilingual maintainer-bundle replenishment request: Python and filtered web have ready-now targets, while c_cpp and rust now require new source mining instead of more review repair.",
        "next_best_step": request["next_best_step"],
        "created_at_utc": request["created_at_utc"],
    }
    write_json(SUMMARY, summary)
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": True, "metrics": request["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
