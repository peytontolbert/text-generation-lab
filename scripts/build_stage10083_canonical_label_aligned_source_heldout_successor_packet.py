#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10083
NAME = "stage10083_canonical_label_aligned_source_heldout_successor_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "canonical_label_aligned_source_heldout_successor_packet.json"
MANIFEST = OUT_DIR / "canonical_label_aligned_source_heldout_manifest.jsonl"
ROWS = OUT_DIR / "canonical_label_aligned_source_heldout_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_LABEL_ALIGNED_SOURCE_HELDOUT_SUCCESSOR_PACKET_STAGE10083.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10036_real_fresh_heldout_merge_validator/expanded_source_heldout_manifest.jsonl"
COLLISION_AUDIT = ROOT / "runs/summaries/stage10068_multilingual_label_semantics_collision_audit.json"

CANONICAL_LABEL_MAP = {
    "TARGET_TEST": "A",
    "TARGET_ENTRYPOINT": "B",
    "TARGET_SYMBOL": "C",
    "TARGET_FILE": "D",
    "TARGET_CONFIG": "E",
}


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
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "next_best_step": summary["next_best_step"],
    })
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


def _canonicalize_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(row)
    clean = updated.get("clean_state") if isinstance(updated.get("clean_state"), dict) else {}
    target = updated.get("target") if isinstance(updated.get("target"), dict) else {}
    hidden = str(clean.get("edit_localization_target_hidden") or "")
    if not hidden:
        raise KeyError(f"missing hidden target for {row.get('row_id')}")
    canonical = CANONICAL_LABEL_MAP[hidden]
    clean["edit_localization"] = canonical
    clean["edit_localization_target"] = canonical
    target["decoder_text"] = canonical
    target["edit_localization"] = canonical
    target["target_ref"] = canonical
    updated["clean_state"] = clean
    updated["target"] = target
    updated["stage10083_canonical_label"] = canonical
    updated["stage10083_hidden_target"] = hidden
    return updated


def build_packet() -> dict[str, Any]:
    base_rows = load_jsonl(BASE_MANIFEST)
    collision_summary = load_json(COLLISION_AUDIT)
    failures: list[str] = []
    remapped_rows: list[dict[str, Any]] = []
    remap_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    heldout_language_maps: dict[str, dict[str, str]] = {}
    heldout_rows = 0
    heldout_permutation = 0
    heldout_opaque_choice = 0
    heldout_locked_eval_source = 0

    for row in base_rows:
        try:
            updated = _canonicalize_row(row)
        except Exception:
            failures.append(f"canonicalize_failed:{row.get('row_id')}")
            continue
        remapped_rows.append(updated)
        language = str(updated.get("language_family") or "")
        split = str(updated.get("split") or "")
        clean = updated.get("clean_state") if isinstance(updated.get("clean_state"), dict) else {}
        label = str(clean.get("edit_localization_target") or "")
        hidden = str(clean.get("edit_localization_target_hidden") or "")
        remap_counts[f"{language}:{label}"] += 1
        language_counts[language] += 1
        split_counts[split] += 1
        if split in {"eval", "strict_eval"}:
            heldout_rows += 1
            heldout_language_maps.setdefault(language, {})[label] = hidden
            if updated.get("choice_permutation_map") and updated.get("choice_permutation_order"):
                heldout_permutation += 1
            anti_cheat = updated.get("anti_cheat") if isinstance(updated.get("anti_cheat"), dict) else {}
            if anti_cheat.get("opaque_choice_surface") is True:
                heldout_opaque_choice += 1
            source_lineage = updated.get("source_lineage") if isinstance(updated.get("source_lineage"), dict) else {}
            if source_lineage.get("locked_eval_source") is True:
                heldout_locked_eval_source += 1

    write_jsonl(ROWS, remapped_rows)
    write_jsonl(MANIFEST, remapped_rows)

    metrics = {
        "rows": len(remapped_rows),
        "language_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "remap_counts": dict(sorted(remap_counts.items())),
        "heldout_rows": heldout_rows,
        "heldout_rows_with_choice_permutation_metadata": heldout_permutation,
        "heldout_rows_with_opaque_choice_surface": heldout_opaque_choice,
        "heldout_rows_with_locked_eval_source": heldout_locked_eval_source,
        "heldout_per_language_label_map": {
            language: dict(sorted(mapping.items()))
            for language, mapping in sorted(heldout_language_maps.items())
        },
        "canonical_label_map": dict(sorted(CANONICAL_LABEL_MAP.items())),
    }
    if collision_summary.get("passed") is not True:
        failures.append("stage10068_not_passed")
    if metrics["rows"] != 95:
        failures.append("rows_not_95")
    if split_counts.get("train") != 40:
        failures.append("train_rows_not_40")
    if split_counts.get("eval") != 38:
        failures.append("eval_rows_not_38")
    if split_counts.get("strict_eval") != 17:
        failures.append("strict_rows_not_17")
    if language_counts.get("python") != 19:
        failures.append("python_rows_not_19")
    if language_counts.get("c_cpp") != 30:
        failures.append("c_cpp_rows_not_30")
    if language_counts.get("rust") != 11:
        failures.append("rust_rows_not_11")
    if language_counts.get("web_js_ts_html") != 35:
        failures.append("web_rows_not_35")
    if heldout_rows != 55:
        failures.append("heldout_rows_not_55")
    expected_map = {
        "A": "TARGET_TEST",
        "B": "TARGET_ENTRYPOINT",
        "C": "TARGET_SYMBOL",
        "D": "TARGET_FILE",
        "E": "TARGET_CONFIG",
    }
    for language, mapping in heldout_language_maps.items():
        for label, hidden in mapping.items():
            if expected_map[label] != hidden:
                failures.append(f"heldout_canonical_mismatch:{language}:{label}")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "policy": {
            "preserve_stage10036_source_heldout_row_composition": True,
            "canonicalize_label_semantics_only": True,
            "preserve_existing_anti_cheat_and_provenance_fields": True,
            "next_required_rerun_is_same_manifest_for_100m_and_gemma": True,
        },
        "inputs": {
            "base_manifest": display(BASE_MANIFEST),
            "collision_audit": display(Path("runs/local/artifacts/stage10068_multilingual_label_semantics_collision_audit/multilingual_label_semantics_collision_audit.json")),
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    write_json(PACKET, built)
    next_step = (
        "Run the target-100m probe and local Gemma queue on this canonical source-heldout manifest so the next comparison measures the label-semantic fix on the honest 55-row heldout bank."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "packet": display(PACKET),
            "rows": display(ROWS),
            "manifest": display(MANIFEST),
            "doc": display(DOC),
        },
        "decision": "Materialized a canonical-label source-heldout successor packet by remapping the stage10036 expanded heldout manifest so every hidden edit-target family uses the same opaque label across languages while preserving the existing provenance and anti-cheat fields.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10083 Canonical Label Aligned Source Heldout Successor Packet",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows: `{built['metrics']['rows']}`",
        f"Heldout rows: `{built['metrics']['heldout_rows']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": built["failures"], "metrics": built["metrics"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
