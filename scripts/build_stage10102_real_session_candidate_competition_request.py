#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10102
NAME = "stage10102_real_session_candidate_competition_request"
SOURCE = ROOT / "runs/local/artifacts/stage10101_real_session_edit_localization_bootstrap_shortcut_audit/real_session_edit_localization_bootstrap_shortcut_rows.jsonl"
SHORTCUT_AUDIT = ROOT / "runs/local/artifacts/stage10101_real_session_edit_localization_bootstrap_shortcut_audit/real_session_edit_localization_bootstrap_shortcut_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "real_session_candidate_competition_request.json"
ROWS = OUT_DIR / "real_session_candidate_competition_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_SESSION_CANDIDATE_COMPETITION_REQUEST_STAGE10102.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

CODE_EXTS = {".py", ".c", ".cc", ".cpp", ".cxx", ".cu", ".h", ".hh", ".hpp", ".hxx", ".js", ".jsx", ".ts", ".tsx", ".html"}


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
    registry["rows"] = sorted(
        rows,
        key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")),
    )
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


def _combo(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(str(item) for item in (row.get("candidate_target_families") or []) if str(item)))


def _code_like_paths(row: dict[str, Any]) -> list[str]:
    paths = [str(path_text) for path_text in (row.get("change_paths") or []) if str(path_text)]
    return [path_text for path_text in paths if Path(path_text).suffix.lower() in CODE_EXTS]


def _select_template(row: dict[str, Any]) -> str:
    language = str(row.get("language_family") or "")
    combo = _combo(row)
    if language == "python" and combo == ("TARGET_FILE", "TARGET_TEST"):
        return "python_file_vs_test"
    if language == "web_js_ts_html" and combo == ("TARGET_ENTRYPOINT", "TARGET_FILE"):
        return "web_entrypoint_vs_file"
    if language == "c_cpp" and combo == ("TARGET_FILE",) and len(_code_like_paths(row)) >= 2:
        return "cpp_file_vs_file"
    return ""


def _candidate_rules(template: str) -> list[str]:
    if template == "python_file_vs_test":
        return [
            "Include at least one changed implementation file candidate and one selected-test candidate.",
            "Require visible failure/assertion evidence strong enough to distinguish implementation change from stale test expectation.",
            "Hide raw changed-path list from the model-visible surface unless paths are balanced across candidates.",
        ]
    if template == "web_entrypoint_vs_file":
        return [
            "Include an entrypoint candidate and an implementation-file candidate with opaque candidate IDs.",
            "Expose only balanced snippet evidence, not the raw one-file change list that trivially implies the answer.",
            "Require a visible runtime or behavior cue that distinguishes page entrypoint wiring from implementation logic.",
        ]
    if template == "cpp_file_vs_file":
        return [
            "Construct multiple file candidates from the changed C++/CUDA implementation set, not one singleton file label.",
            "Require visible trace, symbol, or call-site evidence to choose among competing native files.",
            "Suppress direct changed-path signature leakage by balancing file-extension/profile cues across candidates.",
        ]
    return []


def build() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_rows = load_jsonl(SOURCE)
    shortcut_audit = load_json(SHORTCUT_AUDIT)
    request_rows: list[dict[str, Any]] = []
    template_counts = Counter()
    language_counts = Counter()
    for row in source_rows:
        template = _select_template(row)
        if not template:
            continue
        request_row = {
            "episode_id": row.get("episode_id"),
            "repo_id": row.get("repo_id"),
            "language_family": row.get("language_family"),
            "competition_template": template,
            "candidate_target_families": row.get("candidate_target_families"),
            "change_paths": row.get("change_paths"),
            "selected_tests": row.get("selected_tests"),
            "visible_evidence_preview": row.get("visible_evidence_preview"),
            "context_role_counts": row.get("context_role_counts"),
            "shortcut_signature": row.get("changed_path_signature"),
            "candidate_construction_rules": _candidate_rules(template),
            "anti_shortcut_requirements": [
                "opaque_candidate_ids",
                "candidate_permutation",
                "balanced_path_exposure",
                "no_raw_changed_path_list_in_prompt",
                "same-template_signature_baseline_below_threshold",
                "expert_maintainer_identifiability_review",
            ],
        }
        request_rows.append(request_row)
        template_counts[template] += 1
        language_counts[str(row.get("language_family") or "")] += 1
    failures: list[str] = []
    if not request_rows:
        failures.append("no_candidate_competition_rows_selected")
    metrics = {
        "requested_rows": len(request_rows),
        "template_counts": dict(sorted(template_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "stage10101_changed_path_signature_majority_exact": ((shortcut_audit.get("metrics") or {}).get("changed_path_signature_majority_exact_on_unique_rows")),
        "rust_rows_available_for_competition": int(language_counts.get("rust", 0)),
        "web_rows_available_for_competition": int(language_counts.get("web_js_ts_html", 0)),
    }
    claim_boundary = {
        "bootstrap_candidate_competition_ready_for_python_c_cpp_web": bool(
            template_counts.get("python_file_vs_test", 0) > 0
            and template_counts.get("cpp_file_vs_file", 0) > 0
            and template_counts.get("web_entrypoint_vs_file", 0) > 0
        ),
        "four_language_maintainer_claim_ready": False,
        "rust_replenishment_required": True,
        "training_on_current_real_session_rows_without_competition_is_disallowed": True,
    }
    next_best_step = (
        "Materialize these candidate-competition rows with opaque candidate IDs and rerun a shortcut audit; only train or compare models on the resulting packet if the changed-path baseline no longer solves the task."
    )
    request = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifacts": {
            "stage10101_rows": display(SOURCE),
            "stage10101_shortcut_audit": display(SHORTCUT_AUDIT),
            "request_rows": display(ROWS),
        },
        "intent": "Turn the real-session evidence reservoir into explicit candidate-competition requests so maintainer-grade edit localization is no longer recoverable from changed-path signatures alone.",
        "metrics": metrics,
        "claim_boundary": claim_boundary,
        "failures": failures,
        "next_best_step": next_best_step,
    }
    return request, request_rows


def write_doc(request: dict[str, Any]) -> None:
    metrics = request["metrics"]
    lines = [
        "# Stage10102 Real Session Candidate Competition Request",
        "",
        f"Passed: `{request['passed']}`",
        f"Requested rows: `{metrics['requested_rows']}`",
        f"Template counts: `{metrics['template_counts']}`",
        f"Language counts: `{metrics['language_counts']}`",
        "",
        "This stage promotes the real-session inventory from a raw evidence reservoir to a candidate-competition request. The request is still bootstrap-only: Python uses file-vs-test competition, Web uses entrypoint-vs-file competition, and C/C++ uses file-vs-file competition over changed native sources. Rust still requires fresh source-backed roots.",
        "",
        f"Next: {request['next_best_step']}",
        "",
    ]
    DOC.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    request, rows = build()
    write_json(REQUEST, request)
    write_jsonl(ROWS, rows)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": request["passed"],
        "artifacts": request["artifacts"],
        "metrics": request["metrics"],
        "next_best_step": request["next_best_step"],
    }
    write_json(SUMMARY, summary)
    write_doc(request)
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": request["passed"], "failures": request["failures"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
