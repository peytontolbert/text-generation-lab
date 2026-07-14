#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11285
NAME = "stage11285_candidate_only_evidence_judgment_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "candidate_only_evidence_judgment_package.json"
TRAIN_JSONL = OUT_DIR / "candidate_only_evidence_judgment_train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "candidate_only_evidence_judgment_validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "candidate_only_evidence_judgment_strict_rows.jsonl"

SOURCE_DIR = ARTIFACTS / "stage11276_capped_direct_retrieval_evidence_package"
SOURCE_ROWS = {
    "train": SOURCE_DIR / "capped_direct_retrieval_evidence_train_rows.jsonl",
    "validation": SOURCE_DIR / "capped_direct_retrieval_evidence_validation_rows.jsonl",
    "strict_eval": SOURCE_DIR / "capped_direct_retrieval_evidence_strict_rows.jsonl",
}


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def make_prompt(row: dict[str, Any]) -> str:
    source = row.get("standalone_projection_source") or {}
    evidence_text = str(source.get("candidate_evidence_text") or "")
    options = row.get("opaque_options") or []
    return "\n".join([
        f"Language: {row.get('language_family')}",
        "Perspective: evidence_candidate_judgment",
        "Decision objective: classify only the candidate evidence item below.",
        "Do not use repository family, source row identity, option order, or any hidden role metadata.",
        "The candidate may be changed-source support, verifier/test evidence, symptom/call-path support, or background context.",
        "",
        "Candidate evidence item:",
        evidence_text,
        "",
        "Options:",
        *[f"{opt['label']}. {opt['value']}" for opt in options],
        "Answer:",
    ])


def rewrite_row(row: dict[str, Any], split: str) -> dict[str, Any]:
    out = dict(row)
    out["row_id"] = str(row["row_id"]).replace("stage11275::", "stage11285::").replace(
        "::direct_retrieval_evidence_candidate_judgment::",
        "::candidate_only_evidence_judgment::",
    )
    out["surface"] = "maintainer_candidate_only_source_evidence_judgment_bounded_choice"
    out["input_text"] = make_prompt(row)
    out["prompt_text"] = out["input_text"]
    out["split"] = split
    out["package_split"] = split
    out["strict_eval_eligible"] = split == "strict_eval"
    out["train_support_only"] = split == "train"
    anti = dict(out.get("anti_cheat") or {})
    anti.update({
        "candidate_only_prompt": True,
        "root_route_fields_removed": True,
        "available_role_list_removed": True,
        "source_row_identity_removed_from_prompt": True,
    })
    out["anti_cheat"] = anti
    source = dict(out.get("standalone_projection_source") or {})
    source["source_inventory_stage"] = "stage11285_candidate_only_rewrite_from_stage11276"
    source["prompt_rewrite"] = "candidate_only_no_root_route_or_available_roles"
    out["standalone_projection_source"] = source
    return out


def leak_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    leaks = Counter()
    for row in rows:
        prompt_before_options = str(row.get("input_text") or "").split("Options:", 1)[0]
        source = row.get("standalone_projection_source") or {}
        target_label = str(row.get("bounded_choice_target_label") or "")
        if f"\n{target_label}." in prompt_before_options or f" {target_label}. " in prompt_before_options:
            leaks["target_label_before_options"] += 1
        if str(row.get("semantic_target_value") or "") in prompt_before_options:
            leaks["semantic_target_before_options"] += 1
        for bad in ["Verifier route:", "Execution route:", "Available local evidence roles:", "Source row:"]:
            if bad in prompt_before_options:
                leaks["root_route_or_identity_field_present"] += 1
    root_sets: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        root_sets[str(row.get("split"))].add(str(row.get("root_id")))
    return {
        "duplicate_row_ids": len(rows) - len({str(row.get("row_id")) for row in rows}),
        "leaks": dict(leaks),
        "root_overlap": {
            "train_validation": sorted(root_sets["train"] & root_sets["validation"]),
            "train_strict": sorted(root_sets["train"] & root_sets["strict_eval"]),
            "validation_strict": sorted(root_sets["validation"] & root_sets["strict_eval"]),
        },
    }


def counts(rows_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for split, rows in rows_by_split.items():
        out[split] = {
            "rows": len(rows),
            "roots": len({str(row.get("root_id")) for row in rows}),
            "by_language": dict(Counter(str(row.get("language_family")) for row in rows)),
            "by_target": dict(Counter(str(row.get("semantic_target_value")) for row in rows)),
            "by_candidate_kind": dict(Counter(str((row.get("standalone_projection_source") or {}).get("candidate_evidence_kind")) for row in rows)),
        }
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows_by_split: dict[str, list[dict[str, Any]]] = {}
    for split, path in SOURCE_ROWS.items():
        rows_by_split[split] = [rewrite_row(row, split) for row in load_jsonl(path)]

    all_rows = [row for rows in rows_by_split.values() for row in rows]
    audit = leak_audit(all_rows)
    passed = audit["duplicate_row_ids"] == 0 and not audit["leaks"] and not any(audit["root_overlap"].values())

    write_jsonl(TRAIN_JSONL, rows_by_split["train"])
    write_jsonl(VALIDATION_JSONL, rows_by_split["validation"])
    write_jsonl(STRICT_JSONL, rows_by_split["strict_eval"])
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": passed,
        "decision": "candidate_only_evidence_judgment_package_ready" if passed else "candidate_only_evidence_judgment_package_blocked",
        "rationale": "Remove root-level verifier route, available-role list, and source-row identity from Stage11276 prompts so the model must classify the candidate evidence item itself.",
        "counts": counts(rows_by_split),
        "audit": audit,
        "outputs": {
            "train_jsonl": rel(TRAIN_JSONL),
            "validation_jsonl": rel(VALIDATION_JSONL),
            "strict_jsonl": rel(STRICT_JSONL),
            "summary_json": rel(SUMMARY_JSON),
        },
        "source_artifacts": {
            "stage11276_package": rel(SOURCE_DIR / "capped_direct_retrieval_evidence_package.json"),
            "stage11284_bias_audit": "runs/local/artifacts/stage11284_capped_direct_retrieval_evidence_bias_audit/capped_direct_retrieval_evidence_bias_audit.json",
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
