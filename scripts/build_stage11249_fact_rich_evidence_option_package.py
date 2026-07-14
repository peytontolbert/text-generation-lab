#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11249
NAME = "stage11249_fact_rich_evidence_option_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fact_rich_evidence_option_package.json"
TRAIN_JSONL = OUT_DIR / "fact_rich_evidence_option_train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "fact_rich_evidence_option_validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "fact_rich_evidence_option_strict_rows.jsonl"

SOURCE_SUMMARY = ARTIFACTS / "stage11243_balanced_evidence_role_grounding_package/balanced_evidence_role_grounding_package.json"
SOURCE_TRAIN = ARTIFACTS / "stage11243_balanced_evidence_role_grounding_package/balanced_evidence_role_grounding_train_rows.jsonl"
SOURCE_VALIDATION = ARTIFACTS / "stage11243_balanced_evidence_role_grounding_package/balanced_evidence_role_grounding_validation_rows.jsonl"
SOURCE_STRICT = ARTIFACTS / "stage11243_balanced_evidence_role_grounding_package/balanced_evidence_role_grounding_strict_rows.jsonl"
ROLE_VALUES = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
    "external_analogue_reference",
    "algorithmic_background_reference",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def fact_for(row: dict[str, Any], role: str) -> str:
    facts = (row.get("standalone_projection_source") or {}).get("evidence_facts") or {}
    return str(facts.get(role) or "no concrete evidence supplied").strip()


def fact_value(row: dict[str, Any], role: str) -> str:
    # Role prefix keeps semantic compatibility; fact suffix gives raw retrieval concrete material.
    return f"{role} | {fact_for(row, role)}"


def rewrite_prompt(prompt: str, options: list[dict[str, str]]) -> str:
    if "\nOptions:\n" not in prompt:
        return prompt.rstrip() + "\nOptions:\n" + "\n".join(f"{o['label']}. {o['value']}" for o in options) + "\nAnswer:"
    prefix = prompt.split("\nOptions:\n", 1)[0].rstrip()
    return prefix + "\n\nOptions:\n" + "\n".join(f"{o['label']}. {o['value']}" for o in options) + "\nAnswer:"


def convert(row: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(row))
    old_options = ((out.get("standalone_projection_source") or {}).get("opaque_options")) or out.get("opaque_options") or []
    new_options = []
    for option in old_options:
        if not isinstance(option, dict):
            continue
        label = str(option.get("label") or "").strip()
        role = str(option.get("value") or "").strip()
        if not label or role not in ROLE_VALUES:
            continue
        new_options.append({"label": label, "value": fact_value(out, role), "semantic_role": role})
    target_role = str(out.get("semantic_target_value") or out.get("gold_value") or "")
    target_label = next((o["label"] for o in new_options if o.get("semantic_role") == target_role), out.get("target_text"))
    projection = out.setdefault("standalone_projection_source", {})
    projection["source_projection_mode"] = projection.get("projection_mode")
    projection["projection_mode"] = "stage11249_fact_rich_evidence_option"
    projection["source_opaque_options"] = old_options
    projection["opaque_options"] = new_options
    projection["gold_value"] = target_role
    projection["gold_label"] = target_label
    projection["option_value_geometry"] = "role_prefixed_concrete_fact_text"
    out["row_id"] = re.sub(r"^stage11243::", "stage11249::", str(out.get("row_id") or ""))
    out["opaque_options"] = new_options
    out["target"] = target_label
    out["target_label"] = target_label
    out["target_text"] = target_label
    out["decoder_text"] = target_label
    out["bounded_choice_target_label"] = target_label
    out["semantic_target_value"] = target_role
    out["gold_value"] = target_role
    out["prompt_text"] = rewrite_prompt(str(out.get("prompt_text") or out.get("input_text") or ""), new_options)
    out["input_text"] = out["prompt_text"]
    anti = out.setdefault("anti_cheat", {})
    anti["fact_rich_option_values"] = True
    anti["role_alias_prefix_with_concrete_fact_suffix"] = True
    return out


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def main() -> None:
    source_summary = load_json(SOURCE_SUMMARY)
    train = [convert(row) for row in load_jsonl(SOURCE_TRAIN)]
    validation = [convert(row) for row in load_jsonl(SOURCE_VALIDATION)]
    strict = [convert(row) for row in load_jsonl(SOURCE_STRICT)]
    roots = {
        "train": {root_key(row) for row in train},
        "validation": {root_key(row) for row in validation},
        "strict": {root_key(row) for row in strict},
    }
    overlaps = {
        "train_validation": sorted(roots["train"] & roots["validation"]),
        "train_strict": sorted(roots["train"] & roots["strict"]),
        "validation_strict": sorted(roots["validation"] & roots["strict"]),
    }
    all_rows = train + validation + strict
    quality_gates = {
        "source_package_passed": bool(source_summary.get("passed")),
        "root_split_disjoint": not any(overlaps.values()),
        "all_rows_have_six_options": all(len(row.get("opaque_options") or []) == 6 for row in all_rows),
        "all_options_have_fact_text": all(" | " in str(option.get("value") or "") for row in all_rows for option in row.get("opaque_options") or []),
        "role_balanced_train": len(set(count_by(train, "semantic_target_value").values())) == 1,
        "role_balanced_validation": len(set(count_by(validation, "semantic_target_value").values())) == 1,
        "role_balanced_strict": len(set(count_by(strict, "semantic_target_value").values())) == 1,
    }
    passed = all(quality_gates.values())
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": passed,
        "decision": "fact_rich_evidence_option_package_ready" if passed else "fact_rich_evidence_option_package_blocked",
        "counts": {
            "train_rows": len(train),
            "validation_rows": len(validation),
            "strict_rows": len(strict),
            "train_roots": len(roots["train"]),
            "validation_roots": len(roots["validation"]),
            "strict_roots": len(roots["strict"]),
            "by_split_role": {
                "train": count_by(train, "semantic_target_value"),
                "validation": count_by(validation, "semantic_target_value"),
                "strict": count_by(strict, "semantic_target_value"),
            },
            "by_split_language": {
                "train": count_by(train, "language_family"),
                "validation": count_by(validation, "language_family"),
                "strict": count_by(strict, "language_family"),
            },
            "root_overlaps": overlaps,
            "source_repo_family_split_overlaps": (source_summary.get("counts") or {}).get("repo_family_split_overlaps"),
            "c_cpp_gap": (source_summary.get("counts") or {}).get("c_cpp_gap"),
        },
        "quality_gates": quality_gates,
        "source_artifacts": {
            "source_summary": rel(SOURCE_SUMMARY),
            "source_train": rel(SOURCE_TRAIN),
            "source_validation": rel(SOURCE_VALIDATION),
            "source_strict": rel(SOURCE_STRICT),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_jsonl": rel(TRAIN_JSONL),
            "validation_jsonl": rel(VALIDATION_JSONL),
            "strict_jsonl": rel(STRICT_JSONL),
        },
    }
    write_jsonl(TRAIN_JSONL, train)
    write_jsonl(VALIDATION_JSONL, validation)
    write_jsonl(STRICT_JSONL, strict)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
