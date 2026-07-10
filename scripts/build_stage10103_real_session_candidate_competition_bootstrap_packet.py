#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10103
NAME = "stage10103_real_session_candidate_competition_bootstrap_packet"
SOURCE = ROOT / "runs/local/artifacts/stage10102_real_session_candidate_competition_request/real_session_candidate_competition_rows.jsonl"
REQUEST = ROOT / "runs/local/artifacts/stage10102_real_session_candidate_competition_request/real_session_candidate_competition_request.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "real_session_candidate_competition_bootstrap_packet.jsonl"
AUDIT = OUT_DIR / "real_session_candidate_competition_bootstrap_audit.json"
DROPS = OUT_DIR / "real_session_candidate_competition_bootstrap_drops.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_SESSION_CANDIDATE_COMPETITION_BOOTSTRAP_PACKET_STAGE10103.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

CODE_EXTS = {".py", ".c", ".cc", ".cpp", ".cxx", ".cu", ".h", ".hh", ".hpp", ".hxx", ".js", ".jsx", ".ts", ".tsx", ".html"}
ENTRYPOINT_NAMES = {"index.html", "index.js", "index.ts", "main.py", "main.js", "main.ts", "app.py", "app.js", "app.ts", "server.py", "server.js"}
OPAQUE_IDS = ("A", "B", "C", "D")


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
    rows = [
        row
        for row in registry.get("rows", [])
        if row.get("stage") != STAGE and row.get("stage_name") != NAME
    ]
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


def _visible_preview_by_path(row: dict[str, Any]) -> dict[str, dict[str, str]]:
    previews: dict[str, dict[str, str]] = {}
    for preview in row.get("visible_evidence_preview") or []:
        if not isinstance(preview, dict):
            continue
        path_text = str(preview.get("path", "")).strip()
        if path_text and path_text not in previews:
            previews[path_text] = {
                "role": str(preview.get("role", "")).strip(),
                "text_preview": str(preview.get("text_preview", "")).strip(),
            }
    return previews


def _redact_path(path_text: str) -> str:
    suffix = Path(path_text).suffix.lower() or "<none>"
    stem = Path(path_text).stem[:24]
    return f"{stem}:{suffix}"


def _candidate_payload(candidate_type: str, path_text: str, preview: dict[str, str], ordinal: int) -> dict[str, Any]:
    return {
        "candidate_surface_family": candidate_type,
        "candidate_label_hint": f"{candidate_type.lower()}_{ordinal}",
        "redacted_path_hint": _redact_path(path_text),
        "evidence_role": preview.get("role", ""),
        "snippet_preview": preview.get("text_preview", "")[:220],
    }


def _opaque_order(seed: str, count: int) -> list[str]:
    labels = list(OPAQUE_IDS[:count])
    labels.sort(key=lambda label: hashlib.sha256(f"{seed}:{label}".encode("utf-8")).hexdigest())
    return labels


def _python_candidates(row: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    previews = _visible_preview_by_path(row)
    impl_path = next((path for path in row.get("change_paths") or [] if Path(str(path)).suffix.lower() == ".py"), "")
    test_path = next((path for path in row.get("selected_tests") or [] if str(path).strip()), "")
    if not impl_path:
        return [], "missing_python_implementation_path"
    if not test_path:
        return [], "missing_python_selected_test"
    impl_preview = previews.get(str(impl_path))
    if not impl_preview:
        return [], "missing_python_implementation_preview"
    test_preview = {"role": "verification_target", "text_preview": f"Verification target: {Path(str(test_path)).name}"}
    return [
        _candidate_payload("IMPLEMENTATION", str(impl_path), impl_preview, 1),
        _candidate_payload("TEST", str(test_path), test_preview, 2),
    ], ""


def _cpp_candidates(row: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    previews = _visible_preview_by_path(row)
    code_paths = [
        str(path)
        for path in row.get("change_paths") or []
        if Path(str(path)).suffix.lower() in {".cpp", ".cu", ".cc", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
    ]
    unique: list[str] = []
    for path_text in code_paths:
        if path_text not in unique:
            unique.append(path_text)
    candidates: list[dict[str, Any]] = []
    for ordinal, path_text in enumerate(unique, start=1):
        preview = previews.get(path_text)
        if preview:
            candidates.append(_candidate_payload("IMPLEMENTATION", path_text, preview, ordinal))
        if len(candidates) >= 2:
            break
    if len(candidates) < 2:
        return [], "insufficient_cpp_code_candidates"
    return candidates[:2], ""


def _web_candidates(row: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    previews = _visible_preview_by_path(row)
    paths = [str(path) for path in row.get("change_paths") or [] if Path(str(path)).suffix.lower() in CODE_EXTS]
    entry_path = next((path for path in paths if Path(path).name.lower() in ENTRYPOINT_NAMES), "")
    impl_path = next((path for path in paths if path != entry_path and Path(path).name.lower() not in ENTRYPOINT_NAMES), "")
    if not entry_path:
        return [], "missing_web_entrypoint_path"
    if not impl_path:
        return [], "missing_web_implementation_path"
    entry_preview = previews.get(entry_path)
    impl_preview = previews.get(impl_path)
    if not entry_preview or not impl_preview:
        return [], "missing_web_preview"
    return [
        _candidate_payload("ENTRYPOINT", entry_path, entry_preview, 1),
        _candidate_payload("IMPLEMENTATION", impl_path, impl_preview, 2),
    ], ""


def _materialize_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    template = str(row.get("competition_template", "")).strip()
    if template == "python_file_vs_test":
        candidates, reason = _python_candidates(row)
    elif template == "cpp_file_vs_file":
        candidates, reason = _cpp_candidates(row)
    elif template == "web_entrypoint_vs_file":
        candidates, reason = _web_candidates(row)
    else:
        return None, "unsupported_template"
    if reason:
        return None, reason
    opaque_ids = _opaque_order(str(row.get("episode_id", "")), len(candidates))
    opaque_candidates = []
    for opaque_id, candidate in zip(opaque_ids, candidates):
        opaque_candidates.append({"candidate_id": opaque_id, **candidate})
    materialized = {
        "row_id": f"stage10103::{row.get('episode_id')}",
        "episode_id": row.get("episode_id"),
        "repo_id": row.get("repo_id"),
        "language_family": row.get("language_family"),
        "competition_template": template,
        "prompt_surface": {
            "task_observation": "A repository maintenance check failed after recent edits. Use only the visible evidence to choose the most plausible candidate surface to inspect or edit first.",
            "visible_evidence": [candidate["snippet_preview"] for candidate in opaque_candidates],
            "candidate_choices": [
                {
                    "candidate_id": candidate["candidate_id"],
                    "surface_family": candidate["candidate_surface_family"],
                    "evidence_role": candidate["evidence_role"],
                    "snippet_preview": candidate["snippet_preview"],
                }
                for candidate in opaque_candidates
            ],
            "return_protocol": "return_only_the_candidate_id",
        },
        "hidden_metadata": {
            "redacted_candidates": opaque_candidates,
            "requires_expert_maintainer_identifiability_review": True,
            "requires_gold_label_adjudication_before_training_or_scoring": True,
            "raw_change_paths_withheld_from_prompt": True,
        },
    }
    return materialized, ""


def build() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    request = load_json(REQUEST)
    source_rows = load_jsonl(SOURCE)
    packet_rows: list[dict[str, Any]] = []
    dropped_rows: list[dict[str, Any]] = []
    template_counts = Counter()
    language_counts = Counter()
    for row in source_rows:
        materialized, reason = _materialize_row(row)
        if materialized is None:
            dropped_rows.append(
                {
                    "episode_id": row.get("episode_id"),
                    "language_family": row.get("language_family"),
                    "competition_template": row.get("competition_template"),
                    "drop_reason": reason,
                }
            )
            continue
        packet_rows.append(materialized)
        template_counts[str(materialized.get("competition_template") or "")] += 1
        language_counts[str(materialized.get("language_family") or "")] += 1
    metrics = {
        "request_rows": int((request.get("metrics") or {}).get("requested_rows", 0) or 0),
        "materialized_rows": len(packet_rows),
        "dropped_rows": len(dropped_rows),
        "template_counts": dict(sorted(template_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "drop_reason_counts": dict(sorted(Counter(str(row.get("drop_reason") or "") for row in dropped_rows).items())),
        "all_materialized_rows_use_opaque_candidate_ids": all(
            all(choice.get("candidate_id") in OPAQUE_IDS for choice in ((row.get("prompt_surface") or {}).get("candidate_choices") or []))
            for row in packet_rows
        ),
        "all_materialized_rows_hide_raw_change_paths": all(
            bool((row.get("hidden_metadata") or {}).get("raw_change_paths_withheld_from_prompt"))
            for row in packet_rows
        ),
    }
    failures: list[str] = []
    if not packet_rows:
        failures.append("no_rows_materialized")
    claim_boundary = {
        "supports_training_or_scoring_now": False,
        "supports_expert_review_bootstrap": bool(packet_rows),
        "gold_labels_still_missing": True,
        "web_rows_underpowered_after_materialization": int(template_counts.get("web_entrypoint_vs_file", 0)) < 5,
        "rust_rows_still_missing": True,
    }
    next_best_step = (
        "Attach maintainer adjudication and gold labels to the materialized packet, then rerun a shortcut baseline on the adjudicated packet before any training or Gemma comparison uses it."
    )
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifacts": {
            "source_request_rows": display(SOURCE),
            "request": display(REQUEST),
            "bootstrap_packet": display(PACKET),
            "drops": display(DROPS),
        },
        "intent": "Materialize a provisional real-session candidate-competition packet with opaque candidates and explicit drop reasons, without pretending that gold adjudication or maintainer signoff already exists.",
        "metrics": metrics,
        "claim_boundary": claim_boundary,
        "failures": failures,
        "next_best_step": next_best_step,
    }
    return audit, packet_rows, dropped_rows


def write_doc(audit: dict[str, Any]) -> None:
    metrics = audit["metrics"]
    lines = [
        "# Stage10103 Real Session Candidate Competition Bootstrap Packet",
        "",
        f"Passed: `{audit['passed']}`",
        f"Materialized rows: `{metrics['materialized_rows']}`",
        f"Dropped rows: `{metrics['dropped_rows']}`",
        f"Template counts: `{metrics['template_counts']}`",
        f"Drop reasons: `{metrics['drop_reason_counts']}`",
        "",
        "This stage turns the stage10102 request into a provisional packet with real source snippets and opaque candidate IDs. It remains review-only: there are still no adjudicated gold labels, Web only partially survives the two-candidate requirement, and Rust is still absent.",
        "",
        f"Next: {audit['next_best_step']}",
        "",
    ]
    DOC.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    audit, rows, drops = build()
    write_json(AUDIT, audit)
    write_jsonl(PACKET, rows)
    write_jsonl(DROPS, drops)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "artifacts": audit["artifacts"],
        "metrics": audit["metrics"],
        "next_best_step": audit["next_best_step"],
    }
    write_json(SUMMARY, summary)
    write_doc(audit)
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": audit["failures"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
