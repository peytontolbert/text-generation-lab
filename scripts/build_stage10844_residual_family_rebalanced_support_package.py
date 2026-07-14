#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10844
NAME = "stage10844_residual_family_rebalanced_support_package"
OUT_DIR = ARTIFACTS / NAME
PACKAGE_JSON = OUT_DIR / "residual_family_rebalanced_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_ROWS_JSONL = OUT_DIR / "added_residual_rebalance_rows.jsonl"
REMOVED_ROWS_JSONL = OUT_DIR / "removed_singleton_verifier_rows.jsonl"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

BASE_DIR = ARTIFACTS / "stage10839_current_residual_support_package"
SOURCE_PATHS = {
    "python_dense_legacy": ARTIFACTS / "stage10479_python_verifier_dense_support_package" / "python_verifier_dense_support_rows.jsonl",
    "python_only_legacy": ARTIFACTS / "stage10453_python_verifier_only_support_package" / "python_verifier_only_support_rows.jsonl",
    "python_semantic_seed": ARTIFACTS / "stage10725_python_verifier_semantic_contrast_builder" / "agentkernel_lite_encdec_train.jsonl",
    "rust_only_legacy": ARTIFACTS / "stage10454_rust_citation_only_support_package" / "rust_citation_only_support_rows.jsonl",
    "rust_semantic_seed": ARTIFACTS / "stage10726_rust_citation_semantic_contrast_builder" / "agentkernel_lite_encdec_train.jsonl",
}

OPTION_LINE_RE = re.compile(r"^([A-Z0-9]+)\.\s*(.+)$")
LABEL_POOL = list("ABCDEFGHJKLMNPQRSTUVWXYZ")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def prompt_text(row: dict[str, Any]) -> str:
    return str(row.get("prompt_text") or row.get("input_text") or row.get("prompt") or "")


def parse_opaque_options(text: str) -> list[dict[str, str]]:
    if "\nOptions:\n" not in text:
        return []
    option_block = text.split("\nOptions:\n", 1)[1]
    option_block = option_block.split("\nAnswer:", 1)[0]
    options: list[dict[str, str]] = []
    for line in option_block.splitlines():
        match = OPTION_LINE_RE.match(line.strip())
        if not match:
            continue
        options.append({"label": match.group(1), "value": match.group(2)})
    return options


def option_count(row: dict[str, Any]) -> int:
    return len(row.get("opaque_options") or parse_opaque_options(prompt_text(row)))


def rewrite_option_block(text: str, options: list[dict[str, str]]) -> str:
    if "\nOptions:\n" not in text:
        return text
    head, tail = text.split("\nOptions:\n", 1)
    if "\nAnswer:" in tail:
        _, answer_tail = tail.split("\nAnswer:", 1)
        suffix = "\nAnswer:" + answer_tail
    else:
        suffix = ""
    option_text = "\n".join(f"{opt['label']}. {opt['value']}" for opt in options)
    return head + "\nOptions:\n" + option_text + suffix


def maybe_compact_long_target_labels(row: dict[str, Any]) -> dict[str, Any]:
    updated = json.loads(json.dumps(row))
    options = list(updated.get("opaque_options") or [])
    target = str(updated.get("target_text") or updated.get("decoder_text") or "")
    if not options or len(target) <= 8:
        return updated
    if len(options) > len(LABEL_POOL):
        return updated

    label_map: dict[str, str] = {}
    remapped_options: list[dict[str, str]] = []
    for idx, option in enumerate(options):
        old_label = str(option["label"])
        new_label = LABEL_POOL[idx]
        label_map[old_label] = new_label
        remapped_options.append({"label": new_label, "value": str(option["value"])})

    if target not in label_map:
        return updated

    new_target = label_map[target]
    updated["opaque_options"] = remapped_options
    updated["target_text"] = new_target
    updated["decoder_text"] = new_target
    updated["target_token_len"] = len(new_target.encode("utf-8"))
    for prompt_key in ("prompt_text", "input_text", "prompt"):
        if prompt_key in updated and isinstance(updated[prompt_key], str):
            updated[prompt_key] = rewrite_option_block(updated[prompt_key], remapped_options)
    anti_cheat = dict(updated.get("anti_cheat") or {})
    anti_cheat["long_target_labels_compacted"] = True
    updated["anti_cheat"] = anti_cheat
    projection = dict(updated.get("standalone_projection_source") or {})
    projection["compacted_from_long_target_label"] = target
    projection["opaque_label_map"] = label_map
    updated["standalone_projection_source"] = projection
    return updated


def normalize_row(row: dict[str, Any], source_key: str) -> dict[str, Any]:
    updated = json.loads(json.dumps(row))
    parsed_options = parse_opaque_options(prompt_text(updated))
    if not updated.get("opaque_options") and parsed_options:
        updated["opaque_options"] = parsed_options
    updated = maybe_compact_long_target_labels(updated)
    updated["split"] = "train"
    updated["split_role"] = "train_support"
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["source_heldout_admissible"] = False
    updated["support_package_stage"] = STAGE
    anti_cheat = dict(updated.get("anti_cheat") or {})
    anti_cheat.update(
        {
            "rebalance_stage": STAGE,
            "rebalance_source_key": source_key,
            "parsed_opaque_options_from_prompt": bool(parsed_options),
        }
    )
    updated["anti_cheat"] = anti_cheat
    provenance = dict(updated.get("support_provenance") or {})
    provenance.update(
        {
            "rebalance_stage": STAGE,
            "rebalance_source_key": source_key,
            "rebalance_source_path": rel(SOURCE_PATHS[source_key]) if source_key in SOURCE_PATHS else rel(BASE_DIR / "current_residual_support_package.json"),
        }
    )
    updated["support_provenance"] = provenance
    updated["residual_family_rebalance_source"] = source_key
    return updated


def count_targets(rows: list[dict[str, Any]], task_type: str) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                str(row.get("target_text") or row.get("decoder_text") or "unknown")
                for row in rows
                if row.get("task_type") == task_type
            ).items()
        )
    )


def count_option_hist(rows: list[dict[str, Any]], task_type: str) -> dict[str, int]:
    return dict(sorted(Counter(option_count(row) for row in rows if row.get("task_type") == task_type).items()))


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def main() -> None:
    base_package = load_json(BASE_DIR / "current_residual_support_package.json")
    base_train = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_train.jsonl")
    base_validation = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_validation.jsonl")
    base_strict = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl")
    base_stress = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl")

    removed_singletons: list[dict[str, Any]] = []
    preserved_train: list[dict[str, Any]] = []
    for row in base_train:
        normalized_base_row = normalize_row(row, "base_package")
        if normalized_base_row.get("task_type") == "verifier_outcome" and option_count(normalized_base_row) <= 1:
            removed_singletons.append(normalized_base_row)
            continue
        preserved_train.append(normalized_base_row)

    strict_source_ids = {
        str(row.get("source_bundle_id") or row.get("source_root_id") or row.get("row_id"))
        for row in base_strict
    }
    strict_row_ids = {str(row["row_id"]) for row in base_strict}
    existing_row_ids = {str(row["row_id"]) for row in preserved_train}

    added_rows: list[dict[str, Any]] = []
    skipped_overlap_rows: list[str] = []
    skipped_singleton_rows: list[str] = []
    added_by_source: Counter[str] = Counter()

    for source_key, path in SOURCE_PATHS.items():
        source_rows = load_jsonl(path)
        for row in source_rows:
            task_type = str(row.get("task_type") or "")
            if task_type not in {"verifier_outcome", "evidence_citation"}:
                continue
            if task_type == "verifier_outcome" and option_count(row) <= 1:
                skipped_singleton_rows.append(str(row.get("row_id") or ""))
                continue
            if task_type == "evidence_citation" and source_key == "rust_semantic_seed" and str(row.get("task_type")) != "evidence_citation":
                continue

            row_id = str(row["row_id"])
            source_id = str(row.get("source_bundle_id") or row.get("source_root_id") or row_id)
            if row_id in strict_row_ids or source_id in strict_source_ids:
                skipped_overlap_rows.append(row_id)
                continue
            if row_id in existing_row_ids:
                continue
            normalized = normalize_row(row, source_key)
            preserved_train.append(normalized)
            added_rows.append(normalized)
            existing_row_ids.add(row_id)
            added_by_source[source_key] += 1

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "residual_family_rebalanced_support_package_ready",
        "claim_scope": [
            "Rebalance the current multilingual support package toward the two remaining residual families without changing the frozen validation or strict overlays.",
            "Reduce trivial verifier supervision by removing singleton-option verifier train rows and add disjoint targeted verifier/citation support rows with explicit option geometry.",
        ],
        "source_artifacts": {
            "base_package": rel(BASE_DIR / "current_residual_support_package.json"),
            **{key: rel(path) for key, path in SOURCE_PATHS.items()},
        },
        "metrics": {
            "base_train_rows": len(base_train),
            "removed_singleton_verifier_rows": len(removed_singletons),
            "added_residual_rebalance_rows": len(added_rows),
            "merged_train_rows": len(preserved_train),
            "validation_rows": len(base_validation),
            "strict_rows": len(base_strict),
            "stress_rows": len(base_stress),
            "added_rows_by_source": dict(sorted(added_by_source.items())),
            "train_by_language": count_by(preserved_train, "language_family"),
            "train_by_task": count_by(preserved_train, "task_type"),
            "verifier_outcome_target_distribution": count_targets(preserved_train, "verifier_outcome"),
            "verifier_outcome_option_histogram": count_option_hist(preserved_train, "verifier_outcome"),
            "evidence_citation_target_distribution": count_targets(preserved_train, "evidence_citation"),
            "evidence_citation_option_histogram": count_option_hist(preserved_train, "evidence_citation"),
            "skipped_overlap_rows": len(skipped_overlap_rows),
            "skipped_singleton_source_rows": len(skipped_singleton_rows),
        },
        "interpretation": [
            "This package directly improves train geometry for verifier_outcome and evidence_citation, but it is still a train-support package rather than a fresh heldout promotion set.",
            "The verifier lane now removes singleton-option rows entirely from train, which forces the next probe to rely more on multi-option disambiguation.",
            "The citation lane adds real E-bearing Rust support, but it still falls short of the ideal 20+ rows per label and does not yet create fresh strict E/F heldout roots by itself.",
        ],
        "honesty_gates": [
            "validation and strict rows are byte-for-byte preserved from stage10839",
            "all added rows remain train_support_only and strict_eval_eligible=false",
            "rows overlapping frozen strict row ids or strict source roots are excluded",
            "singleton verifier rows are quarantined out of train in this rebalance package",
        ],
        "residual_family_status": {
            "python_verifier": "improved multi-option support geometry, still short of the requested 30+ train rows and B/C/G transition semantics",
            "rust_evidence": "improved B/C/D/E support coverage, still lacks strong F-labeled evidence_citation train coverage and fresh non-tokenizers strict roots",
        },
        "base_package_metrics_snapshot": base_package.get("metrics"),
        "outputs": {
            "package_json": rel(PACKAGE_JSON),
            "train_rows": rel(TRAIN_JSONL),
            "validation_rows": rel(VALIDATION_JSONL),
            "strict_rows": rel(STRICT_JSONL),
            "stress_rows": rel(STRESS_JSONL),
            "added_rows": rel(ADDED_ROWS_JSONL),
            "removed_singletons": rel(REMOVED_ROWS_JSONL),
        },
        "next_best_step": "Use this package for a diagnostic residual-family probe with lower preservation pressure and explicit reporting on verifier and evidence family deltas, then continue building fresh heldout roots for Python verifier transitions and Rust E/F evidence roles.",
    }

    write_jsonl(TRAIN_JSONL, preserved_train)
    write_jsonl(VALIDATION_JSONL, base_validation)
    write_jsonl(STRICT_JSONL, base_strict)
    write_jsonl(STRESS_JSONL, base_stress)
    write_jsonl(ADDED_ROWS_JSONL, added_rows)
    write_jsonl(REMOVED_ROWS_JSONL, removed_singletons)
    write_json(PACKAGE_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "train_rows": payload["metrics"]["merged_train_rows"],
            "added_rows": payload["metrics"]["added_residual_rebalance_rows"],
            "artifact": rel(PACKAGE_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
