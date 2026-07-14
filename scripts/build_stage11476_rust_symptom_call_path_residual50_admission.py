#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"

STAGE = 11476
NAME = "stage11476_rust_symptom_call_path_residual50_admission"
OUT = ART / NAME
SUMMARY = OUT / "rust_symptom_call_path_residual50_admission.json"
CANDIDATES = OUT / "rust_symptom_call_path_candidates.jsonl"
ADMITTED = OUT / "admitted_rust_symptom_call_path_rows.jsonl"
BLOCKED = OUT / "blocked_rust_symptom_call_path_rows.jsonl"

SOURCE_FILES = [
    ART / "stage10782_targeted_residual_support_probe_request/targeted_residual_support_probe_manifest.jsonl",
    ART / "stage10801_python_plus_rust_competition_support_probe_request/python_plus_rust_competition_support_probe_manifest.jsonl",
    ART / "stage11181_contract_evidence_support_probe_request/contract_evidence_support_probe_manifest.jsonl",
    ART / "stage11209_fresh_verifier_constraint_preserved_probe_request/fresh_verifier_constraint_preserved_probe_manifest.jsonl",
    ART / "stage11213_evidence_fact_text_probe_request/evidence_fact_text_probe_manifest.jsonl",
    ART / "stage11436_full_coverage_semantic_candidate_package/agentkernel_lite_encdec_train.jsonl",
]
STRICT_FORBIDDEN = [
    ART / "stage11193_rust_external_graph_replacement_rows/rust_replacement_strict_candidate_rows.jsonl",
    ART / "stage11436_full_coverage_semantic_candidate_package/semantic_candidate_residual_bank.jsonl",
]

TARGET_ROLE = "symptom_or_call_path_analogue"
FORBIDDEN_REPO_FAMILIES = {"tokenizers"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def gold_value(row: dict[str, Any]) -> str:
    return str((row.get("standalone_projection_source") or {}).get("gold_value") or row.get("semantic_target_value") or "")


def option_values(row: dict[str, Any]) -> set[str]:
    options = row.get("opaque_options") or (row.get("standalone_projection_source") or {}).get("opaque_options") or []
    return {str(option.get("value")) for option in options if isinstance(option, dict)}


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id"))


def train_forbidden(row: dict[str, Any]) -> bool:
    anti = row.get("anti_cheat") or {}
    split = row.get("split") or row.get("package_split") or row.get("split_role")
    return bool(
        anti.get("not_train_support")
        or row.get("strict_eval_eligible") is True
        or split in {"strict_eval", "strict_candidate"}
    )


def has_rust_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in [".rs", "cargo", "rust", "fn ", "mod ", "use "])


def has_anchor(row: dict[str, Any], text: str) -> bool:
    anti = row.get("anti_cheat") or {}
    return bool(
        row.get("selected_test_anchor")
        or row.get("verifier_anchor")
        or row.get("selected_test_anchor_present")
        or row.get("selected_verifier_anchor_present")
        or row.get("selected_tests")
        or anti.get("explicit_selected_test_ledger")
        or anti.get("selected_test_anchor_present")
        or anti.get("selected_verifier_anchor_present")
        or "verifier_and_test_constraint" in text
        or "selected-test" in text.lower()
    )


def evidence_text_after_key(text: str, key: str) -> str:
    marker = f"{key} "
    if marker not in text:
        marker = f"{key} ["
    idx = text.find(marker)
    if idx < 0:
        return ""
    tail = text[idx:]
    stop_candidates = [tail.find("\n" + other) for other in [
        "candidate_change_surface",
        "symptom_or_call_path_analogue",
        "verifier_and_test_constraint",
        "nearby_definition_or_usage_context",
        "algorithmic_background_reference",
        "external_analogue_reference",
    ] if other != key]
    stops = [pos for pos in stop_candidates if pos > 0]
    return tail[: min(stops)] if stops else tail[:1200]


def distinct_candidate_and_symptom(text: str) -> bool:
    candidate = evidence_text_after_key(text, "candidate_change_surface")
    symptom = evidence_text_after_key(text, TARGET_ROLE)
    if not candidate or not symptom:
        return False
    return candidate.strip()[:240] != symptom.strip()[:240]


def normalize_row(row: dict[str, Any], source_path: Path) -> dict[str, Any]:
    out = dict(row)
    out["split"] = "train"
    out["package_split"] = "train"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["residual50_family_id"] = "rust_symptom_call_path_vs_candidate_surface"
    out["source_artifact"] = rel(source_path)
    anti = dict(out.get("anti_cheat") or {})
    anti["train_support_only"] = True
    anti["rust_symptom_call_path_residual50_admitted"] = True
    anti["reserved_eval_lineage_excluded"] = True
    out["anti_cheat"] = anti
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    forbidden_roots = set()
    for path in STRICT_FORBIDDEN:
        for row in iter_jsonl(path):
            forbidden_roots.add(root_id(row))
            forbidden_roots.add(str(row.get("source_root_id") or ""))

    raw_candidates: list[dict[str, Any]] = []
    for path in SOURCE_FILES:
        for row in iter_jsonl(path):
            if row.get("language_family") != "rust":
                continue
            if gold_value(row) != TARGET_ROLE:
                continue
            candidate = dict(row)
            candidate["_source_artifact"] = rel(path)
            raw_candidates.append(candidate)

    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    admitted_roots: set[str] = set()
    admitted_repos: Counter[str] = Counter()
    for candidate in raw_candidates:
        text = str(candidate.get("input_text") or candidate.get("prompt_text") or "")
        rid = root_id(candidate)
        repo = str(candidate.get("repo_family") or "unknown")
        reasons: list[str] = []
        if train_forbidden(candidate):
            reasons.append("reserved_or_eval_row")
        if rid in forbidden_roots:
            reasons.append("strict_or_residual_lineage")
        if repo in FORBIDDEN_REPO_FAMILIES:
            reasons.append("forbidden_weak_or_quarantined_repo_family")
        opts = option_values(candidate)
        if TARGET_ROLE not in opts or "candidate_change_surface" not in opts:
            reasons.append("missing_required_competing_roles")
        if not has_rust_marker(text):
            reasons.append("missing_rust_material_marker")
        if not has_anchor(candidate, text):
            reasons.append("missing_selected_test_or_verifier_anchor")
        if not distinct_candidate_and_symptom(text):
            reasons.append("candidate_and_symptom_evidence_not_distinct")
        if rid in admitted_roots:
            reasons.append("duplicate_root")
        if admitted_repos[repo] >= 4:
            reasons.append("repo_family_cap")

        if reasons:
            blocked_row = dict(candidate)
            blocked_row["block_reasons"] = reasons
            blocked.append(blocked_row)
            continue

        source_path = ROOT / str(candidate.pop("_source_artifact"))
        row = normalize_row(candidate, source_path)
        admitted.append(row)
        admitted_roots.add(rid)
        admitted_repos[repo] += 1

    # Prefer breadth and keep the target shape bounded.
    admitted = admitted[:10]
    admitted_root_ids = {root_id(row) for row in admitted}
    extra_admitted = [
        row for row in blocked
        if root_id(row) in admitted_root_ids and "duplicate_root" in row.get("block_reasons", [])
    ]

    write_jsonl(CANDIDATES, raw_candidates)
    write_jsonl(ADMITTED, admitted)
    write_jsonl(BLOCKED, blocked + extra_admitted)

    by_repo = Counter(row.get("repo_family") for row in admitted)
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": len(admitted) >= 10,
        "decision": "rust_symptom_call_path_residual50_admitted"
        if len(admitted) >= 10
        else "rust_symptom_call_path_residual50_still_short",
        "metrics": {
            "raw_candidates": len(raw_candidates),
            "admitted_rows": len(admitted),
            "admitted_unique_roots": len({root_id(row) for row in admitted}),
            "admitted_unique_repos": len(by_repo),
            "admitted_by_repo": dict(sorted(by_repo.items())),
            "blocked_rows": len(blocked),
            "forbidden_roots": len(forbidden_roots),
        },
        "admission_contract": {
            "language_family": "rust",
            "gold_value": TARGET_ROLE,
            "requires_candidate_change_surface_hard_negative": True,
            "requires_rust_material_marker": True,
            "requires_selected_test_or_verifier_anchor": True,
            "requires_distinct_candidate_and_symptom_text": True,
            "excludes_reserved_eval_lineage": True,
            "excludes_forbidden_repo_families": sorted(FORBIDDEN_REPO_FAMILIES),
        },
        "source_artifacts": {
            "source_files": [rel(path) for path in SOURCE_FILES],
            "strict_forbidden": [rel(path) for path in STRICT_FORBIDDEN],
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "candidates": rel(CANDIDATES),
            "admitted": rel(ADMITTED),
            "blocked": rel(BLOCKED),
        },
    }
    write_json(SUMMARY, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
