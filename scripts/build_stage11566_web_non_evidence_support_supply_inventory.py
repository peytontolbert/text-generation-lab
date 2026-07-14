#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11566
NAME = "stage11566_web_non_evidence_support_supply_inventory"
OUT = ART / NAME
SUMMARY = OUT / "web_non_evidence_support_supply_inventory.json"
CANDIDATES = OUT / "web_non_evidence_support_candidates.jsonl"
REJECTIONS = OUT / "web_non_evidence_support_rejections.jsonl"

WEB_HELDOUT = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"
FILTERED_VALIDATION = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl"
FILTERED_STRICT = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
OLD_VALIDATION = ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl"
OLD_STRICT = ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl"

EXCLUDE_STAGE_NAMES = {
    "stage11548_web_root_heldout_stage11507_score_audit",
    "stage11549_web_root_heldout_same_manifest_gemma_comparison",
    "stage11564_conservative_openhands_postrun_gate_audit",
    "stage11559_expanded_text_rich_bridge_postrun_gate_audit",
}
NON_EVIDENCE_TASKS = {
    "symptom_localization",
    "verifier_outcome",
    "minimal_fix_selection",
    "alternative_hypothesis_elimination",
    "abstention_insufficient_evidence",
    "patch_impact",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows=[]
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            obj=json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True)+"\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True)+"\n" for row in rows), encoding="utf-8")


def root_id(row: dict[str, Any]) -> str:
    rid = row.get("root_id") or row.get("source_bundle_id")
    if rid:
        return str(rid)
    row_id = str(row.get("row_id") or "")
    parts = row_id.split("::")
    return "::".join(parts[:2]) if len(parts) >= 2 else row_id


def task_type(row: dict[str, Any]) -> str:
    task = str(row.get("task_type") or "")
    if task:
        return task
    row_id = str(row.get("row_id") or "")
    parts = row_id.split("::")
    if not parts:
        return ""
    val = parts[-1]
    if val in {"heldout_v1", "train_v1", "reviewed_v27_compact"} and len(parts) >= 2:
        val = parts[-2]
    return val


def repo_family(row: dict[str, Any]) -> str:
    val = str(row.get("repo_family") or "")
    if val:
        return val
    rid = str(row.get("row_id") or root_id(row))
    if "openhands" in rid:
        return "openhands"
    if "llama_stack" in rid:
        return "llama_stack"
    if "mcp" in rid or "modelcontextprotocol" in rid:
        return "modelcontextprotocol_typescript_sdk"
    if "sep_automation" in rid:
        return "sep_automation"
    if "openclaw" in rid or "convex" in rid:
        return "convex"
    if "sourcebot" in rid:
        return "sourcebot"
    if "bddy" in rid or "website" in rid:
        return "bddy_website"
    return "unknown"


def options(row: dict[str, Any]) -> list[Any]:
    src = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    opts = src.get("opaque_options") or row.get("opaque_options") or row.get("options") or []
    return opts if isinstance(opts, list) else []


def target_label(row: dict[str, Any]) -> str:
    for key in ["bounded_choice_target_label", "target_text", "decoder_text"]:
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    tgt = row.get("target")
    if isinstance(tgt, dict):
        for key in ["bounded_choice_target_label", "decoder_text", "target_text"]:
            val = tgt.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


def is_web(row: dict[str, Any]) -> bool:
    if str(row.get("language_family") or "") == "web_js_ts_html":
        return True
    rid = str(row.get("row_id") or "")
    return any(tok in rid for tok in ["web_js_ts_html", "openhands", "llama_stack", "mcp_typescript", "sep_automation", "openclaw", "sourcebot", "bddy_website"])


def is_support_only(row: dict[str, Any]) -> bool:
    ac = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    if ac.get("not_strict_eval_eligible") is True or ac.get("train_support_only") is True:
        return True
    split = str(row.get("split") or "")
    rid = str(row.get("row_id") or "")
    return split == "train" or "train_support" in rid or "support" in rid


def has_verifier_anchor(row: dict[str, Any]) -> bool:
    text = json.dumps(row, sort_keys=True).lower()
    return any(tok in text for tok in ["verifier", "test", "vitest", "pytest", "selected", "assert", "expected", "fail_to_pass"])


def rejection(row: dict[str, Any], protected_roots: set[str]) -> str | None:
    if not is_web(row):
        return "not_web"
    task = task_type(row)
    if task not in NON_EVIDENCE_TASKS:
        return "not_non_evidence_task"
    if root_id(row) in protected_roots:
        return "protected_root_overlap"
    if not is_support_only(row):
        return "not_train_support_only"
    opts = options(row)
    if len(opts) < 2:
        return "too_few_options"
    if not target_label(row):
        return "missing_target_label"
    labels = {str(opt.get("label") or opt.get("id") or "") for opt in opts if isinstance(opt, dict)}
    if target_label(row) not in labels:
        return "target_label_not_in_options"
    if not has_verifier_anchor(row):
        return "missing_verifier_or_test_anchor"
    return None


def main() -> None:
    protected = set()
    for path in [WEB_HELDOUT, FILTERED_VALIDATION, FILTERED_STRICT, OLD_VALIDATION, OLD_STRICT]:
        protected.update(root_id(row) for row in load_jsonl(path))
    candidates_by_id: dict[str, dict[str, Any]] = {}
    rejections: list[dict[str, Any]] = []
    scanned_files = 0
    scanned_rows = 0
    for path in ART.glob("stage*/**/*.jsonl"):
        stage_dir = next((part for part in path.parts if part.startswith("stage")), "")
        if stage_dir in EXCLUDE_STAGE_NAMES:
            continue
        rows = load_jsonl(path)
        if not rows:
            continue
        scanned_files += 1
        for row in rows:
            scanned_rows += 1
            reason = rejection(row, protected)
            if reason is None:
                item = dict(row)
                item["stage11566_source_path"] = rel(path)
                item["stage11566_root_id"] = root_id(row)
                item["stage11566_task_type"] = task_type(row)
                item["stage11566_repo_family"] = repo_family(row)
                candidates_by_id.setdefault(str(item.get("row_id") or f"{root_id(row)}::{task_type(row)}"), item)
            elif is_web(row) and task_type(row) in NON_EVIDENCE_TASKS:
                rejections.append({"row_id": row.get("row_id"), "root_id": root_id(row), "task_type": task_type(row), "repo_family": repo_family(row), "reason": reason, "source_path": rel(path)})
    candidates = list(candidates_by_id.values())
    roots = {row["stage11566_root_id"] for row in candidates}
    by_task = Counter(row["stage11566_task_type"] for row in candidates)
    by_repo = Counter(row["stage11566_repo_family"] for row in candidates)
    roots_by_repo = defaultdict(set)
    for row in candidates:
        roots_by_repo[row["stage11566_repo_family"]].add(row["stage11566_root_id"])
    gates = {
        "at_least_20_rows": len(candidates) >= 20,
        "at_least_8_roots": len(roots) >= 8,
        "at_least_3_repo_families": len(roots_by_repo) >= 3,
        "has_openhands_support": any(row["stage11566_repo_family"] == "openhands" for row in candidates),
        "has_non_openhands_support": any(row["stage11566_repo_family"] != "openhands" for row in candidates),
        "all_root_disjoint_from_protected": all(row["stage11566_root_id"] not in protected for row in candidates),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": all(gates.values()),
        "decision": "web_non_evidence_support_supply_ready" if all(gates.values()) else "web_non_evidence_support_supply_insufficient",
        "metrics": {
            "scanned_files": scanned_files,
            "scanned_rows": scanned_rows,
            "candidate_rows": len(candidates),
            "candidate_roots": len(roots),
            "candidate_task_counts": dict(by_task),
            "candidate_repo_counts": dict(by_repo),
            "candidate_root_counts_by_repo": {k: len(v) for k, v in sorted(roots_by_repo.items())},
            "rejection_counts": dict(Counter(r["reason"] for r in rejections)),
        },
        "gates": gates,
        "claim_boundary": [
            "Inventory only; no training or promotion.",
            "Candidates are Web non-evidence train-support rows that are root-disjoint from Web heldout and protected canaries.",
            "Rows are not automatically sufficient for a broad Web claim; they are supply for a controlled package if admitted.",
        ],
        "source_artifacts": {
            "web_heldout": rel(WEB_HELDOUT),
            "filtered_validation": rel(FILTERED_VALIDATION),
            "filtered_strict": rel(FILTERED_STRICT),
            "old_validation": rel(OLD_VALIDATION),
            "old_strict": rel(OLD_STRICT),
        },
        "outputs": {"candidates": rel(CANDIDATES), "rejections": rel(REJECTIONS), "summary": rel(SUMMARY)},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(CANDIDATES, candidates)
    write_jsonl(REJECTIONS, rejections[:2000])
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARIES / f"{NAME}.json", summary)
    print(json.dumps({"decision": summary["decision"], "metrics": summary["metrics"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
